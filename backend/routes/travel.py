from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import get_base_url, get_model_name, llm_configured
from schemas import FactorCreate, FactorUpdate, GenerateRequest, Persona, SimulateRequest, SimulateResponse
from services.factor_store import add_factor, delete_factor, load_factors_db, update_factor
from services.job_store import load_jobs, load_outcomes, load_stages, load_sub_jobs
from services.persona_store import get_personas, set_personas
from services.travel_harness import generate_personas, identify_factors, load_factors, simulate_persona

router = APIRouter(prefix="/api", tags=["travel-sandbox"])
ROOT = Path(__file__).resolve().parents[2]
MEMORY_PATH = ROOT / "data" / "travel_memories.json"


@router.get("/config")
def config_status():
    return {"llm_configured": llm_configured(), "model": get_model_name(), "base_url": get_base_url()}


@router.get("/jobs")
def jobs_map():
    jobs = load_jobs()
    steps = load_sub_jobs()
    step_by_id = {x.id: x for x in steps}
    trees = []
    for job in jobs:
        by_stage: dict[str, list] = {stage: [] for stage in load_stages()}
        for sid in job.step_ids:
            step = step_by_id.get(sid)
            if step:
                by_stage.setdefault(step.stage, []).append(step.model_dump())
        trees.append({**job.model_dump(), "stages": [{"name": stage, "steps": rows} for stage, rows in by_stage.items() if rows]})
    return {"jobs": [x.model_dump() for x in jobs], "sub_jobs": [x.model_dump() for x in steps], "job_trees": trees, "stages": load_stages(), "outcomes": [x.model_dump() for x in load_outcomes()]}


@router.get("/outcomes")
def outcomes():
    return [x.model_dump() for x in load_outcomes()]


@router.get("/factors")
def factors():
    return load_factors_db().model_dump()


@router.post("/factors")
def create_factor(body: FactorCreate):
    try:
        return add_factor(body).model_dump()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/factors/{factor_id}")
def edit_factor(factor_id: str, body: FactorUpdate):
    try:
        return update_factor(factor_id, body).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/factors/{factor_id}")
def remove_factor(factor_id: str):
    try:
        return delete_factor(factor_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/personas")
def personas():
    return [p.model_dump() for p in get_personas()]


@router.post("/generate", response_model=list[Persona])
def generate(body: GenerateRequest):
    try:
        job_ids = body.job_ids or body.options.get("job_ids")
        generated = generate_personas(body.count, use_llm=llm_configured() if body.use_llm is None else body.use_llm, job_ids=job_ids)
        return [p.model_dump() for p in set_personas(generated, reason="travel_generate")]
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败：{exc}") from exc


@router.post("/simulate", response_model=SimulateResponse)
def simulate(body: SimulateRequest):
    current = get_personas()
    if not current:
        raise HTTPException(status_code=400, detail="请先生成旅游画像")
    if not body.campaign.strip():
        raise HTTPException(status_code=400, detail="话术或旅行方案不能为空")
    if body.use_llm and not llm_configured():
        raise HTTPException(status_code=400, detail="LLM 未配置；请设置漫创共享 .env 路径或本项目 DeepSeek 环境变量。")
    selected = [p for p in current if not body.persona_ids or p.id in body.persona_ids]
    factor_list, outcomes_list = load_factors(), load_outcomes()
    hits = identify_factors(body.campaign, factor_list)
    try:
        memories = json.loads(MEMORY_PATH.read_text(encoding="utf-8")) if body.use_memory and MEMORY_PATH.exists() else {}
        if not isinstance(memories, dict):
            memories = {}
        results = [simulate_persona(p, body.campaign, factor_list, outcomes_list, hits, use_llm=body.use_llm,
                                   memory=memories.get(p.id, [])) for p in selected]
        if body.use_memory:
            for result in results:
                history = memories.setdefault(result.persona_id, [])
                history.append({"campaign": body.campaign, "decision": result.decision,
                                "outcome_improved": result.outcome_improved, "next_step": result.next_step})
                memories[result.persona_id] = history[-10:]
            MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_PATH.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"仿真失败：{exc}") from exc
    summary = {key: sum(1 for item in results if item.decision == key) for key in ("advance", "hesitate", "na", "reject")}
    return SimulateResponse(results=results, summary=summary, campaign_hits=[f.name for f in factor_list if f.id in hits])


@router.post("/memories/reset")
def reset_memories():
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text("{}", encoding="utf-8")
    return {"status": "ok"}

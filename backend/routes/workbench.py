"""Original workbench export and memory controls, backed by travel simulation data."""
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from schemas import ExportCampaignRequest, VerificationRequest
from services.persona_store import get_personas
from services.export_campaign import build_campaign_workbook
from routes import travel

router = APIRouter(prefix="/api", tags=["travel-workbench"])

def memories():
    if not travel.MEMORY_PATH.exists():
        return {}
    return json.loads(travel.MEMORY_PATH.read_text(encoding="utf-8"))

def save(data):
    travel.MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    travel.MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def require_persona(identifier):
    if not any(p.id == identifier for p in get_personas()):
        raise HTTPException(404, "旅游画像不存在")

@router.post("/export/campaign")
def export_campaign(body: ExportCampaignRequest):
    if not body.results:
        raise HTTPException(400, "请先运行旅行方案测试")
    content = build_campaign_workbook(campaign=body.campaign, results=body.results,
        personas=get_personas(), campaign_hits=body.campaign_hits, interventions=body.interventions,
        use_llm=body.use_llm, use_memory=body.use_memory)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Travel_Campaign.xlsx"'})

@router.get("/personas/{identifier}/memories")
def timeline(identifier: str):
    require_persona(identifier)
    rows = memories().get(identifier, [])
    return {"persona_id": identifier, "day": len(rows), "reflections": [], "memories": [
        {"id": str(i), "day": i, "type": "observation", "content": r.get("note") or
         f"方案：{r.get('campaign', '')}；判定：{r.get('decision', '')}；下一步：{r.get('next_step', '')}",
         "importance": 5} for i, r in enumerate(rows, 1)]}

@router.post("/personas/{identifier}/memories/reset")
def reset_one(identifier: str):
    require_persona(identifier)
    data = memories()
    data.pop(identifier, None)
    save(data)
    return {"ok": True}

@router.get("/memories/export")
def export_memories():
    return Response(json.dumps({"format": "travel-memories-v1", "memories": memories()}, ensure_ascii=False),
        media_type="application/json", headers={"Content-Disposition": 'attachment; filename="travel_memories.json"'})

@router.post("/memories/import")
async def import_memories(file: UploadFile = File(...), replace: bool = True):
    try:
        bundle = json.loads(await file.read())
        if not isinstance(bundle, dict) or bundle.get("format") != "travel-memories-v1":
            raise ValueError()
        rows = bundle["memories"]
        if not isinstance(rows, dict) or any(not isinstance(k, str) or not isinstance(v, list) or
                any(not isinstance(r, dict) or any(not isinstance(r.get(f, ""), str) for f in
                    ("campaign", "decision", "next_step", "note")) for r in v) for k, v in rows.items()):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, "旅游记忆包格式不正确")
    data = {} if replace else memories()
    valid = {p.id for p in get_personas()}
    data.update({k: v[-10:] for k, v in rows.items() if k in valid})
    save(data)
    return {"ok": True, "message": "旅游方案记忆已导入"}

@router.post("/verify")
def verify(body: VerificationRequest):
    require_persona(body.persona_id)
    if body.status not in {"verified", "unverified", "opposite"}:
        raise HTTPException(400, "验证状态不正确")
    data = memories()
    rows = data.setdefault(body.persona_id, [])
    rows.append({"campaign": body.campaign, "decision": body.decision or "", "note": body.note,
                 "verification": body.status})
    data[body.persona_id] = rows[-10:]
    save(data)
    return {"ok": True}

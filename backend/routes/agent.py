import json
import secrets
from copy import deepcopy
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from agent_schemas import ProfileRequest, ReviewRequest, PrototypeRequest, AnalysisRequest, CompareRequest, DiscussionRequest
from services import agent_store as store, research_agent as agent, agent_media

router = APIRouter(prefix="/api/agent", tags=["research-agent"])


def call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, "记录不存在或已删除") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:500]) from exc


def request_key(request):
    key = request.headers.get("Idempotency-Key")
    if key and (len(key) > 100 or len(key) < 8):
        raise HTTPException(422, "提交编号需为 8–100 个字符")
    return key


def start(action, snapshot, key=None):
    row, created = store.new_run(action, snapshot, key)
    return agent.launch(row, created)


@router.get("/profiles")
def profiles():
    return {"profiles": call(agent.profiles)}


@router.post("/profiles/extract", status_code=202)
def extract(body: ProfileRequest, request: Request):
    messages = call(agent.parse_messages, body)
    snapshot = {"label": body.label, "episode": body.episode, "target_speaker": body.target_speaker,
                "messages": messages, "media_id": body.media_id}
    return call(start, "extract", snapshot, request_key(request))


@router.post("/profiles/prototype", status_code=201)
def prototype(body: PrototypeRequest):
    content = call(agent.validate_profile, body.model_dump(include={"summary", "needs", "unknowns"}), [], "", True)
    return store.put("profile", {"id": "P"+secrets.token_hex(12), "label": body.label, "episode": body.episode,
        "type": "custom_archetype", "status": "reviewed", "revision": 1, "messages": [], **content,
        "origin": "用户自定义假设原型，不对应真实人口样本", "created_at": store.now()})


@router.put("/profiles/{identifier}/review")
def review(identifier: str, body: ReviewRequest):
    with store.LOCK:
        profile = call(store.get, "profile", identifier)
        if profile["type"] != "source_profile":
            raise HTTPException(422, "此接口只用于核对资料画像")
        if body.expected_revision != profile["revision"]:
            raise HTTPException(409, "画像已更新，请刷新后重新核对")
        content = call(agent.validate_profile, body.model_dump(include={"summary", "needs", "unknowns"}), profile["messages"], profile["target_speaker"])
        profile.update(content, revision=profile["revision"]+1, status="reviewed", reviewer=body.reviewer, reviewed_at=store.now(),
                       origin="操作者已核对资料与画像；不等于被分析对象本人确认")
        return store.put("profile", profile)


@router.delete("/profiles/{identifier}")
def delete_profile(identifier: str):
    with store.LOCK:
        call(store.get, "profile", identifier)
        for run in store.listing("run"):
            if identifier in json.dumps(run, ensure_ascii=False):
                store.remove("run", run["id"])
        store.remove("profile", identifier)
    return {"deleted": True}


@router.post("/analyses", status_code=202)
def analyze(body: AnalysisRequest, request: Request):
    return call(start, "analyze", call(agent.create_analysis_snapshot, body), request_key(request))


@router.post("/runs/{identifier}/compare", status_code=202)
def compare(identifier: str, body: CompareRequest, request: Request):
    parent = call(store.get, "run", identifier)
    if parent["action"] not in {"analyze", "discuss"} or parent["status"] not in {"completed", "partial"}:
        raise HTTPException(422, "请选择已完成的需求分析作为对照基线")
    snapshot = deepcopy(parent["snapshot"])
    snapshot.setdefault("dimensions", [])
    snapshot.update(plan=body.plan, discussion=body.discussion, parent_id=identifier, parent_cases=parent["result"]["cases"])
    return call(start, "analyze", snapshot, request_key(request))


@router.post("/runs/{identifier}/discuss", status_code=202)
def discuss(identifier: str, body: DiscussionRequest, request: Request):
    parent = call(store.get, "run", identifier)
    if parent["action"] not in {"analyze", "discuss"} or parent["status"] not in {"completed", "partial"}:
        raise HTTPException(422, "请先完成需求分析，再讨论取舍")
    snapshot = deepcopy(parent["snapshot"])
    snapshot.setdefault("dimensions", [])
    snapshot.update(discussion=body.discussion, parent_id=identifier, parent_cases=parent["result"]["cases"])
    return call(start, "discuss", snapshot, request_key(request))


@router.get("/runs")
def runs():
    # List summaries only; full source snapshots remain in the explicit task detail.
    return {"runs": [{k: row[k] for k in ("id", "action", "status", "created_at", "updated_at", "error")}
                     for row in store.listing("run")[:100]]}


@router.get("/runs/{identifier}")
def run_detail(identifier: str):
    return call(store.get, "run", identifier)


@router.get("/runs/{identifier}/events")
def events(identifier: str, after: int = 0):
    run = call(store.get, "run", identifier)
    return {"events": [e for e in run["events"] if e["seq"] > after], "status": run["status"]}


@router.post("/runs/{identifier}/cancel")
def cancel(identifier: str):
    call(store.get, "run", identifier)
    return store.update_run(identifier, cancel_requested=True, status="cancelled", error="用户已取消；已发出的请求可能产生用量")


@router.get("/runs/{identifier}/report")
def report(identifier: str):
    run = call(store.get, "run", identifier)
    if run["action"] not in {"analyze", "discuss"} or run["status"] not in {"completed", "partial"}:
        raise HTTPException(422, "报告尚未完成")
    result = run["result"]
    snapshot = run["snapshot"]
    labels = {p["id"]: p for p in snapshot["profiles"]}
    lines = ["# 旅游方案需求分析", "", snapshot["cohort_notice"], "", "## 方案", "", snapshot["plan"], "", "## 业务约束", "", snapshot["constraints"] or "未提供",
             "", "## 分析概述", "", result["recommendations"]["summary"]]
    lines.extend(["", "## 启用决策维度匹配", "", "维度权重仅表示研究关注优先级，不是满足分数或概率。"])
    for row in result.get("dimension_summary", []):
        lines.append(f"- {row['id']} {row['name']}（优先级 {row['weight']}）：匹配 {row['need_matches']} 项需求 / {row['profile_matches']} 个画像")
    lines.extend(["", "## 逐项需求与依据"])
    for case in result["cases"]:
        p = labels[case["profile_id"]]
        needs = {n["id"]: n for n in p["needs"]}
        messages = {m["id"]: m for m in p.get("messages", [])}
        lines.extend(["", f"### {p['label']} · {agent.STATUSES[case['status']]}", f"角色类型：{p['type']}；画像版本：{p['revision']}；情境：{p['episode']}"])
        for row in case["rows"]:
            need = needs[row["need_id"]]
            lines.extend(["", f"- {need['label']}：{agent.STATUSES[row['status']]}（{need['kind']}）", f"  - {row['explanation']}", f"  - 方案依据：{'；'.join(row['plan_quotes']) or '未找到'}"])
            for match in row.get("factor_matches", []):
                factor = next((item for item in snapshot.get("dimensions", []) if item["id"] == match["factor_id"]), None)
                if factor:
                    lines.append(f"  - 相关维度：{factor['id']} {factor['name']}（权重 {factor['weight']}）：{match['rationale']}；方案原文：{match['plan_quote']}")
            for ref in need["evidence"]:
                m = messages[ref["message_id"]]
                lines.append(f"  - 资料依据 [{m['id']}] {m['speaker']} {m.get('start') if m.get('start') is not None else ''}：{ref['quote']}")
    lines.extend(["", "## 待确认", *["- "+q for q in result["recommendations"]["questions"]], "", "## 候选修改（尚待对照验证）"])
    for candidate in result["recommendations"]["candidates"]:
        lines.extend(["", "### "+candidate["title"], candidate["plan"], "取舍："+candidate["tradeoff"]])
    lines.extend(["", "## 覆盖统计", json.dumps(result["metrics"], ensure_ascii=False), "", "## 执行记录", *[f"- {e['at']} {e['tool']} {e['status']}：{e['summary']}" for e in run["events"]]])
    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="travel-analysis-{identifier}.md"'})


@router.post("/media", status_code=202)
async def upload(request: Request):
    if request.headers.get("X-Research-Consent") != "true":
        raise HTTPException(422, "请确认录音可用于本次分析")
    try:
        media = await agent_media.receive(request, unquote(request.headers.get("X-Filename", "")))
        run = start("transcribe", {"media_id": media["id"]})
        return {"media_id": media["id"], "run_id": run["id"]}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/media")
def media_list():
    return {"media": [{k: row.get(k) for k in ("id", "label", "status", "created_at")} for row in store.listing("media")]}


@router.get("/media/{identifier}")
def media_detail(identifier: str):
    row = call(store.get, "media", identifier)
    return {k: v for k, v in row.items() if k != "filename"}


@router.get("/media/{identifier}/audio")
def audio(identifier: str):
    row = call(store.get, "media", identifier)
    return FileResponse(store.MEDIA_DIR / row["filename"], filename=row["label"])


@router.delete("/media/{identifier}")
def delete_media(identifier: str):
    call(store.purge_media, identifier)
    return {"deleted": True, "note": "已删除录音、转录、相关画像及报告"}

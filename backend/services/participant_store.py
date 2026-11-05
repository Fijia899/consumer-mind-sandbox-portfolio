"""Local evidence ledger. Imports never manufacture people or overwrite forecasts."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from participant_schemas import ParticipantInput, ParticipantReview
from services import observed_profiles

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "data" / "participants_state.json"
ARCHIVE_DIR = ROOT / "data" / "legacy_archive"
LEGACY_PATHS = [ROOT / "data" / name for name in ("personas.json", "research_state.json", "travel_memories.json")]
LOCK = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def canonical(url):
    parts = urlsplit(url)
    if parts.scheme in {"http", "https"}:
        tracking = {"xsec_token", "xsec_source", "share_from_user_hidden", "share_id"}
        query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_") and k.lower() not in tracking)
        return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))
    return url.strip()


def subject_id(platform, key):
    # Source-local continuity only; no automatic linking across platforms.
    return "U" + digest([platform.strip().casefold(), key.strip()])[:20]


def _save(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATE_PATH)


def archive_legacy():
    originals = {p.name: p.read_bytes() for p in LEGACY_PATHS if p.exists()}
    archive_id = digest({name: hashlib.sha256(body).hexdigest() for name, body in originals.items()})[:20]
    directory = ARCHIVE_DIR / archive_id
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for name, body in originals.items():
        target = directory / name
        if target.exists():
            if target.read_bytes() != body:
                raise ValueError("历史备份校验失败，停止迁移")
        else:
            target.write_bytes(body)
        files.append({"file": name, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
    manifest = {"archive_id": archive_id, "mode": "read_only", "files": files}
    path = directory / "manifest.json"
    if not path.exists():
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _seed_participants():
    bundle = observed_profiles.load()
    participants = []
    for original in bundle["profiles"]:
        participant = {
            "id": original["id"], "subject_key": original["account_id"], "platform": "小红书",
            "label": original["label"], "profile_url": original["profile_url"],
            "identity_level": "account_traceable", "identity_evidence": "仅核对站内作者账号一致，未核验现实身份",
            "status": "accepted", "revision": 1, "evaluation_split": None,
            "created_at": now(), "updated_at": now(), "origin": bundle["id"],
            "limitations": original["limitations"] + ["迁入的是已核对摘要与短引文，未保存完整原文。"],
            "unknowns": original["unknowns"], "sources": [], "facts": [], "insights": [], "episodes": [],
            "reviews": [{"status": "accepted", "reviewer": "公开来源核查迁移", "method": "assisted",
                         "note": bundle["methodology"]["inclusion_rule"], "recorded_at": now()}],
        }
        for source in original["sources"]:
            participant["sources"].append({
                "id": source["id"], "kind": source["kind"], "subject_key": original["account_id"],
                "platform": "小红书", "locator": source["url"], "title": source["title"],
                "text": source["excerpt"], "summary": source["summary"], "published_at": None,
                "date_display": source["date_display"], "collected_at": source["checked_at"],
                "usage_basis": "public_research", "instrument_version": "", "review_status": "checked",
                "review_method": "assisted", "reviewer": "公开来源核查", "review_note": "已核对账号与原文；不证明实际经历",
                "comment_id": source["comment_id"], "author_profile_url": source["author_profile_url"],
                "capture_scope": "excerpt_only",
            })
            # Each post remains its own context; proximity in time is not proof of one trip.
            participant["episodes"].append({
                "id": "E-" + source["id"], "title": source["title"], "source_ids": [source["id"]],
                "time_scope": "historical" if source["context"] == "post_trip" else "undated",
                "current_confirmed_at": None, "current_valid_until": None, "confirmation_quote": "",
            })
        for claim in original["claims"]:
            participant["facts"].append({"id": claim["id"], "text": claim["text"], "source_ids": claim["source_ids"],
                "representation": "checked_summary", "basis": "self_report", "review_method": "assisted"})
        for need in original["needs"]:
            fact_ids = [f["id"] for f in participant["facts"] if set(f["source_ids"]) & set(need["source_ids"])]
            if fact_ids:
                participant["insights"].append({"id": need["id"], "label": need["label"], "question": need["question"],
                    "fact_ids": fact_ids, "terms": need["terms"], "method": "assisted", "basis": "researcher_analysis"})
        participants.append(participant)
    return participants


def _load():
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if state.get("schema_version") != 1:
            raise ValueError("真人档案数据版本不受支持")
        return state
    archive = archive_legacy()
    state = {"schema_version": 1, "created_at": now(), "legacy_archive": archive,
             "participants": _seed_participants(), "predictions": []}
    _save(state)
    return state


def initialize():
    with LOCK:
        state = _load()
        changed = False
        for prediction in state["predictions"]:
            if prediction["status"] == "pending":
                prediction.update(status="failed", results={}, error="服务重启中断了模型请求，请重新运行。")
                changed = True
        if changed:
            _save(state)
        return state


def public_participant(participant):
    result = deepcopy(participant)
    result.pop("subject_key", None)
    result.pop("input_hash", None)
    for source in result["sources"]:
        source.pop("subject_key", None)
    result["eligibility_issues"] = eligibility(participant)
    return result


def listing():
    with LOCK:
        state = _load()
        return {"participants": [public_participant(p) for p in state["participants"]],
                "counts": {status: sum(p["status"] == status for p in state["participants"])
                           for status in ("accepted", "pending", "excluded")}}


def find(state, participant_id):
    participant = next((p for p in state["participants"] if p["id"] == participant_id), None)
    if participant is None:
        raise KeyError("真人档案不存在")
    return participant


def get(participant_id):
    with LOCK:
        return public_participant(find(_load(), participant_id))


def eligibility(participant):
    issues = []
    checked = [s for s in participant["sources"] if s["review_status"] == "checked"]
    checked_ids = {s["id"] for s in checked}
    supported = [f for f in participant["facts"] if set(f["source_ids"]) <= checked_ids]
    if len({f["text"].strip() for f in supported}) < 4:
        issues.append("需要至少四项来自已核查资料的具体旅行自述")
    if not participant["episodes"]:
        issues.append("需要可定位到来源的旅行情境")
    if not any(s["kind"] in {"questionnaire", "interview"} for s in checked):
        referenced = {sid for f in supported for sid in f["source_ids"]}
        own_notes = {canonical(s["locator"]) for s in checked if s["kind"] == "note" and s["id"] in referenced}
        if len(own_notes) < 2:
            issues.append("网络样本需要至少两篇不同的本人笔记参与事实支持")
        if not participant["profile_url"]:
            issues.append("网络样本需要可追溯的账号主页")
    return issues


def _imported(row: ParticipantInput, existing=None):
    source = row.model_dump(mode="json")
    facts = [{"id": f["id"], "text": f["quote"], "source_ids": [f["source_id"]],
              "representation": "verbatim", "basis": "self_report", "review_method": next(s.review_method for s in row.sources if s.id == f["source_id"])}
             for f in source.pop("facts")]
    for insight in source["insights"]:
        insight["basis"] = "researcher_analysis"
    return {**source, "id": existing["id"] if existing else subject_id(row.platform, row.subject_key),
            "facts": facts, "input_hash": digest(row.model_dump(mode="json")), "status": "pending",
            "identity_level": "account_traceable" if all(s.kind in {"comment", "note"} for s in row.sources) else "consented_response",
            "identity_evidence": "尚待审核", "revision": (existing["revision"] + 1 if existing else 1),
            "created_at": existing["created_at"] if existing else now(), "updated_at": now(),
            "evaluation_split": existing["evaluation_split"] if existing else None,
            "reviews": deepcopy(existing["reviews"]) if existing else [], "origin": "import"}


def import_records(records: list[ParticipantInput]):
    with LOCK:
        state = _load()
        identities = [(r.platform.casefold(), r.subject_key) for r in records]
        if len(set(identities)) != len(identities):
            raise ValueError("同一批次请合并同一受访者的资料后再导入")
        added, updated, duplicates, ids = 0, 0, 0, []
        for row in records:
            existing = next((p for p in state["participants"] if p["platform"].casefold() == row.platform.casefold() and p["subject_key"] == row.subject_key), None)
            if existing and existing.get("input_hash") == digest(row.model_dump(mode="json")):
                duplicates += 1
                ids.append(existing["id"])
                continue
            if existing and (existing["evaluation_split"] == "holdout" or existing["origin"] != "import"):
                raise ValueError("最终测试或已迁移的核查档案已冻结，不能用导入覆盖")
            # A known feedback record may not be relabeled as baseline evidence.
            feedbacks = [p["feedback"] for p in state["predictions"] if p.get("feedback") and existing and p["participant_id"] == existing["id"]]
            for s in row.sources:
                if any(canonical(s.locator) == canonical(f["evidence_source"]) or f["quote"] in s.text for f in feedbacks):
                    raise ValueError("本人反馈必须留在验证区，不能重新导入为预测资料")
            for other in state["participants"]:
                if existing and other["id"] == existing["id"]:
                    continue
                for s in row.sources:
                    if any(s.kind in {"questionnaire", "interview"} and s.kind == old["kind"] and
                           canonical(s.locator) == canonical(old["locator"]) for old in other["sources"]):
                        raise ValueError("该原始答卷/访谈记录已属于另一个受访者，请核对编号")
            participant = _imported(row, existing)
            if existing:
                state["participants"][state["participants"].index(existing)] = participant
                updated += 1
            else:
                state["participants"].append(participant)
                added += 1
            ids.append(participant["id"])
        if added or updated:
            _save(state)
        return {"added": added, "updated": updated, "duplicates": duplicates, "ids": ids}


def review(participant_id, request: ParticipantReview):
    with LOCK:
        state = _load()
        participant = find(state, participant_id)
        if participant["evaluation_split"] == "holdout":
            raise ValueError("最终测试档案已冻结，不能在测试中改变采纳条件")
        if request.status == "accepted":
            issues = eligibility(participant)
            if issues:
                raise ValueError("；".join(issues))
        if request.identity_level == "identity_verified" and len(request.identity_evidence.strip()) < 5:
            raise ValueError("身份已核验必须提供核验记录，账号连续性不能代替身份核验")
        has_consent = any(s["kind"] in {"questionnaire", "interview"} and s["usage_basis"] == "consented" for s in participant["sources"])
        if request.identity_level == "consented_response" and not has_consent:
            raise ValueError("本人授权回答需要问卷或访谈授权记录")
        participant.update(status=request.status, identity_level=request.identity_level,
                           identity_evidence=request.identity_evidence or request.note,
                           revision=participant["revision"] + 1, updated_at=now())
        participant["reviews"].append({**request.model_dump(), "recorded_at": now()})
        _save(state)
        return public_participant(participant)


def archive_view():
    with LOCK:
        state = _load()
        manifest = state["legacy_archive"]
        directory = ARCHIVE_DIR / manifest["archive_id"]
        data = {}
        for item in manifest["files"]:
            raw = (directory / item["file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("历史归档校验不一致")
            data[item["file"]] = json.loads(raw)
        research = data.get("research_state.json", {})
        return {"manifest": manifest, "personas": data.get("personas.json", []),
                "simulation_runs": research.get("simulation_runs", []), "trials": research.get("trials", []),
                "evidence_count": len(research.get("records", [])), "read_only": True}

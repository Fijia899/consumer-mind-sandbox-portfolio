"""Apply curated public evidence to existing personas and explain it in the workbench."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from research_schemas import ImportRequest, ReviewRequest
from schemas import Persona
from services import research_store as store

CORPUS_PATH = store.ROOT / "data/travel_evidence_zh.json"
BACKUP_DIR = store.ROOT / "data/persona_backups"
DEMOGRAPHICS = ["age", "gender", "city", "occupation", "income"]


def install_curated_evidence():
    """Only this versioned, source-checked collection is assisted-reviewed automatically."""
    bundle = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    imported = store.import_records(ImportRequest.model_validate({"records": bundle["records"]}).records)
    for row in store.dashboard()["records"]:
        if row["id"] not in imported["ids"]:
            continue
        fields = {key: row[key] for key in ("job_id", "stage", "perspective", "labels", "profile")}
        store.review(row["id"], ReviewRequest.model_validate({**fields, "status": "approved",
            "reviewer": "Codex 公开原文整理", "review_method": "assisted",
            "note": f"{bundle['edition']}：原页或公开索引已核对；标注为模型辅助，作者身份和实际经历未核实。"}))
    current = store.dashboard()["active_version"]
    if imported["added"] or not current:
        current = store.calibrate("中文旅游原文校准 · " + bundle["edition"])
    return current


def _party(text):
    groups = {"children": ("孩子", "幼儿", "宝宝", "亲子"), "parents": ("父母", "爸妈", "老人"),
              "couple": ("伴侣", "女朋友", "男朋友", "情侣", "对象", "老婆", "老公")}
    return {key for key, words in groups.items() if any(w in text for w in words)}


def compatible(persona, row):
    if row["job_id"] != persona["jtbd"]["job_id"]:
        return False
    story = " ".join(str(persona.get(k, "")) for k in ("family", "role", "subject"))
    story += json.dumps(persona.get("mindset", {}), ensure_ascii=False)
    source_story = row["text"] + " " + row["context"]
    left, right = _party(story), _party(source_story)
    party_sensitive = any(l["factor_id"] in {"B3", "B4", "B13"} for l in row["labels"]) or any(f["field"] in {"party_size", "party_description"} for f in row["profile"])
    if party_sensitive and left and right and not left.intersection(right):
        return False
    if any(w in source_story for w in ("日本", "跨境", "出境")) and not any(w in story for w in ("日本", "跨境", "出境", "签证", "语言")):
        return False
    return True


def adjust(personas, use_profile=True):
    version, rows = store.active_context()
    chinese = [r for r in rows if r["language"] == "zh" and r["perspective"] == "planning"]
    result = []
    for persona in personas:
        # Re-applying evidence starts from the original hypothesis, never nests snapshots.
        base = deepcopy(persona.research.get("base_persona") or persona.model_dump())
        base.pop("research", None)
        base["evidence_refs"] = ["synthetic", "hypothesis"]
        matches = [r for r in chinese if compatible(base, r)]
        old = {x["code"] for x in base["dominant_features"]}
        ranked = sorted(matches, key=lambda r: (-len(old.intersection(l["factor_id"] for l in r["labels"])), r["source_url"], r["text_hash"]))
        chosen = [ranked[0]["id"]] if ranked else []
        updated = store.ground_blueprints([base], record_ids=chosen, use_profile=use_profile)[0]
        metadata = updated["research"]
        metadata["evidence_only"] = True
        metadata["original_features"] = sorted(old)
        metadata["unsupported_fields"] = DEMOGRAPHICS + ["travel." + key for key in base["travel"] if "travel." + key not in metadata["field_sources"]]
        metadata["change_note"] = ("已用相近旅行情境的公开原文调整顾虑；未观察到的原假设保留在对照中。" if chosen
                                   else "尚未找到情境相近的中文调整资料，保留原画像假设，不能称为已验证。")
        result.append(Persona.model_validate(updated))
    return result


def optimize_existing():
    from services import persona_store
    if not persona_store.PERSONAS_PATH.exists():
        raise ValueError("请先生成旅游画像")
    original_bytes = persona_store.PERSONAS_PATH.read_bytes()
    existing = persona_store.get_personas()
    if not existing:
        raise ValueError("请先生成旅游画像")
    install_curated_evidence()
    updated = adjust(existing)
    # Preserve the user's exact current file before applying any runtime update.
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / (store.digest(original_bytes.hex())[:20] + ".json")
    if not backup.exists():
        backup.write_bytes(original_bytes)
    persona_store.set_personas(updated, reason="public_chinese_evidence_calibration")
    return {"personas": [p.model_dump() for p in updated], **audit(updated), "backup_created": True}


def _source_card(row):
    return {"id": row["id"], "platform": row["platform"], "url": row["source_url"], "quote": row["text"],
            "context": row["context"], "published_at": row["published_at"],
            "perspective": row["perspective"], "annotation_method": row.get("review_method", "unknown")}


def audit(personas=None):
    from services.persona_store import get_personas
    from services.travel_harness import load_factors
    personas = get_personas() if personas is None else personas
    with store.LOCK:
        state = store._load()
        active = store._active(state)
    approved = [r for r in state["records"] if r["status"] == "approved" and r["language"] == "zh"]
    by_id = {r["id"]: r for r in approved}
    factors = {f.id: f for f in load_factors()}
    reports = []
    for persona in personas:
        meta = persona.research
        current = bool(active and meta.get("version_id") == active["id"] and meta.get("signature") == active["signature"])
        used = [by_id[rid] for rid in meta.get("record_ids", []) if rid in by_id] if current else []
        base = meta.get("base_persona") or persona.model_dump()
        held = [r for r in approved if r["split"] == "holdout" and compatible(base, r)]
        supported = {l["factor_id"] for r in used for l in r["labels"] if l["basis"] == "explicit"}
        original = set(meta.get("original_features", [f.code for f in persona.dominant_features]))
        claims = []
        for fid in sorted(supported | original):
            if fid not in factors:
                continue
            supporting = [r for r in used if any(l["factor_id"] == fid and l["basis"] == "explicit" for l in r["labels"])]
            comparison = [r for r in held if any(l["factor_id"] == fid and l["basis"] == "explicit" for l in r["labels"])]
            claims.append({"factor_id": fid, "claim": factors[fid].name, "used_to_adjust": bool(supporting),
                           "status": "有原文支持" if supporting else "原假设，尚无匹配证据",
                           "additional_discussions": len({r["source_group"] for r in comparison}),
                           "sources": [_source_card(r) for r in supporting],
                           "comparisons": [_source_card(r) for r in comparison]})
        reports.append({"persona_id": persona.id, "applied": bool(used), "current": current,
                        "note": meta.get("change_note", "当前人物仍是合成假设，尚未用真实资料校准。"),
                        "claims": claims, "sources": [_source_card(r) for r in used],
                        "known_fields": meta.get("field_sources", {}) if used else {},
                        "unknown": "年龄、职业、收入与未注明来源的出行数值均未验证；名字是人物代号。",
                        "validation": "对照检查的是需求是否在其他公开讨论出现，不能证明此人物真实存在或能预测其预订。"})
    return {"reports": reports, "summary": {"personas": len(personas), "adjusted": sum(r["applied"] for r in reports),
             "chinese_records": len(approved), "discussions": len({r["source_group"] for r in approved}),
             "comparison_records": sum(r["split"] == "holdout" for r in approved),
             "unconfirmed_claims": sum(not c["used_to_adjust"] for r in reports for c in r["claims"]),
             "platforms": dict(Counter(r["platform"] for r in approved)),
             "ready": bool(active), "note": "公开自述，模型辅助整理；需求有证据不等于行为预测已验证。"}}

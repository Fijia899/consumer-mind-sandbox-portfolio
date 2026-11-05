"""Local, versioned research evidence; no network fetching or identity enrichment."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import unicodedata
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from research_schemas import EvidenceInput, ReviewRequest

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "data" / "research_state.json"
STARTER_PATH = ROOT / "data" / "research_starter.json"
LOCK = threading.RLock()
ENGINE_VERSION = "travel-evidence-1"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _load():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"salt": secrets.token_hex(32), "records": [], "versions": [], "active_version": None, "evaluations": [], "trials": []}


def _save(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATE_PATH)


def _normalize(text):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())


def _redact(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱已移除]", text)
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[电话已移除]", text)
    return re.sub(r"(?<!\w)@[\w.-]+", "[账号已移除]", text)


def _source(url):
    parts = urlsplit(str(url))
    if parts.username or parts.password:
        raise ValueError("来源链接不得包含账号或密码")
    path = parts.path.rstrip("/")
    # Reddit post/comment slugs do not identify a different discussion.
    match = re.match(r"(/r/[^/]+/comments/[^/]+)", path, re.I)
    if match:
        path = match[1]
    host = parts.netloc.lower()
    if host == "v2ex.com" or host.endswith(".v2ex.com"):
        host = "www.v2ex.com"
    # Some forums identify the discussion in the query, rather than the path.
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k in {"mod", "tid", "qid", "id"}))
    return urlunsplit((parts.scheme, host, path, query, ""))


def _group(state, platform, key):
    return hmac.new(bytes.fromhex(state["salt"]), f"{platform.casefold().strip()}:{key.casefold().strip()}".encode(), hashlib.sha256).hexdigest()


def _validate_annotation(row):
    from services.travel_harness import load_jobs, load_steps, load_factors
    jobs = {j.id: j for j in load_jobs()}
    stages = {s.stage for s in load_steps()}
    factors = {f.id for f in load_factors()}
    if row["job_id"] and row["job_id"] not in jobs:
        raise ValueError("任务编码不存在")
    if row["stage"] and row["stage"] not in stages:
        raise ValueError("旅行阶段不存在")
    if len({x["factor_id"] for x in row["labels"]}) != len(row["labels"]):
        raise ValueError("同一证据不能重复标注相同维度")
    for label in row["labels"]:
        if label["factor_id"] not in factors:
            raise ValueError("标注引用了不存在的维度")
        if label["quote"] not in row["text"]:
            raise ValueError("标注引文必须是原文片段")
        if any(len(t.strip()) < 2 or t.casefold() not in label["quote"].casefold() for t in label["terms"]):
            raise ValueError("检索词至少两个字符且必须出现在引文中")
    if len({x["field"] for x in row["profile"]}) != len(row["profile"]):
        raise ValueError("画像属性不能重复")
    bounds = {"trip_length_days": (1, 60), "party_size": (1, 30), "budget_per_person": (0, 500000)}
    for fact in row["profile"]:
        if fact["quote"] not in row["text"]:
            raise ValueError("画像属性必须有原文片段支持")
        field, value = fact["field"], fact["value"]
        if field in bounds and (type(value) is not int or not bounds[field][0] <= value <= bounds[field][1]):
            raise ValueError(f"{field} 必须是有效整数；不要换算未注明的币种或总预算")
        if field == "booked" and type(value) is not bool:
            raise ValueError("booked 必须为布尔值")
        if field in {"departure_window", "party_description"} and (not isinstance(value, str) or not 1 <= len(value) <= 200):
            raise ValueError("旅行描述必须是 1-200 字的文本")


def import_records(records: list[EvidenceInput]):
    with LOCK:
        state = _load()
        existing = {r["text_hash"] for r in state["records"]}
        added, duplicates = [], 0
        for item in records:
            row = item.model_dump(mode="json")
            author = row.pop("author_key")
            row["source_url"] = _source(row["source_url"])
            for field in ("text", "context", "platform"):
                row[field] = _redact(row[field])
            for label in row["labels"]:
                label["quote"] = _redact(label["quote"])
                label["terms"] = [_redact(t).strip() for t in label["terms"]]
            for fact in row["profile"]:
                fact["quote"] = _redact(fact["quote"])
                if isinstance(fact["value"], str):
                    fact["value"] = _redact(fact["value"])
            _validate_annotation(row)
            text_hash = digest(_normalize(row["text"]))
            if text_hash in existing:
                duplicates += 1
                continue
            group = _group(state, row["platform"], author or row["source_url"])
            if author and any(t["group"] == group for t in state["trials"]):
                raise ValueError("该作者已作为独立实验参与者登记，不能再导入为调整证据")
            source_group = _group(state, "source", row["source_url"])
            related = [r for r in state["records"] + added if r["group"] == group or r["source_group"] == source_group]
            splits = {r["split"] for r in related}
            if len(splits) > 1:
                raise ValueError("作者与来源关联到不同数据集，请合并重复来源后重新导入")
            split = next(iter(splits), "holdout" if int(group[:8], 16) % 5 == 0 else "train")
            row.update(id="E" + secrets.token_hex(6), text_hash=text_hash, group=group, source_group=source_group,
                       split=split, split_basis="author" if author else "source", status="pending",
                       imported_at=now(), reviewer="", review_note="", revision=1)
            added.append(row)
            existing.add(text_hash)
        state["records"].extend(added)
        if added:
            _save(state)
        return {"added": len(added), "duplicates": duplicates, "ids": [r["id"] for r in added]}


def review(record_id, body: ReviewRequest):
    with LOCK:
        state = _load()
        row = next((r for r in state["records"] if r["id"] == record_id), None)
        if row is None:
            raise KeyError("证据不存在")
        update = body.model_dump()
        update["review_note"] = _redact(update.pop("note"))
        update["reviewer"] = _redact(update["reviewer"])
        candidate = {**row, **update}
        # Review content goes through the same redaction path as import.
        for label in candidate["labels"]:
            label["quote"] = _redact(label["quote"])
            label["terms"] = [_redact(t).strip() for t in label["terms"]]
        for fact in candidate["profile"]:
            fact["quote"] = _redact(fact["quote"])
            if isinstance(fact["value"], str):
                fact["value"] = _redact(fact["value"])
        _validate_annotation(candidate)
        if body.status == "approved" and (not body.job_id or not body.stage or not body.labels):
            raise ValueError("审核通过前必须填写任务、阶段和维度标注")
        if body.status == "approved" and row["authenticity"] != "unverified":
            raise ValueError("疑似营销或虚假内容不能进入校准")
        row.update(candidate, reviewed_at=now(), revision=row["revision"] + 1)
        if any(record_id in v["record_ids"] for v in state["versions"] if v["id"] == state["active_version"]):
            state["active_version"] = None
        _save(state)
        return _public_row(row)


def _public_row(row):
    return {k: v for k, v in row.items() if k not in {"group", "source_group", "text_hash"}}


def delete_record(record_id):
    with LOCK:
        state = _load()
        if not any(r["id"] == record_id for r in state["records"]):
            raise KeyError("证据不存在")
        state["records"] = [r for r in state["records"] if r["id"] != record_id]
        # Remove derived snapshots and validation runs containing deleted material.
        invalid = {v["id"] for v in state["versions"] if record_id in v["record_ids"]}
        state["versions"] = [v for v in state["versions"] if v["id"] not in invalid]
        state["evaluations"] = [e for e in state["evaluations"] if e["version_id"] not in invalid and record_id not in e["record_ids"]]
        state["trials"] = [t for t in state["trials"] if t["version_id"] not in invalid]
        removed_runs = {r["id"] for r in state.get("simulation_runs", []) if any(
            record_id in p["persona"]["research"].get("record_ids", [])
            or p["persona"]["research"].get("version_id") in invalid for p in r["entries"])}
        state["simulation_runs"] = [r for r in state.get("simulation_runs", []) if r["id"] not in removed_runs]
        state["trials"] = [t for t in state["trials"] if t.get("run_id") not in removed_runs]
        if state["active_version"] in invalid:
            state["active_version"] = None
        _save(state)
        # Existing generated personas retain only IDs, never source excerpts.
        return {"deleted": record_id, "invalidated_versions": len(invalid)}


def signature():
    paths = [ROOT / "data" / n for n in ("factors.json", "jobs.json", "outcomes.json", "persona_seeds.json", "travel_evidence_zh.json")]
    paths += [Path(__file__), ROOT / "backend/services/travel_harness.py", ROOT / "backend/research_schemas.py", ROOT / "backend/schemas.py"]
    paths.append(ROOT / "backend/services/persona_evidence.py")
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def _eligible(row):
    return (row["status"] == "approved" and row["split"] == "train" and row["authenticity"] == "unverified"
            and any(l["basis"] == "explicit" for l in row["labels"]))


def calibrate(name):
    with LOCK:
        state = _load()
        rows = [r for r in state["records"] if _eligible(r)]
        if not rows:
            raise ValueError("需要至少一条审核通过的调整集证据")
        lexicon: dict[str, list[str]] = {}
        counts: dict[str, set] = {}
        for row in rows:
            for label in row["labels"]:
                if label["basis"] == "explicit":
                    lexicon.setdefault(label["factor_id"], []).extend(label["terms"])
                    counts.setdefault(label["factor_id"], set()).add(row["group"])
        version = {"id": "V" + secrets.token_hex(6), "name": name, "created_at": now(),
                   "signature": signature(), "engine": ENGINE_VERSION, "record_ids": [r["id"] for r in rows],
                   "revisions": {r["id"]: r["revision"] for r in rows},
                   "lexicon": {k: sorted(set(v)) for k, v in lexicon.items()},
                   "factor_author_counts": {k: len(v) for k, v in counts.items()},
                   "unique_groups": len({r["group"] for r in rows}),
                   "platforms": dict(Counter(r["platform"] for r in rows)),
                   "annotation_methods": dict(Counter(r.get("review_method", "human") for r in rows))}
        state["versions"].append(version)
        state["active_version"] = version["id"]
        _save(state)
        return version


def _active(state):
    version = next((v for v in state["versions"] if v["id"] == state["active_version"]), None)
    if version and version["signature"] != signature():
        return None
    return version


def active_context():
    with LOCK:
        state = _load()
        version = _active(state)
        if not version:
            raise ValueError("没有有效校准版本，请先在研究校准页审核证据并创建版本")
        return deepcopy(version), deepcopy([r for r in state["records"] if r["id"] in version["record_ids"]])


def ground_blueprints(blueprints, use_profile=True, record_ids=None):
    """One traceable planning record per slot; no inferred attributes or holdout text."""
    from services.travel_harness import load_factors, load_jobs, load_steps
    version, rows = active_context()
    factors = {f.id: f for f in load_factors(True)}
    jobs = {j.id: j for j in load_jobs()}
    steps = {s.id: s for s in load_steps()}
    result = deepcopy(blueprints)
    for index, bp in enumerate(result):
        candidates = [r for r in rows if r["job_id"] == bp["jtbd"]["job_id"] and r["perspective"] == "planning"
                      and any(steps[s].stage == r["stage"] for s in jobs[r["job_id"]].step_ids)
                      and any(l["basis"] == "explicit" and l["factor_id"] in factors for l in r["labels"])]
        if record_ids is not None:
            candidates = [r for r in candidates if r["id"] in record_ids]
        base = deepcopy(bp)
        bp["research"] = {"version_id": version["id"], "signature": version["signature"], "record_ids": [],
                          "field_sources": {}, "base_persona": base, "profile_enabled": use_profile,
                          "note": "无匹配证据，保留合成假设；人物姓名、年龄、职业等均为合成细节。"}
        if not candidates:
            continue
        row = candidates[index % len(candidates)]
        ids = list(dict.fromkeys(l["factor_id"] for l in row["labels"] if l["basis"] == "explicit" and l["factor_id"] in factors))
        bp["factor_weights"] = {f: (8 if f in ids else 0) for f in factors}
        bp["dominant_features"] = [{"code": f, "weight": 8} for f in ids]
        bp["jtbd"]["forces"] = {key: [f for f in ids if factors[f].force_default == key]
                                   for key in ("push", "pull", "anxiety", "habit_or_alternative")}
        bp["blockers"] = [factors[f].name for f in ids if factors[f].force_default == "anxiety"]
        bp["drivers"] = [factors[f].name for f in ids if factors[f].force_default != "anxiety"]
        bp["mindset"]["fear"] = "；".join(bp["blockers"]) or "尚未观察到明确顾虑"
        bp["mindset"]["core_motive"] = bp["jtbd"]["core_job"]
        bp["mindset"]["decision_logic"] = "合成决策规则：优先核对" + "、".join(factors[f].name for f in ids)
        bp["mindset"]["quote"] = "合成表达：这次旅行，我想先确认" + "、".join(factors[f].name for f in ids)
        job = jobs[row["job_id"]]
        bp["jtbd"]["current_step"] = next(steps[s].name for s in job.step_ids if steps[s].stage == row["stage"])
        bp["travel"]["stage"] = row["stage"]
        for outcome in bp["jtbd"]["desired_outcomes"]:
            outcome["importance"] = 9 if any(outcome["id"] in factors[f].outcome_ids for f in ids) else 5
        fields = {"dominant_features": row["id"], "jtbd.forces": row["id"], "travel.stage": row["id"]}
        if use_profile:
            for fact in row["profile"]:
                if fact["basis"] != "self_report":
                    continue
                if fact["field"] == "party_description":
                    bp["family"] = fact["value"]
                    fields["family"] = row["id"]
                else:
                    bp["travel"][fact["field"]] = fact["value"]
                    fields["travel." + fact["field"]] = row["id"]
        bp["evidence_refs"] += [row["id"], version["id"]]
        bp["research"].update(record_ids=[row["id"]], field_sources=fields,
                              note="依据已审核的公开自述校准；未列明来源的属性仍是合成假设，非真人复制。")
    return result


def predict_labels(text, version=None):
    from services.travel_harness import load_factors
    folded = text.casefold()
    lexicon = version["lexicon"] if version else {}
    return {f.id for f in load_factors(True) if any(term.casefold() in folded for term in f.keywords + lexicon.get(f.id, []) if term)}


def _metrics(pairs):
    tp = sum(len(expected & actual) for expected, actual in pairs)
    fp = sum(len(actual - expected) for expected, actual in pairs)
    fn = sum(len(expected - actual) for expected, actual in pairs)
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {"n": len(pairs), "precision": precision, "recall": recall,
            "micro_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            "exact_match": sum(a == b for a, b in pairs) / len(pairs) if pairs else None,
            "tp": tp, "fp": fp, "fn": fn}


def evaluate():
    with LOCK:
        state = _load()
        version = _active(state)
        if not version:
            raise ValueError("请先创建有效校准版本")
        rows = [r for r in state["records"] if r["split"] == "holdout" and r["status"] == "approved"
                and any(l["basis"] == "explicit" for l in r["labels"])]
        if not rows:
            raise ValueError("尚无已审核的留出集；请继续导入不同作者/来源的资料，不能拿调整集充当验证")
        train = [r for r in state["records"] if r["id"] in version["record_ids"]]
        if {r["group"] for r in train} & {r["group"] for r in rows} or {r["source_group"] for r in train} & {r["source_group"] for r in rows}:
            raise ValueError("发现作者或来源泄漏，请重新整理数据")
        details, base_pairs, calibrated_pairs = [], [], []
        for row in rows:
            expected = {l["factor_id"] for l in row["labels"] if l["basis"] == "explicit"}
            base = predict_labels(row["text"])
            calibrated = predict_labels(row["text"], version)
            base_pairs.append((expected, base))
            calibrated_pairs.append((expected, calibrated))
            details.append({"id": row["id"], "expected": sorted(expected), "baseline": sorted(base), "calibrated": sorted(calibrated),
                            "missed": sorted(expected - calibrated), "extra": sorted(calibrated - expected)})
        report = {"id": "R" + secrets.token_hex(6), "created_at": now(), "version_id": version["id"],
                  "signature": version["signature"], "record_ids": [r["id"] for r in rows],
                  "holdout_revisions": {r["id"]: r["revision"] for r in rows},
                  "baseline": _metrics(base_pairs), "calibrated": _metrics(calibrated_pairs), "details": details,
                  "unique_groups": len({r["group"] for r in rows}), "platforms": dict(Counter(r["platform"] for r in rows)),
                  "split_basis": dict(Counter(r["split_basis"] for r in rows)),
                  "annotation_methods": dict(Counter(r.get("review_method", "human") for r in rows)),
                  "run_number": 1 + sum(e["version_id"] == version["id"] for e in state["evaluations"]),
                  "scope": "仅衡量评论中决策维度的识别；不代表画像真实性、人群比例或预订预测准确率。反复查看留出结果后调参，会使其成为开发集，需另收新资料。"}
        state["evaluations"].append(report)
        _save(state)
        return report


def create_trial(persona, campaign, participant_key, platform):
    from schemas import Persona
    from services.travel_harness import identify_factors, load_factors, load_outcomes, simulate_persona
    with LOCK:
        state = _load()
        group = _group(state, platform, participant_key)
        if any(r["group"] == group for r in state["records"]):
            raise ValueError("该参与者已在评论证据库中，请选择新的独立参与者")
        research = persona.research
        version_id = research.get("version_id")
        version = _active(state)
        if version_id and (not version or version_id != version["id"]):
            raise ValueError("画像校准版本已失效，请重新生成后再登记实验")
        factors, outcomes = load_factors(), load_outcomes()
        hits = identify_factors(campaign, factors)
        base = Persona.model_validate(research["base_persona"]) if research.get("base_persona") else persona
        variants = {"baseline": base, "comments": persona.model_copy(deep=True), "comments_profile": persona}
        # Derive comments-only variant using the frozen base and the same evidence record.
        if version_id:
            grounded = ground_blueprints([base.model_dump()], use_profile=False, record_ids=research.get("record_ids", []))[0]
            if grounded["research"]["record_ids"] != research.get("record_ids"):
                raise ValueError("无法复现该画像的证据，请按同一任务单独重新生成")
            variants["comments"] = Persona.model_validate(grounded)
            variants["comments_profile"] = Persona.model_validate(ground_blueprints([base.model_dump()], use_profile=True, record_ids=research.get("record_ids", []))[0])
        predictions = {key: simulate_persona(p, campaign, factors, outcomes, hits).decision for key, p in variants.items()}
        trial = {"id": "T" + secrets.token_hex(6), "created_at": now(), "persona_id": persona.id,
                 "campaign": _redact(campaign), "group": group, "version_id": version_id,
                 "signature": signature(), "predictions": predictions, "observation": None,
                 "objective": "真人对原方案是否愿意进一步了解的自述；不衡量实际预订"}
        state["trials"].append(trial)
        _save(state)
        return {k: v for k, v in trial.items() if k != "group"}


def _redact_tree(value):
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, dict):
        return {k: _redact_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_tree(v) for v in value]
    return value


def save_simulation_run(campaign, personas, results):
    """Freeze the actual displayed output, including LLM text, without re-running it."""
    by_id = {p.id: p for p in personas}
    with LOCK:
        state = _load()
        run = {"id": "R" + secrets.token_hex(8), "created_at": now(),
               "signature": signature(), "campaign": _redact(campaign),
               "entries": [_redact_tree({"persona": by_id[r.persona_id].model_dump(mode="json"),
                                           "result": r.model_dump(mode="json")}) for r in results]}
        state.setdefault("simulation_runs", []).append(run)
        _save(state)
        return run["id"]


def create_run_trial(run_id, body):
    with LOCK:
        state = _load()
        run = next((r for r in state.get("simulation_runs", []) if r["id"] == run_id), None)
        if not run:
            raise KeyError("测试记录不存在，请重新运行话术测试")
        entry = next((e for e in run["entries"] if e["persona"]["id"] == body.persona_id), None)
        if not entry:
            raise ValueError("该画像不属于这次话术测试")
        group = _group(state, body.platform, body.participant_key)
        if any(r["group"] == group for r in state["records"]):
            raise ValueError("该参与者已在评论证据库中，请选择新的独立参与者")
        if any(t.get("run_id") == run_id and t["group"] == group for t in state["trials"]):
            raise ValueError("同一参与者在本次话术测试中已登记，请勿重复计数")
        trial = {"id": "T" + secrets.token_hex(6), "kind": "campaign_feedback", "run_id": run_id,
                 "created_at": now(), "predicted_at": run["created_at"], "persona_id": body.persona_id,
                 "campaign": run["campaign"], "group": group,
                 "version_id": entry["persona"]["research"].get("version_id"),
                 "signature": run["signature"], "mode": entry["result"]["mode"],
                 "snapshot": deepcopy(entry), "platform": _redact(body.platform), "context": _redact(body.context),
                 "predictions": {"displayed": entry["result"]["decision"]}, "observation": None,
                 "objective": "独立旅游意向参与者对同一方案的自述意向对照；不衡量预订转化"}
        state["trials"].append(trial)
        _save(state)
        return _public_trial(trial)


def _public_trial(trial):
    result = {k: v for k, v in trial.items() if k != "group"}
    if trial.get("kind") == "campaign_feedback":
        observation = trial["observation"]
        result["verification"] = ("pending" if not observation else
                                  "consistent" if trial["predictions"]["displayed"] == observation["decision"] else "different")
    return result


def observe(trial_id, body):
    with LOCK:
        state = _load()
        trial = next((t for t in state["trials"] if t["id"] == trial_id), None)
        if not trial:
            raise KeyError("实验不存在")
        if trial["observation"]:
            raise ValueError("真人结果已登记，不能覆盖；请另建实验")
        if trial.get("kind") == "campaign_feedback" and len(body.evidence_source.strip()) < 5:
            raise ValueError("请填写可回查的证据出处，如访谈记录编号或授权记录位置")
        trial["observation"] = {**_redact_tree(body.model_dump()), "recorded_at": now()}
        _save(state)
        return _public_trial(trial)


def dashboard():
    with LOCK:
        state = _load()
        active = _active(state)
        completed = [t for t in state["trials"] if t["observation"]]
        trial_metrics = {}
        def trial_version(t):
            suffix = " · 当次反馈 · " + t["mode"] if t.get("kind") == "campaign_feedback" else ""
            return (t["version_id"] or "uncalibrated") + " · " + t["signature"][:8] + suffix
        for version_id in sorted({trial_version(t) for t in completed}):
            subset = [t for t in completed if trial_version(t) == version_id]
            trial_metrics[version_id] = {"n": len(subset), "unique_participants": len({t["group"] for t in subset}),
                "agreement": {k: sum(t["predictions"][k] == t["observation"]["decision"] for t in subset) / len(subset)
                              for k in subset[0]["predictions"]}}
        revisions = {r["id"]: r["revision"] for r in state["records"]}
        current_signature = signature()
        evaluations = [{**e, "stale": e["signature"] != current_signature or any(revisions.get(rid) != rev for rid, rev in e["holdout_revisions"].items())}
                       for e in state["evaluations"]]
        return {"records": [_public_row(r) for r in state["records"]], "active_version": active,
                "versions": state["versions"], "evaluations": evaluations,
                "trials": [_public_trial(t) for t in state["trials"]],
                "trial_metrics": trial_metrics,
                "counts": dict(Counter(r["status"] for r in state["records"])),
                "limits": "评论作者身份与真实性未核实；来源集中、主动发言偏差和时间差仍存在。样本频次不是市场占比。"}

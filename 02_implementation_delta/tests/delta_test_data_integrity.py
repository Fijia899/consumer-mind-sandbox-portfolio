import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

VALID_FORCES = {"push", "pull", "anxiety", "habit_or_alternative"}


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_jobs_ontology_is_consistent():
    raw = _load("jobs.json")
    jobs = raw["jobs"]
    sub_jobs = raw["sub_jobs"]

    job_ids = [j["id"] for j in jobs]
    assert len(job_ids) == len(set(job_ids)), "Job id 必须唯一"
    assert len(jobs) >= 5, "至少要有 5 个主 Job"

    sub_ids = [s["id"] for s in sub_jobs]
    assert len(sub_ids) == len(set(sub_ids)), "Sub-Job id 必须唯一"

    for j in jobs:
        for sid in j["step_ids"]:
            assert sid in sub_ids, f"Job {j['id']} 的 step {sid} 不存在"
        for oid in j["outcome_ids"]:
            assert oid in {
                o["id"] for o in _load("outcomes.json")["outcomes"]
            }, f"Job {j['id']} 引用了不存在的 Outcome {oid}"

    for s in sub_jobs:
        assert s["stage"] in raw["stages"], f"Sub-Job {s['id']} 的阶段不存在"
        for jid in s["job_ids"]:
            assert jid in job_ids, f"Sub-Job {s['id']} 引用不存在的 Job {jid}"


def test_outcomes_reference_real_factors():
    factor_ids = {f["id"] for f in _load("factors.json")["factors"]}
    outcomes = _load("outcomes.json")["outcomes"]

    oids = [o["id"] for o in outcomes]
    assert len(oids) == len(set(oids)), "Outcome id 必须唯一"
    assert len(outcomes) >= 5

    for o in outcomes:
        for fid in o.get("factor_ids", []):
            assert fid in factor_ids, f"Outcome {o['id']} 引用了不存在的 Factor {fid}"


def test_factors_reference_jobs_and_outcomes():
    jobs = _load("jobs.json")
    outcomes = _load("outcomes.json")
    job_ids = {j["id"] for j in jobs["jobs"]}
    outcome_ids = {o["id"] for o in outcomes["outcomes"]}

    factors = _load("factors.json")["factors"]
    fids = [f["id"] for f in factors]
    assert len(fids) == len(set(fids)), "Factor id 必须唯一"
    assert len(factors) >= 20, "至少要有 20 条决策维度"

    for f in factors:
        assert f["weight"] >= 1 and f["weight"] <= 10
        assert f["force_default"] in VALID_FORCES
        for jid in f.get("job_ids", []):
            assert jid in job_ids, f"Factor {f['id']} 引用不存在的 Job {jid}"
        for oid in f.get("outcome_ids", []):
            assert oid in outcome_ids, f"Factor {f['id']} 引用了不存在的 Outcome {oid}"
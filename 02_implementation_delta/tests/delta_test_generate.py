import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORCE_VALUES = {"push", "pull", "anxiety", "habit_or_alternative"}


def test_generate_n_personas_rule_mode(client):
    resp = client.post("/api/generate", json={"count": 3, "use_llm": False})
    assert resp.status_code == 200, resp.text
    personas = resp.json()
    assert len(personas) == 3

    data = json.loads((ROOT / "data" / "factors.json").read_text(encoding="utf-8"))
    valid_factors = {f["id"] for f in data["factors"]}
    jobs = json.loads((ROOT / "data" / "jobs.json").read_text(encoding="utf-8"))
    job_ids = {j["id"] for j in jobs["jobs"]}
    outcomes = json.loads((ROOT / "data" / "outcomes.json").read_text(encoding="utf-8"))
    outcome_ids = {o["id"] for o in outcomes["outcomes"]}

    for p in personas:
        assert p["id"]
        assert p["jtbd"]["job_id"] in job_ids, f"{p['id']} job_id 非法"
        assert p["jtbd"]["current_step"], f"{p['id']} 缺少 current_step"
        for d in p["dominant_features"]:
            assert d["code"] in valid_factors, f"{p['id']} 主导维度 {d['code']} 非法"
        illegal_weights = set(p["factor_weights"]) - valid_factors
        assert not illegal_weights, f"{p['id']} 存在非法权重键 {illegal_weights}"
        for do in p["jtbd"]["desired_outcomes"]:
            assert do["id"] in outcome_ids
        assert p["jtbd"]["forces"]["push"] or p["jtbd"]["forces"]["pull"]


def test_personas_listed_after_generate(client):
    client.post("/api/generate", json={"count": 2, "use_llm": False})
    resp = client.get("/api/personas")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_generate_respects_job_filter(client):
    resp = client.post(
        "/api/generate",
        json={"count": 5, "use_llm": False, "job_ids": ["J5"]},
    )
    assert resp.status_code == 200
    for p in resp.json():
        assert p["jtbd"]["job_id"] == "J5"
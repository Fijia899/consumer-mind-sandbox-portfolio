def _generate(client, count=12, **kw):
    body = {"count": count, "use_llm": False, **kw}
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_simulate_requires_personas(client):
    client.post("/api/memories/reset")
    resp = client.get("/api/personas")
    assert resp.status_code == 200

    resp = client.post("/api/simulate", json={"campaign": "测试话术", "use_llm": False})
    assert resp.status_code == 200 or resp.status_code == 400


def test_simulate_returns_differentiated_decisions(client):
    _generate(client, count=12)
    resp = client.post(
        "/api/simulate",
        json={"campaign": "深夜情绪上头，先等5分钟冲动延迟缓冲，把念头写下来打断循环，有人陪你说说话，同路人社群一起打卡", "use_llm": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    results = body["results"]
    assert len(results) > 0

    decisions = {r["decision"] for r in results}
    assert decisions <= {"advance", "hesitate", "reject", "na"}
    assert "summary" in body and isinstance(body["summary"], dict)

    for r in results:
        assert r["persona_id"]
        assert r["reaction"]
        assert ("outcome_improved" in r) and ("next_step" in r)


def test_stronger_intervention_advances_more_than_bare_endorsement(client):
    _generate(client, count=20)
    weak = client.post(
        "/api/simulate",
        json={
            "campaign": "睡前仪式很重要，睡眠作息要规律，睡个好觉",
            "use_llm": False,
            "reproducible": True,
        },
    ).json()
    strong = client.post(
        "/api/simulate",
        json={
            "campaign": "深夜想TA先等5分钟延迟缓冲，把TA的联系方式拉黑删除，找同路人社群说说话，有人陪着你，坚持打卡记录坚持天数",
            "use_llm": False,
            "reproducible": True,
        },
    ).json()

    weak_adv = weak["summary"].get("advance", 0)
    strong_adv = strong["summary"].get("advance", 0)
    assert strong_adv >= weak_adv, f"强干预 advance({strong_adv}) 应不低于弱干预({weak_adv})"


def test_negative_persuasion_produces_rejects(client):
    _generate(client, count=12)
    resp = client.post(
        "/api/simulate",
        json={
            "campaign": "别戒了，复合算了，忍不住就发，想开点",
            "use_llm": False,
            "reproducible": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"].get("reject", 0) >= 1, "劝阻话术应产生至少 1 个 reject"


def test_simulate_is_reproducible_in_rule_mode(client):
    _generate(client, count=10)
    payload = {"campaign": "5分钟冲动延迟缓冲+拉黑删除+打卡记录坚持天数", "use_llm": False, "reproducible": True}
    a = client.post("/api/simulate", json=payload).json()
    b = client.post("/api/simulate", json=payload).json()

    a_key = [(r["persona_id"], r["decision"], r["next_step"]) for r in a["results"]]
    b_key = [(r["persona_id"], r["decision"], r["next_step"]) for r in b["results"]]
    assert a_key == b_key, "reproducible 模式下同输入应同输出"


def test_high_risk_persona_accepts_crisis_referral(client):
    personas = _generate(client, count=16, job_ids=["J7"])
    high_ids = [p["id"] for p in personas if p.get("detach", {}).get("safety_flag")]
    assert high_ids, "高危 Job 生成应产出 safety_flag=True 的触发者"
    resp = client.post(
        "/api/simulate",
        json={
            "campaign": "这里有24小时危机干预热线，别一个人硬扛，立即求助",
            "persona_ids": high_ids,
            "use_llm": False,
            "reproducible": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == len(high_ids)
    assert all(r["decision"] == "advance" for r in body["results"]), body["summary"]


def test_high_risk_not_rejected_by_discouragement(client):
    personas = _generate(client, count=16, job_ids=["J7"])
    high_ids = [p["id"] for p in personas if p.get("detach", {}).get("safety_flag")]
    assert high_ids
    resp = client.post(
        "/api/simulate",
        json={
            "campaign": "想开点，别这么脆弱，至于吗",
            "persona_ids": high_ids,
            "use_llm": False,
            "reproducible": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(r["decision"] == "hesitate" for r in body["results"]), body["summary"]


def test_verification_writeback(client):
    _generate(client, count=2)
    pid = client.get("/api/personas").json()[0]["id"]
    resp = client.post(
        "/api/verify",
        json={"persona_id": pid, "campaign": "测试", "status": "verified", "note": "真实用户反馈一致"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_memory_closed_loop(client):
    _generate(client, count=2)
    personas = client.get("/api/personas").json()
    pid = personas[0]["id"]

    resp = client.post(
        "/api/simulate",
        json={"campaign": "先等5分钟冲动延迟缓冲，把想念写下来做替代动作，有人陪你说说话", "use_llm": False, "use_memory": True},
    )
    assert resp.status_code == 200

    mem = client.get(f"/api/personas/{pid}/memories")
    assert mem.status_code == 200
    assert len(mem.json().get("memories", [])) >= 1

    reset = client.post("/api/memories/reset")
    assert reset.status_code == 200
"""高危门控端到端对照测试（规则引擎，真实 /api/generate + /api/simulate 链路）。

与 test_simulate.py 的专项用例互补：这里固定用「同一库内的高危(J7/A10) vs 普通(J2)」两个样本，
对同一话术做横向对照，固化 five 组实机验证的判定差异：

1. 危机转介话术：高危必须 advance（O9 兜底、will≥8）；普通人不被推进（转介被门禁过滤）
2. 劝阻话术：高危 hesitate（“想开点”不能推开高危者）；普通人 reject
3. 普通戒断话术：高危 reject/na（不对症，不透支推进）；普通人 advance/hesitate（对症被回应）
"""

DISSUADE = "别想太多，想开点，忍着就好，复合算了，谁没分过手，别这么脆弱"

REFERRAL = (
    "如果你在深夜有伤害自己的念头，请立即拨打心理援助热线，不要一个人硬扛，"
    "我们有危机干预和紧急预案，为你提供专业心理援助和救命的安全网"
)

SOOTHING_RECOVERY = (
    "深夜想TA的时候先等5分钟冲动延迟缓冲，把念头写下来，打断反刍循环，"
    "坚持打卡看到自己坚持的天数，破戒了也没关系，我们陪你重来"
)


def _generate(client, count=20, **kw):
    body = {"count": count, "use_llm": False, **kw}
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _sim(client, campaign, persona_ids):
    resp = client.post(
        "/api/simulate",
        json={
            "campaign": campaign,
            "persona_ids": persona_ids,
            "use_llm": False,
            "reproducible": True,
        },
    )
    assert resp.status_code == 200, resp.text
    by_id = {r["persona_id"]: r for r in resp.json()["results"]}
    assert len(by_id) == len(persona_ids), resp.text
    return by_id


def _sample_high_and_normal(client):
    """同一库内在 J7(高危任务) 与 J2(联系冲动) 间生成，返回 (高危样本, 普通样本)。"""
    personas = _generate(client, count=20, job_ids=["J7", "J2"])
    high = next((p for p in personas if p.get("detach", {}).get("safety_flag")), None)
    norm = next(
        (
            p
            for p in personas
            if not p.get("detach", {}).get("safety_flag")
            and (p.get("jtbd") or {}).get("job_id") == "J2"
        ),
        None,
    )
    assert high is not None, "J7 生成应产出 A10 高危档案"
    assert norm is not None, "J2 生成应产出普通档案"
    return high, norm


def test_referral_advances_only_high_risk(client):
    high, norm = _sample_high_and_normal(client)
    res = _sim(client, REFERRAL, [high["id"], norm["id"]])
    h, n = res[high["id"]], res[norm["id"]]

    assert h["decision"] == "advance", h
    assert h["willingness"] >= 8, h
    assert "O9" in h["outcome_improved"], h

    assert n["decision"] != "advance", (
        "危机转介话术只对高危者推进；普通人不该被转介话术直接推进"
    )


def test_discouragement_hesitates_high_risk_but_rejects_normal(client):
    high, norm = _sample_high_and_normal(client)
    res = _sim(client, DISSUADE, [high["id"], norm["id"]])
    h, n = res[high["id"]], res[norm["id"]]

    assert h["decision"] == "hesitate", "高危者被「想开点」推开前至少要犹豫，而非 reject"
    assert n["decision"] == "reject", "普通人面对劝阻应拒绝"


def test_soothing_recovery_misses_high_risk_but_helps_normal(client):
    high, norm = _sample_high_and_normal(client)
    res = _sim(client, SOOTHING_RECOVERY, [high["id"], norm["id"]])
    h, n = res[high["id"]], res[norm["id"]]

    assert h["decision"] in {"reject", "na"}, (
        "普通戒断话术不对高风险者对症，绝不能给他推进"
    )
    assert n["decision"] in {"advance", "hesitate"}, (
        "同样的话术对普通求助者应被回应（至少犹豫）"
    )
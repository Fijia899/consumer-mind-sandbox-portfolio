import json

import pytest

from schemas import Persona
from services import travel_harness as harness


def rule(index, campaign, factors=None):
    factors = factors if factors is not None else harness.load_factors()
    persona = Persona.model_validate(harness._blueprints(7)[index])
    return harness.simulate_persona(persona, campaign, factors, harness.load_outcomes(), harness.identify_factors(campaign, factors))


def test_positive_double_negation_does_not_reject():
    result = rule(2, "人均总价透明，无隐藏费用，不另收费，支持免费改期。")
    assert result.decision == "advance"
    assert "O6" in result.outcome_improved
    assert "budget_clarity" in result.interventions


def test_unrelated_limitation_does_not_reject_every_persona():
    campaign = "提供近期真实评价；不支持退改。"
    assert rule(0, campaign).decision != "reject"
    result = rule(5, campaign)
    assert result.decision == "reject"
    assert not result.outcome_improved
    assert not result.interventions


def test_negative_offer_is_not_presented_as_support():
    result = rule(5, "不支持免费改期，也不提供当地客服。")
    assert result.decision == "reject"
    assert not result.outcome_improved
    assert not harness.detect_interventions("不支持免费改期，也不提供当地客服。", harness.load_factors())


def test_disabled_dimensions_cannot_drive_results():
    factors = [f.model_copy(update={"enabled": False}) for f in harness.load_factors()]
    assert not harness.identify_factors("费用透明，免费改期，提供当地客服", factors)
    assert rule(5, "费用透明，免费改期，提供当地客服", factors).decision == "na"


def test_mentions_of_concerns_do_not_count_as_resolved():
    campaign = "担心预算超支和退改规则"
    result = rule(2, campaign)
    assert result.decision == "hesitate"
    assert not result.outcome_improved
    assert not result.interventions
    assert not harness.detect_interventions(campaign, harness.load_factors())


def test_random_blueprints_pass_structural_checks():
    for bp in harness._blueprints(21, randomize=True, random_seed=7):
        persona = Persona.model_validate(bp)
        assert not harness._validate(persona, harness.load_factors(), harness.load_jobs(), harness.load_steps(), harness.load_outcomes(), bp, set())


@pytest.mark.parametrize("mismatch", ["role", "stage", "weight", "outcome"])
def test_generation_qc_rejects_inconsistent_profiles(mismatch):
    bp = harness._blueprints(1)[0]
    persona = Persona.model_validate(bp)
    if mismatch == "role":
        persona.role = "另一个角色"
    elif mismatch == "stage":
        persona.travel.stage = "旅程回顾"
    elif mismatch == "weight":
        persona.factor_weights[persona.dominant_features[0].code] = 0
    else:
        persona.jtbd.desired_outcomes.append(persona.jtbd.desired_outcomes[0])
    assert harness._validate(persona, harness.load_factors(), harness.load_jobs(), harness.load_steps(), harness.load_outcomes(), bp, set())




@pytest.mark.parametrize("invalid", ["not json", '{"name":"缺少字段"}'])
def test_llm_generation_recovers_from_parse_or_schema_error(monkeypatch, invalid):
    bp = harness._blueprints(1)[0]
    responses = iter([invalid, json.dumps(bp, ensure_ascii=False)])
    prompts = []
    monkeypatch.setattr(harness, "_client", lambda: object())
    def complete(client, prompt, **kwargs):
        prompts.append(prompt)
        return next(responses)
    monkeypatch.setattr(harness, "_complete", complete)
    assert len(harness.generate_personas(1, use_llm=True)) == 1
    assert len(prompts) == 2
    assert "结构上下文" in prompts[1]


def test_llm_cannot_upgrade_hesitation_or_hide_missing_outcomes(monkeypatch):
    persona = Persona.model_validate(harness._blueprints(1)[0])
    factors = harness.load_factors()
    campaign = "周末放松安排"
    baseline = harness._rule_result(persona, campaign, factors, harness.load_outcomes(), harness.identify_factors(campaign, factors))
    assert baseline.decision == "hesitate"
    monkeypatch.setattr(harness, "_client", lambda: object())
    monkeypatch.setattr(harness, "_complete", lambda *args, **kwargs: json.dumps({
        "decision": "advance", "willingness": 10, "reaction": "立刻预订",
        "outcome_improved": [], "unresolved_outcomes": [], "next_step": "未知步骤",
    }))
    result = harness.simulate_persona(persona, campaign, factors, harness.load_outcomes(), harness.identify_factors(campaign, factors), use_llm=True)
    assert result.decision == "hesitate"
    assert result.willingness <= 5
    assert result.reaction == baseline.reaction
    assert set(result.unresolved_outcomes) == {x.id for x in persona.jtbd.desired_outcomes}
    assert result.next_step == persona.jtbd.current_step

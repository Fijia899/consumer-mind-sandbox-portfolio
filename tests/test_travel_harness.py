import json

from services import travel_harness


def test_llm_generation_retries_after_structural_qc(monkeypatch):
    blueprint = travel_harness._blueprints(1)[0]
    invalid = json.loads(json.dumps(blueprint, ensure_ascii=False))
    invalid["dominant_features"][0]["code"] = "UNKNOWN"
    prompts = []
    responses = iter((invalid, blueprint))

    monkeypatch.setattr(travel_harness, "_client", lambda: object())
    monkeypatch.setattr(
        travel_harness,
        "_complete",
        lambda client, prompt, **kwargs: (prompts.append(prompt), json.dumps(next(responses), ensure_ascii=False))[1],
    )

    personas = travel_harness.generate_personas(1, use_llm=True)
    assert len(personas) == 1
    assert len(prompts) == 2
    assert "旅游意向人群" in prompts[0]
    assert "质检问题" in prompts[1]
    assert personas[0].jtbd.job_id == blueprint["jtbd"]["job_id"]


def test_llm_generation_falls_back_to_valid_blueprint_after_content_qc(monkeypatch):
    blueprint = travel_harness._blueprints(1)[0]
    invalid = json.loads(json.dumps(blueprint, ensure_ascii=False))
    invalid["dominant_features"][0]["code"] = "UNKNOWN"
    monkeypatch.setattr(travel_harness, "_client", lambda: object())
    monkeypatch.setattr(travel_harness, "_complete", lambda *args, **kwargs: json.dumps(invalid, ensure_ascii=False))
    personas = travel_harness.generate_personas(1, use_llm=True)
    assert personas[0].id == blueprint["id"]
    assert "archetype_fallback" in personas[0].evidence_refs


def test_blueprints_only_use_enabled_dimensions(monkeypatch):
    original = travel_harness.load_factors
    monkeypatch.setattr(travel_harness, "load_factors", lambda enabled_only=False: original(True) if enabled_only else original())
    rows = travel_harness._blueprints(3)
    enabled = {factor.id for factor in original(True)}
    assert all(set(row["factor_weights"]) == enabled for row in rows)


def test_llm_cannot_upgrade_unmatched_copy_to_advance(monkeypatch):
    persona = travel_harness._blueprints(1)[0]
    from schemas import Persona
    persona = Persona.model_validate(persona)
    monkeypatch.setattr(travel_harness, "_client", lambda: object())
    monkeypatch.setattr(
        travel_harness,
        "_complete",
        lambda *args, **kwargs: json.dumps({
            "decision": "advance", "willingness": 10, "reaction": "我愿意立刻预订。",
            "reasoning": "看起来很吸引人。", "outcome_improved": [], "unresolved_outcomes": [],
            "next_step": persona.jtbd.current_step,
        }, ensure_ascii=False),
    )
    result = travel_harness.simulate_persona(
        persona, "一个完全无关的文本", travel_harness.load_factors(),
        travel_harness.load_outcomes(), [], use_llm=True,
    )
    assert result.decision == "na"
    assert result.mode == "llm"


def test_memory_is_included_in_llm_simulation_prompt(monkeypatch):
    from schemas import Persona
    persona = Persona.model_validate(travel_harness._blueprints(1)[0])
    prompts = []
    monkeypatch.setattr(travel_harness, "_client", lambda: object())
    monkeypatch.setattr(travel_harness, "_complete", lambda client, prompt, **kwargs: (prompts.append(prompt) or json.dumps({"decision":"na"})))
    travel_harness.simulate_persona(persona, "旅行方案", travel_harness.load_factors(), travel_harness.load_outcomes(), [],
        use_llm=True, memory=[{"campaign":"上次方案", "decision":"hesitate"}])
    assert "上次方案" in prompts[0]

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from schemas import TravelInfo
from services import travel_harness


@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_deepseek_j7_batch_rejects_renamed_copies(client, monkeypatch, repair_succeeds):
    request = {"count": 7, "job_ids": ["J7"]}
    before = client.post("/api/generate", json={**request, "use_llm": False}).json()
    rows = deepcopy(before)
    for index, row in enumerate(rows):
        row["name"] = f"周{chr(0x4e00 + index)}"
        row["travel"]["budget_per_person"] = 2100 + 500 * index
        row["mindset"]["quote"] = f"我给这趟旅行的第 {index + 1} 项体验留了半天。"
    renamed_copy = {**rows[0], "name": rows[1]["name"]}
    rephrased_copy = {**renamed_copy, "mindset": rows[1]["mindset"]}
    rephrased_copy["travel"] = {**renamed_copy["travel"], "budget_per_person": 2200}
    rephrased_copy["drivers"] = list(reversed(renamed_copy["drivers"]))
    responses = iter(
        [rows[0], renamed_copy, rephrased_copy, *rows[1:]]
        if repair_succeeds else [rows[0], *([renamed_copy] * travel_harness.MAX_QC_RETRIES)]
    )
    prompts = []

    def complete(_client, prompt, **kwargs):
        prompts.append(prompt)
        return json.dumps(next(responses), ensure_ascii=False)

    monkeypatch.setattr(travel_harness, "_client", lambda: object())
    monkeypatch.setattr(travel_harness, "_complete", complete)
    response = client.post("/api/generate", json={**request, "use_llm": True})
    assert rows[0]["mindset"]["quote"] in prompts[1]
    assert "旅行自述重复" in prompts[2]
    if repair_succeeds:
        assert "出游安排、顾虑和关注点重复" in prompts[3]
        assert response.status_code == 200, response.text
        result = response.json()
        assert len(result) == 7
        assert all(row["jtbd"]["job_id"] == "J7" for row in result)
        assert len({row["travel"]["budget_per_person"] for row in result}) == 7
        assert len({row["mindset"]["quote"] for row in result}) == 7
        assert client.get("/api/personas").json() == result
    else:
        assert response.status_code == 422
        assert "第 2 位画像未通过质检" in response.json()["detail"]
        assert client.get("/api/personas").json() == before


@pytest.mark.parametrize("count", [8, 60])
def test_deepseek_batch_uses_distinct_constraints_and_upstream_parameters(client, monkeypatch, count):
    rows = travel_harness._blueprints(count)
    seed_names = [row["name"] for row in rows[:7]]
    for index, row in enumerate(rows):
        row["name"] = f"周{chr(0x4e00 + index)}"
        row["travel"].update(trip_length_days=2 + index // 6, party_size=1 + index % 6, departure_window="九月初")
        row["mindset"]["quote"] = f"假期安排第{index + 1}天和同行者去看海。"
    numbered = {**rows[0], "name": f"{seed_names[0]}·２"}
    seed_copy = {**rows[0], "name": seed_names[0]}
    responses = iter([numbered, seed_copy, *rows])
    calls = []

    def create(**payload):
        calls.append(payload)
        content = json.dumps(next(responses), ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    model = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(travel_harness, "_client", lambda: model)
    response = client.post("/api/generate", json={"count": count, "use_llm": True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result) == count
    assert [row["name"] for row in result] == [row["name"] for row in rows]
    assert [row["jtbd"]["job_id"] for row in result] == [row["jtbd"]["job_id"] for row in rows]
    assert client.get("/api/personas").json() == result
    assert [call["temperature"] for call in calls] == [0.88, 0.35, 0.35] + [0.88] * (count - 1)
    assert all(call["max_tokens"] == 4096 and call["extra_body"] == {"thinking": {"type": "disabled"}} for call in calls)
    prompts = [call["messages"][0]["content"] for call in calls]
    assert "末尾不得带数字编号" in prompts[1]
    assert "画像姓名与规则种子或本批已生成画像重复" in prompts[2]
    contexts = [json.loads(prompt.split("【结构上下文】\n")[1].split("\n\n【生成步骤】")[0]) for prompt in [prompts[0], *prompts[3:]]]
    assert len({tuple(context["travel_constraints"]) for context in contexts}) == count
    assert set(seed_names) == set(contexts[0]["seed_names"])
    assert [p["name"] for p in contexts[-1]["existing_personas"]] == [row["name"] for row in rows[:-1]]


def test_legacy_generation_creates_tourism_intent_personas(client):
    response = client.post('/api/generate', json={'count': 2, 'use_llm': False})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2
    assert all(row['jtbd']['core_job'] for row in rows)
    assert all({'synthetic', 'hypothesis'} <= set(row['evidence_refs']) for row in rows)
    assert len(client.get('/api/personas').json()) == 2


def test_legacy_simulator_returns_classifications_and_task_outcomes(client):
    generated = client.post('/api/generate', json={'count': 3, 'use_llm': False})
    assert generated.status_code == 200, generated.text
    selected = {persona['id']: persona for persona in generated.json()[:2]}
    jobs = client.get('/api/jobs').json()
    steps_by_job = {
        job['id']: {step['name'] for stage in job['stages'] for step in stage['steps']}
        for job in jobs['job_trees']
    }
    response = client.post('/api/simulate', json={
        'campaign': '周末短途旅行方案，费用包含交通与住宿，可免费改期。',
        'use_llm': False,
        'persona_ids': list(selected),
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert {row['persona_id'] for row in data['results']} == set(selected)
    assert sum(data['summary'].values()) == 2
    for row in data['results']:
        task = selected[row['persona_id']]['jtbd']
        assert row['next_step'] in steps_by_job[task['job_id']]
        assert 'outcome_improved' in row and 'unresolved_outcomes' in row


def test_retired_evidence_optimizer_stays_unavailable(client):
    assert client.post('/api/personas/optimize').status_code == 404
    assert client.get('/api/personas/evidence').status_code == 404


def test_memory_reset_uses_legacy_route_without_touching_persona_store(client, tmp_path, monkeypatch):
    from routes import travel
    path = tmp_path / 'travel_memories.json'
    monkeypatch.setattr(travel, 'MEMORY_PATH', path)
    response = client.post('/api/memories/reset')
    assert response.status_code == 200
    assert path.read_text(encoding='utf-8') == '{}'


def test_simulation_persists_only_selected_profile_memories(client, tmp_path, monkeypatch):
    from routes import travel
    path = tmp_path / 'travel_memories.json'
    monkeypatch.setattr(travel, 'MEMORY_PATH', path)
    client.post('/api/generate', json={'count': 2, 'use_llm': False})
    response = client.post('/api/simulate', json={'campaign': '提供清楚的费用明细', 'use_memory': True})
    assert response.status_code == 200, response.text
    memories = __import__('json').loads(path.read_text(encoding='utf-8'))
    assert set(memories) == {row['persona_id'] for row in response.json()['results']}
    assert all(row[0]['campaign'] == '提供清楚的费用明细' for row in memories.values())


def test_missing_travel_attributes_remain_unknown():
    assert all(value is None for value in TravelInfo().model_dump().values())

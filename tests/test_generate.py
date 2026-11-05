from schemas import TravelInfo
def test_legacy_generation_creates_tourism_intent_personas(client):
    response = client.post('/api/generate', json={'count': 2, 'use_llm': False})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2
    assert all(row['jtbd']['core_job'] for row in rows)
    assert all({'synthetic', 'hypothesis'} <= set(row['evidence_refs']) for row in rows)
    assert len(client.get('/api/personas').json()) == 2


def test_legacy_simulator_returns_classifications_and_task_outcomes(client):
    client.post('/api/generate', json={'count': 2, 'use_llm': False})
    response = client.post('/api/simulate', json={
        'campaign': '周末短途旅行方案，费用包含交通与住宿，可免费改期。',
        'use_llm': False,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['results']) == 2
    assert sum(data['summary'].values()) == 2
    assert all('outcome_improved' in row and 'unresolved_outcomes' in row for row in data['results'])


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

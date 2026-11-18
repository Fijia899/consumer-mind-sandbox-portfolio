from io import BytesIO

import pytest
from openpyxl import load_workbook


@pytest.fixture
def travel_memory(tmp_path, monkeypatch):
    from routes import travel
    monkeypatch.setattr(travel, "MEMORY_PATH", tmp_path / "memories.json")
    return travel.MEMORY_PATH


def test_generate_filter_simulate_export_and_memory_roundtrip(client, travel_memory):
    generated = client.post('/api/generate', json={'count': 4, 'use_llm': False, 'job_ids': ['J3']})
    assert generated.status_code == 200, generated.text
    personas = generated.json()
    assert len(personas) == 4
    assert {p['jtbd']['job_id'] for p in personas} == {'J3'}
    campaign = '周末两天游，人均1200元含交通住宿，费用透明无隐藏费用，可免费改期一次。'
    response = client.post('/api/simulate', json={'campaign': campaign, 'use_memory': True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert {r['persona_id'] for r in result['results']} == {p['id'] for p in personas}
    assert all(r['reaction'] and r['next_step'] for r in result['results'])
    exported = client.post('/api/export/campaign', json={'campaign': campaign, **result})
    assert exported.status_code == 200, exported.text
    workbook = load_workbook(BytesIO(exported.content), read_only=True)
    try:
        cells = [cell for sheet in workbook for row in sheet.values for cell in row]
        assert campaign in cells
        assert all(p['name'] in cells for p in personas)
        assert '人均预算（元）' in cells
    finally:
        workbook.close()
    identifier = personas[0]['id']
    assert client.get(f'/api/personas/{identifier}/memories').json()['memories']
    bundle = client.get('/api/memories/export').json()
    client.post('/api/memories/reset')
    assert not client.get(f'/api/personas/{identifier}/memories').json()['memories']
    import json
    restored = client.post('/api/memories/import', files={'file': ('memory.json', json.dumps(bundle), 'application/json')})
    assert restored.status_code == 200, restored.text
    assert client.get(f'/api/personas/{identifier}/memories').json()['memories']
    assert client.post('/api/verify', json={'persona_id': identifier, 'status': 'verified', 'note': '旅游访谈待核对'}).status_code == 200
    assert client.post(f'/api/personas/{identifier}/memories/reset').status_code == 200
    assert not client.get(f'/api/personas/{identifier}/memories').json()['memories']


def test_invalid_memory_import_preserves_existing_file(client, travel_memory):
    travel_memory.write_text('{}', encoding='utf-8')
    for payload in ('[]', '{"format":"travel-memories-v1","memories":{"x":[null]}}'):
        response = client.post('/api/memories/import', files={'file': ('bad.json', payload, 'application/json')})
        assert response.status_code == 422
        assert travel_memory.read_text(encoding='utf-8') == '{}'

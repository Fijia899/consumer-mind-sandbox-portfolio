import pytest


def test_original_travel_workbench_pages(client):
    for path in ('/', '/agent', '/jobs', '/admin'):
        response = client.get(path)
        assert response.status_code == 200
        assert '旅游意向人群心智沙盘' in response.text
        assert 'no-store' in response.headers['cache-control']
    for path in ('/participants', '/research', '/sources'):
        assert client.get(path).status_code == 404
    page = client.get('/').text
    for control in ('gen-count', 'entry-themes', 'btn-generate', 'campaign-text',
                    'btn-simulate', 'persona-list', 'persona-detail', 'result-heatmap', 'btn-export-excel'):
        assert f'id="{control}"' in page
    assert 'research-console' not in page
    assert 'id="run-research-agent"' not in page
    assert 'href="/jobs"' in page
    assert 'original-travel-workbench-v1' in client.get('/api/health').json()['capabilities']


def test_original_assets_use_travel_data(client):
    js = client.get('/static/js/app.js').text
    assert 'p.travel?.stage' in js
    assert 'p.osa' not in js
    assert 'MindSim for Travel' in client.get('/').text
    for outcome in client.get('/api/outcomes').json():
        assert outcome['label'] in js
    assert client.get('/static/css/app.css').status_code == 200


@pytest.mark.parametrize('method,path',[
    ('post','/api/research/starter'), ('post','/api/research/import'),
    ('post','/api/research/evaluate'), ('post','/api/research/trials'),
])
def test_removed_research_pages_do_not_disable_api_safety(client, method, path):
    response = getattr(client, method)(path, json={})
    assert response.status_code == 410

import pytest


def test_original_travel_workflow_is_the_only_primary_page(client):
    for path in ('/', '/agent'):
        response = client.get(path)
        assert response.status_code == 200
        assert '旅游意向人群心智沙盘' in response.text
        assert 'id="persona-list"' in response.text
        assert 'id="agent-analysis"' in response.text
        assert 'href="/jobs"' not in response.text
        assert 'href="/sources"' not in response.text
        assert 'no-store' in response.headers['cache-control']

    for path in ('/participants', '/jobs', '/research', '/sources'):
        assert client.get(path).status_code == 404

    assert client.get('/admin').status_code == 200
    health = client.get('/api/health').json()
    assert health['audience'] == '旅游意向人群'
    assert 'legacy-travel-simulator-v1' in health['capabilities']
    assert 'visual-analysis-flow-v1' in health['capabilities']


def test_home_restores_legacy_generation_and_analysis_controls(client):
    page = client.get('/').text
    for control in ['count', 'job-filter', 'generate', 'persona-list', 'campaign', 'simulate', 'agent-analysis']:
        assert f'id="{control}"' in page
    assert 'data-flow="plan"' in page
    assert 'data-flow="factors"' in page
    assert 'data-flow="personas"' in page
    assert 'data-flow="summary"' in page
    css = client.get('/static/css/travel.css').text
    assert '--paper:#f3f8fd' in css and '--green:#1769aa' in css
    js = client.get('/static/js/travel.js').text
    assert 'function renderAnalysisFlow' in js
    assert "api('/api/simulate'" in js


def test_analysis_flow_has_accessible_progress_and_replay(client):
    page = client.get('/').text
    assert '沿用 JTBD 旧分析逻辑' not in page
    assert 'id="analysis-progress"' in page
    assert 'role="progressbar"' in page
    assert 'id="analysis-status" role="status"' in page
    assert 'id="replay-analysis"' in page
    css = client.get('/static/css/travel.css').text
    assert '@media(prefers-reduced-motion:reduce)' in css
    assert '@keyframes flow-stream' in css


@pytest.mark.parametrize('method,path',[
    ('post','/api/research/starter'), ('post','/api/research/import'),
    ('post','/api/research/evaluate'), ('post','/api/research/trials'),
])
def test_removed_research_pages_do_not_disable_api_safety(client, method, path):
    response = getattr(client, method)(path, json={})
    assert response.status_code == 410

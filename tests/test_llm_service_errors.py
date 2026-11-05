"""Provider failures retain snapshots and never fall back to invented results."""
import json

import httpx
import pytest
from openai import OpenAI

from services import participant_predictions as predictions, participant_store as store


def completion(content):
    return {'id':'test','object':'chat.completion','created':0,'model':'test',
            'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}]}


@pytest.mark.parametrize('failure,status,retries',[(503,503,3),(429,503,3),(401,503,1),(404,503,1),('timeout',504,3),('connection',503,3)])
def test_provider_failure_retains_snapshot_without_partial_results(client,forecast,monkeypatch,failure,status,retries):
    calls=[]; clients=[]
    def handle(request):
        calls.append(request)
        if failure=='timeout': raise httpx.ReadTimeout('private-provider-detail',request=request)
        if failure=='connection': raise httpx.ConnectError('private-provider-detail',request=request)
        return httpx.Response(failure,headers={'retry-after-ms':'1'},json={'error':{'message':'private-provider-detail'}})
    def factory(**kwargs):
        assert kwargs['timeout']==30 and kwargs['max_retries']==2
        api=OpenAI(api_key='test-only',base_url='https://test.invalid/v1',timeout=kwargs['timeout'],max_retries=kwargs['max_retries'],
                   http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        monkeypatch.setattr(api,'_calculate_retry_timeout',lambda *args:0)
        clients.append(api);return api
    monkeypatch.setattr(predictions,'llm_configured',lambda:True)
    monkeypatch.setattr(predictions,'get_api_key',lambda:'test-only')
    monkeypatch.setattr(predictions,'OpenAI',factory)
    before=store.get(forecast['participant_id'])['facts']
    response=client.post('/api/predictions',json=forecast)
    assert response.status_code==status,response.text
    assert 'private-provider-detail' not in response.text and '替代判断' in response.text
    assert len(calls)==2*retries
    result=client.get('/api/predictions').json()['predictions'][0]
    assert result['status']=='failed' and result['results']=={} and result['snapshot']['facts']
    assert store.get(forecast['participant_id'])['facts']==before


def test_transient_failure_retries_same_prompt(monkeypatch):
    calls=[]
    def handle(request):
        calls.append(json.loads(request.content))
        if len(calls)==1:return httpx.Response(503,headers={'retry-after-ms':'1'},json={'error':{'message':'busy'}})
        return httpx.Response(200,json=completion('{"decision":"insufficient"}'))
    monkeypatch.setattr(predictions,'llm_configured',lambda:True)
    monkeypatch.setattr(predictions,'get_api_key',lambda:'test-only')
    monkeypatch.setattr(predictions,'OpenAI',lambda **kw:OpenAI(api_key='test-only',base_url='https://test.invalid/v1',max_retries=2,
                         http_client=httpx.Client(transport=httpx.MockTransport(handle))))
    assert predictions._json_call('test system',{'campaign':'test'})['decision']=='insufficient'
    assert len(calls)==2 and calls[0]==calls[1]


def test_partial_model_success_is_not_published(client,forecast,monkeypatch):
    def call(mode,*args):
        if mode=='evidence_model':raise RuntimeError('private-failure')
        return {'decision':'hesitate'}
    monkeypatch.setattr(predictions,'request_model',call)
    assert client.post('/api/predictions',json=forecast).status_code==503
    assert client.get('/api/predictions').json()['predictions'][0]['results']=={}


def test_invalid_model_json_and_restart_interruption(client,forecast,monkeypatch):
    def invalid(*args):raise json.JSONDecodeError('invalid','?',0)
    monkeypatch.setattr(predictions,'_json_call',invalid)
    assert client.post('/api/predictions',json=forecast).status_code==502
    state=store._load();state['predictions'][0]['status']='pending';store._save(state)
    store.initialize()
    assert store._load()['predictions'][0]['status']=='failed'

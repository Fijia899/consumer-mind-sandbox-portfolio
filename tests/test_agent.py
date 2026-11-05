"""Isolated fixtures exercise the new ledger; no test data reaches real research."""
import json
import time
from copy import deepcopy
from types import SimpleNamespace

import pytest

from agent_schemas import AnalysisRequest, ProfileRequest
from services import research_agent as agent, agent_store as store, archetypes, agent_media


def test_model_json_retries_malformed_json_and_counts_both_calls(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = iter(["{tool: analyze_batch}", '{"tool":"finish"}'])
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def __enter__(self): return self
        def __exit__(self, *args): return False
        def create(self, **kwargs):
            prompts.append(json.loads(kwargs['messages'][1]['content']))
            content = next(self.responses)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                                   usage=SimpleNamespace(total_tokens=7))

    prompts = []
    monkeypatch.setattr(agent, 'llm_configured', lambda: True)
    monkeypatch.setattr(agent, 'get_api_key', lambda: 'test-only')
    monkeypatch.setattr(agent, 'get_base_url', lambda: 'https://test.invalid/v1')
    monkeypatch.setattr(agent, 'OpenAI', FakeClient)
    run, _ = store.new_run('analyze', {}, None)

    result = agent.model_json(run['id'], time.monotonic() + 30, '只返回 JSON', {'plan': '测试旅游方案'})

    assert result == {'tool': 'finish'}
    assert prompts[0] == {'plan': '测试旅游方案'}
    assert prompts[1]['invalid_response'] == '{tool: analyze_batch}'
    assert prompts[1]['original_input'] == prompts[0]
    assert store.get('run', run['id'])['usage'] == {'calls': 2, 'tokens': 14, 'unknown_usage_calls': 0}


def test_model_json_stops_after_one_malformed_json_retry(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{tool: broken}'))], usage=None)

    monkeypatch.setattr(agent, 'llm_configured', lambda: True)
    monkeypatch.setattr(agent, 'get_api_key', lambda: 'test-only')
    monkeypatch.setattr(agent, 'get_base_url', lambda: 'https://test.invalid/v1')
    monkeypatch.setattr(agent, 'OpenAI', FakeClient)
    run, _ = store.new_run('analyze', {}, None)

    with pytest.raises(ValueError, match='连续两次未返回合法 JSON'):
        agent.model_json(run['id'], time.monotonic() + 30, '只返回 JSON', {'plan': '测试旅游方案'})
    assert len(calls) == 2
    assert store.get('run', run['id'])['usage'] == {'calls': 2, 'tokens': 0, 'unknown_usage_calls': 2}


@pytest.fixture
def source():
    return {"label": "隔离测试角色", "episode": "测试周末亲子游", "target_speaker": "客户",
            "text": "客户：希望能免费改期，带孩子不能太赶。\n销售：费用是八千元。\n客户：午后要有休息时间。", "consent": True}


@pytest.fixture
def fake_agent(monkeypatch):
    def model(identifier, deadline, instruction, payload):
        agent.guard(identifier, deadline)
        if "生成旅游需求画像草稿" in instruction:
            message = next(m for m in payload['messages'] if m['speaker'] == payload['target_speaker'])
            return {"summary": "隔离测试画像概述", "needs": [{"id": "N1", "label": "希望能免费改期", "kind": "fact", "hard": True,
                    "evidence": [{"message_id": message['id'], "quote": "希望能免费改期"}]}], "unknowns": ["预算金额未知"]}
        if "选择工具" in instruction:
            if payload['remaining_ids']:
                return {"tool": "analyze_batch", "arguments": {"profile_ids": payload['remaining_ids'][:6]}}
            return {"tool": "finish" if payload['has_recommendations'] else "propose_changes", "arguments": {}}
        if "逐项判断" in instruction:
            status = "met" if "免费改期" in payload['plan'] else "unknown"
            dimension = next(iter(payload.get("enabled_decision_dimensions", [])), None)
            return {"cases": [{"profile_id": p['id'], "rows": [{"need_id": n['id'], "status": status,
                "explanation": "隔离夹具判断，非真实模型结论", "plan_quotes": [payload['plan']] if status == 'met' else [],
                "factor_matches": ([{"factor_id": dimension["id"], "rationale": "隔离夹具维度匹配", "plan_quote": payload['plan']}]
                                   if dimension and status == 'met' else []),
                "question": "请核实规则"} for n in p['needs']]} for p in payload['profiles']]}
        return {"summary": "隔离测试简报，非真实用户反馈", "questions": ["请核实服务能否兑现"],
                "candidates": [{"title": "测试修改版本", "plan": "测试方案支持免费改期", "tradeoff": "新增服务成本需要确认"}]}
    monkeypatch.setattr(agent, 'model_json', model)
    monkeypatch.setattr(agent.POOL, 'submit', lambda fn, *args: fn(*args))
    return model


def extract(client, source):
    response = client.post('/api/agent/profiles/extract', json=source)
    assert response.status_code == 202, response.text
    row = store.get('run', response.json()['id'])
    assert row['status'] == 'completed', row
    return store.get('profile', row['result']['profile_id'])


def approve(client, p):
    body = {k: p[k] for k in ['summary','needs','unknowns']}
    body.update(expected_revision=p['revision'], reviewer='隔离测试核查者')
    response = client.put('/api/agent/profiles/'+p['id']+'/review',json=body)
    assert response.status_code == 200, response.text
    return response.json()


def analysis(client, **changes):
    body = {'mode':'general','profile_ids':['A011','A021'],'plan':'测试周末方案，包含住宿和交通。',**changes}
    response = client.post('/api/agent/analyses',json=body)
    assert response.status_code == 202, response.text
    return store.get('run',response.json()['id'])


def test_extract_review_analyze_and_export_preserves_source_attribution(client, source, fake_agent):
    p=extract(client,source)
    assert p['status']=='draft'
    assert '费用是八千元' not in json.dumps(p['needs'],ensure_ascii=False)
    response=client.post('/api/agent/analyses',json={'mode':'personal','profile_ids':[p['id']],'plan':'测试方案支持免费改期'})
    assert response.status_code==422
    p=approve(client,p)
    run=analysis(client,mode='personal',profile_ids=[p['id']],plan='测试方案支持免费改期')
    assert run['status']=='completed'
    assert run['result']['metrics']['counts']['met']==1
    assert run['snapshot']['profiles'][0]['revision']==p['revision']
    assert any(e['tool']=='validate_claims' and e['status']=='completed' for e in run['events'])
    report=client.get('/api/agent/runs/'+run['id']+'/report')
    assert report.status_code==200 and '资料依据 [M1] 客户' in report.text
    assert '八千元' not in report.text


@pytest.mark.parametrize('mutation',['other-speaker','invented-quote','unknown-message','assumption','missing-evidence'])
def test_source_profile_cannot_accept_foreign_or_unsupported_facts(client,source,fake_agent,mutation):
    p=extract(client,source);data={k:deepcopy(p[k]) for k in ['summary','needs','unknowns']}
    n=data['needs'][0]
    if mutation=='other-speaker':n['evidence']=[{'message_id':'M2','quote':'费用是八千元'}]
    if mutation=='invented-quote':n['evidence'][0]['quote']='本人的预算为两万元'
    if mutation=='unknown-message':n['evidence'][0]['message_id']='M999'
    if mutation=='assumption':n['kind']='assumption'
    if mutation=='missing-evidence':n['evidence']=[]
    response=client.put('/api/agent/profiles/'+p['id']+'/review',json={**data,'expected_revision':1,'reviewer':'test'})
    assert response.status_code==422
    assert store.get('profile',p['id'])['status']=='draft'


def test_review_revision_conflict_and_existing_run_stays_frozen(client,source,fake_agent):
    p=approve(client,extract(client,source));old_revision=p['revision']
    run=analysis(client,mode='personal',profile_ids=[p['id']])
    updated=approve(client,p)
    assert updated['revision']==old_revision+1
    response=client.put('/api/agent/profiles/'+p['id']+'/review',json={**{k:p[k] for k in ['summary','needs','unknowns']},'expected_revision':old_revision,'reviewer':'test'})
    assert response.status_code==409
    assert store.get('run',run['id'])['snapshot']['profiles'][0]['revision']==old_revision


def test_prototype_types_are_explicit_and_cannot_enter_real_source_path(client):
    body={'label':'隔离假设原型','episode':'测试短途游','summary':'测试假设','needs':[{'id':'N1','label':'需要免费改期','kind':'assumption'}]}
    p=client.post('/api/agent/profiles/prototype',json=body).json()
    assert p['type']=='custom_archetype' and p['needs'][0]['kind']=='assumption'
    body['needs'][0]['kind']='fact'
    assert client.post('/api/agent/profiles/prototype',json=body).status_code==422
    assert len(archetypes.all_profiles())==24
    assert len({p['id'] for p in archetypes.all_profiles()})==24


def test_general_analysis_rejects_source_roles_and_duplicate_prototypes(client,source,fake_agent):
    p=approve(client,extract(client,source))
    for ids in [[p['id']],['A011','A011']]:
        assert client.post('/api/agent/analyses',json={'mode':'general','profile_ids':ids,'plan':'测试方案内容不少于五字'}).status_code==422


def test_24_archetype_batch_report_keeps_denominator_and_has_real_tool_events(client,fake_agent):
    run=analysis(client,profile_ids=[],cohort_size=24)
    assert run['status']=='completed'
    assert run['result']['metrics']['total']==24
    assert run['result']['metrics']['counts']['unknown']==24
    assert run['result']['metrics']['coverage']==0
    assert len([e for e in run['events'] if e['tool']=='analyze_batch' and e['status']=='completed'])==4
    assert run['snapshot']['cohort_notice'].endswith('不代表多数真实游客')


def test_comparison_uses_identical_cohort_and_reports_benefit(client,fake_agent):
    original=analysis(client,constraints='总价不能增加')
    response=client.post('/api/agent/runs/'+original['id']+'/compare',json={'plan':'修改后测试方案，支持免费改期','discussion':'优先灵活出行'})
    revised=store.get('run',response.json()['id'])
    assert revised['status']=='completed'
    assert revised['snapshot']['profiles']==original['snapshot']['profiles']
    assert revised['snapshot']['constraints']=='总价不能增加'
    assert revised['result']['metrics']['total']==original['result']['metrics']['total']
    assert all(c['change']=='clarified' for c in revised['result']['comparison'])
    assert store.get('run',original['id'])['snapshot']['plan']==original['snapshot']['plan']


def test_discussion_does_not_relabel_unverified_candidates_as_new_analysis(client,fake_agent):
    original=analysis(client,constraints='不能增加总价')
    response=client.post('/api/agent/runs/'+original['id']+'/discuss',json={'discussion':'优先照顾亲子家庭，哪些安排可以删减？'})
    discussed=store.get('run',response.json()['id'])
    assert discussed['status']=='completed'
    assert discussed['result']['cases']==original['result']['cases']
    assert discussed['snapshot']['plan']==original['snapshot']['plan']
    assert discussed['snapshot']['constraints']=='不能增加总价'
    assert discussed['result']['comparison'] is None
    assert not any(e['tool']=='analyze_batch' for e in discussed['events'])
    assert client.get('/api/agent/runs/'+discussed['id']+'/report').status_code==200


@pytest.mark.parametrize('mutation',['missing-case','duplicate-case','missing-need','foreign-need','foreign-quote','no-quote'])
def test_batch_validator_rejects_biased_or_fabricated_outputs(mutation):
    p=archetypes.all_profiles()[0];plan='测试方案有明确服务'
    case={'profile_id':p['id'],'rows':[{'need_id':n['id'],'status':'met','explanation':'测试解释','plan_quotes':[plan]} for n in p['needs']]}
    data={'cases':[case]}
    if mutation=='missing-case':data['cases']=[]
    if mutation=='duplicate-case':data['cases'].append(deepcopy(case))
    if mutation=='missing-need':case['rows'].pop()
    if mutation=='foreign-need':case['rows'][0]['need_id']='N999'
    if mutation=='foreign-quote':case['rows'][0]['plan_quotes']=['不存在的承诺']
    if mutation=='no-quote':case['rows'][0]['plan_quotes']=[]
    with pytest.raises(ValueError):agent.validate_batch(data,[p],plan)


def test_failed_batch_kept_in_report_denominator(client,fake_agent,monkeypatch):
    monkeypatch.setattr(agent,'assess_batch',lambda *args: (_ for _ in ()).throw(ValueError('test invalid output')))
    run=analysis(client)
    assert run['status']=='partial'
    assert run['result']['metrics']['total']==2
    assert run['result']['metrics']['counts']['failed']==2
    assert run['result']['metrics']['analyzed']==0


def test_no_covered_needs_is_not_mislabeled_partly_satisfied():
    p=archetypes.all_profiles()[0]
    raw={'cases':[{'profile_id':p['id'],'rows':[{'need_id':n['id'],'status':'uncovered','explanation':'方案没有涉及该需求','plan_quotes':[]} for n in p['needs']]}]}
    cases=agent.validate_batch(raw,[p],'一个没有相关服务描述的方案')
    assert cases[0]['status']=='uncovered'
    stats=agent.aggregate(cases,1)
    assert stats['coverage']==0 and stats['counts']['uncovered']==1 and stats['counts']['partial']==0


def test_analysis_snapshot_freezes_only_enabled_dimensions(monkeypatch):
    all_dimensions = [
        {"id": "B1", "enabled": True, "group": "B", "name": "预算透明", "weight": 8, "definition": "价格清晰", "keywords": ["报价"]},
        {"id": "B2", "enabled": False, "group": "B", "name": "停用维度", "weight": 7, "definition": "不用", "keywords": ["停用"]},
    ]
    monkeypatch.setattr(agent.factor_store, "get_enabled_factors", lambda: [
        agent.factor_store.Factor.model_validate(row) for row in all_dimensions if row["enabled"]
    ])
    snapshot = agent.create_analysis_snapshot(AnalysisRequest(
        mode="general", profile_ids=["A011"], plan="旅游方案说明",
    ))
    assert [row["id"] for row in snapshot["dimensions"]] == ["B1"]
    assert "keywords" in snapshot["dimensions"][0]


@pytest.mark.parametrize("match,valid", [
    ({"factor_id": "B1", "rationale": "和方案报价有关", "plan_quote": "人均报价清楚"}, True),
    ({"factor_id": "B2", "rationale": "停用项不能命中", "plan_quote": "人均报价清楚"}, False),
    ({"factor_id": "B1", "rationale": "引文不在方案", "plan_quote": "免费退款"}, False),
    ({"factor_id": "UNKNOWN", "rationale": "维度不存在", "plan_quote": "人均报价清楚"}, False),
])
def test_dimension_match_must_use_enabled_id_and_exact_plan_quote(match, valid):
    p = archetypes.all_profiles()[0]
    plan = "人均报价清楚，支持免费改期"
    raw = {"cases": [{"profile_id": p["id"], "rows": [
        {"need_id": n["id"], "status": "uncovered", "explanation": "需求未被方案提及", "plan_quotes": [], "factor_matches": []}
        for n in p["needs"]
    ]}]}
    raw["cases"][0]["rows"][0]["factor_matches"] = [match]
    dimensions = [{"id": "B1", "enabled": True}, {"id": "B2", "enabled": False}]
    if valid:
        result = agent.validate_batch(raw, [p], plan, dimensions)
        assert result[0]["rows"][0]["factor_matches"][0]["factor_id"] == "B1"
    else:
        with pytest.raises(ValueError):
            agent.validate_batch(raw, [p], plan, dimensions)


def test_dimension_analysis_requires_explicit_empty_or_populated_match_list():
    p = archetypes.all_profiles()[0]
    plan = "方案不涉及所选需求"
    raw = {"cases": [{"profile_id": p["id"], "rows": [
        {"need_id": n["id"], "status": "uncovered", "explanation": "方案未提及该需求", "plan_quotes": [], "factor_matches": []}
        for n in p["needs"]
    ]}]}
    del raw["cases"][0]["rows"][0]["factor_matches"]
    with pytest.raises(ValueError, match="factor_matches"):
        agent.validate_batch(raw, [p], plan, [])


def test_dimension_summary_counts_matches_and_keeps_unmatched_enabled_dimensions():
    cases = [{"profile_id": "A1", "rows": [{"factor_matches": [{"factor_id": "B1"}]}]},
             {"profile_id": "A2", "rows": [{"factor_matches": [{"factor_id": "B1"}, {"factor_id": "B1"}]}]}]
    dimensions = [{"id": "B1", "name": "预算", "group": "B", "weight": 8},
                  {"id": "B2", "name": "路线", "group": "B", "weight": 6}]
    summary = agent.dimension_coverage(cases, dimensions)
    assert summary == [
        {"id": "B1", "name": "预算", "group": "B", "weight": 8, "need_matches": 3, "profile_matches": 2},
        {"id": "B2", "name": "路线", "group": "B", "weight": 6, "need_matches": 0, "profile_matches": 0},
    ]


def test_idempotent_analysis_conflict_does_not_create_extra_run(client,fake_agent):
    body={'mode':'general','profile_ids':['A011'],'plan':'测试方案没有退改说明'};headers={'Idempotency-Key':'test-idempotent-key'}
    a=client.post('/api/agent/analyses',json=body,headers=headers)
    b=client.post('/api/agent/analyses',json=body,headers=headers)
    assert a.json()['id']==b.json()['id'] and len(store.listing('run'))==1
    body['plan']='另一个测试方案'
    assert client.post('/api/agent/analyses',json=body,headers=headers).status_code==422


def test_cancelled_queued_run_never_calls_model(client,monkeypatch):
    monkeypatch.setattr(agent.POOL,'submit',lambda *args:None)
    row=analysis(client)
    assert client.post('/api/agent/runs/'+row['id']+'/cancel').json()['status']=='cancelled'
    monkeypatch.setattr(agent,'model_json',lambda *args:pytest.fail('Cancelled task called model'))
    agent.worker(row['id'])
    assert store.get('run',row['id'])['result'] is None


def test_model_failure_is_recorded_without_fallback(client,monkeypatch):
    monkeypatch.setattr(agent.POOL,'submit',lambda fn,*args:fn(*args))
    monkeypatch.setattr(agent,'model_json',lambda *args: (_ for _ in ()).throw(RuntimeError('测试服务不可用')))
    row=analysis(client)
    assert row['status']=='failed' and row['result'] is None
    assert row['events'][-1]['status']=='failed'


@pytest.mark.parametrize('condition',['time','calls','tokens'])
def test_budget_guard_stops_execution(condition):
    row,_=store.new_run('test',{});deadline=time.monotonic()+10
    if condition=='time':deadline=time.monotonic()-1
    else:
        row['usage'][condition]=agent.MAX_CALLS if condition=='calls' else agent.MAX_TOKENS
        store.update_run(row['id'],usage=row['usage'])
    with pytest.raises(ValueError):agent.guard(row['id'],deadline)


def test_restart_marks_pending_tasks_interrupted():
    pending,_=store.new_run('test',{});done,_=store.new_run('test',{})
    store.update_run(done['id'],status='completed')
    store.interrupt_pending()
    assert store.get('run',pending['id'])['status']=='interrupted'
    assert store.get('run',done['id'])['status']=='completed'


def test_chat_requires_target_speaker_and_rejects_duplicate_messages(source):
    source['text']='没有说话人标签的资料'
    with pytest.raises(ValueError):agent.parse_messages(ProfileRequest(**source))
    source.update(text='',messages=[{'id':'M1','speaker':'销售','text':'推荐一个方案'}])
    with pytest.raises(ValueError):agent.parse_messages(ProfileRequest(**source))
    source['messages']=[{'id':'M1','speaker':'客户','text':'测试内容'},{'id':'M1','speaker':'客户','text':'其他内容'}]
    with pytest.raises(ValueError):agent.parse_messages(ProfileRequest(**source))


def test_media_transcription_review_timestamps_and_cascade_delete(client,fake_agent,monkeypatch,source):
    transcript={'messages':[{'id':'M1','speaker':'未标注','text':'希望能免费改期','start':0.0,'end':3.0}], 'duration':3.0}
    monkeypatch.setattr(agent_media,'transcribe',lambda path:deepcopy(transcript))
    response=client.post('/api/agent/media',content=b'test-fixture-only',headers={'X-Filename':'test.wav','X-Research-Consent':'true','Content-Type':'application/octet-stream'})
    assert response.status_code==202
    identifier=response.json()['media_id'];m=client.get('/api/agent/media/'+identifier).json()
    assert m['messages'][0]['speaker']=='未标注'
    source.update(text='',media_id=identifier,messages=[{**m['messages'][0],'speaker':'客户'}])
    p=extract(client,source);approve(client,p)
    run=analysis(client,mode='personal',profile_ids=[p['id']])
    bad=deepcopy(source);bad['messages'][0]['start']=1
    assert client.post('/api/agent/profiles/extract',json=bad).status_code==422
    assert client.delete('/api/agent/media/'+identifier).status_code==200
    assert client.get('/api/agent/runs/'+run['id']).status_code==404
    assert not store.listing('profile') and not store.listing('run')
    assert not list(store.MEDIA_DIR.glob('*.wav'))
    with store.connection() as conn:assert conn.execute('SELECT count(*) FROM keys').fetchone()[0]==0


@pytest.mark.parametrize('filename,consent',[('test.exe','true'),('test.wav','false')])
def test_audio_upload_rejects_invalid_type_or_missing_consent(client,filename,consent):
    response=client.post('/api/agent/media',content=b'fake',headers={'X-Filename':filename,'X-Research-Consent':consent})
    assert response.status_code==422 and not store.listing('media')


def test_upload_limit_removes_partial_file(client,monkeypatch):
    monkeypatch.setattr(agent_media,'MAX_BYTES',3)
    response=client.post('/api/agent/media',content=b'1234',headers={'X-Filename':'t.wav','X-Research-Consent':'true'})
    assert response.status_code==422
    assert not list(store.MEDIA_DIR.glob('*.wav'))


def test_private_origin_cannot_read_agent_data(client):
    response=client.get('/api/agent/profiles',headers={'Origin':'https://untrusted.example'})
    assert 'access-control-allow-origin' not in response.headers

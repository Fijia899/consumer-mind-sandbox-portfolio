"""Prospective same-person evaluation replaces synthetic-person enrollment."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from services import participant_store as store, participant_predictions as predictions


def answer(pid):
    return {'participant_id':pid,'respondent_key':'test-person-1','decision':'advance',
            'quote':'看过这个方案，我愿意进一步了解详情。','evidence_source':'test-only/feedback/1',
            'identity_confirmation':'同一匿名受访者编号，同一冻结情境与方案，未展示模型判断',
            'recorder':'test','observed_at':datetime.now(timezone.utc).isoformat(),'consent_confirmed':True}


def test_forecasts_freeze_evidence_and_three_comparators_before_feedback(client, forecast, mock_models, intake):
    response=client.post('/api/predictions',json=forecast)
    assert response.status_code==200,response.text
    record=response.json()
    assert record['feedback'] is None and set(record['results'])==set(predictions.VARIANTS)
    assert record['participant_revision']==2 and record['signature'] and record['model']
    assert all('willingness' not in r and 'probability' not in r for r in record['results'].values())
    feedback=answer(forecast['participant_id'])
    posted=client.post(f"/api/predictions/{record['id']}/feedback",json=feedback)
    assert posted.status_code==200,posted.text
    assert posted.json()['results']==record['results'] and posted.json()['snapshot']==record['snapshot']
    assert 'respondent_key' not in posted.json()['feedback']
    assert client.post(f"/api/predictions/{record['id']}/feedback",json=feedback).status_code==422
    intake['label']='修改开发档案标签'
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code==200
    saved=client.get('/api/predictions').json()['predictions'][0]
    assert saved['snapshot']==record['snapshot'] and saved['participant_revision']==2


@pytest.mark.parametrize('change', ['wrong-key','wrong-person','early','future','no-consent','baseline-source','baseline-answer'])
def test_feedback_must_be_same_person_new_answer_after_prediction(client, forecast, mock_models, change, intake):
    record=client.post('/api/predictions',json=forecast).json()
    body=answer(forecast['participant_id'])
    if change=='wrong-key': body['respondent_key']='similar-person'
    if change=='wrong-person': body['participant_id']='XHS-05'
    if change=='early': body['observed_at']=record['created_at']
    if change=='future': body['observed_at']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    if change=='no-consent': body['consent_confirmed']=False
    if change=='baseline-source': body['evidence_source']=intake['sources'][0]['locator']
    if change=='baseline-answer': body['quote']=intake['facts'][0]['quote']
    assert client.post(f"/api/predictions/{record['id']}/feedback",json=body).status_code==422
    assert client.get('/api/predictions').json()['predictions'][0]['feedback'] is None


def test_holdout_is_frozen_and_cannot_be_reused_after_answers(client, forecast, mock_models, intake):
    forecast['evaluation_split']='holdout'
    record=client.post('/api/predictions',json=forecast).json()
    intake['label']='不允许测试中修改'
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code==422
    review={'status':'excluded','reviewer':'test','note':'不能剔除预测困难样本','identity_level':'consented_response'}
    assert client.post(f"/api/participants/{forecast['participant_id']}/review",json=review).status_code==422
    assert client.post('/api/predictions',json={**forecast,'evaluation_split':'development'}).status_code==422
    assert client.post(f"/api/predictions/{record['id']}/feedback",json=answer(forecast['participant_id'])).status_code==200
    forecast['campaign']='另一个旅游方案，无隐藏费用'
    assert client.post('/api/predictions',json=forecast).status_code==422


def test_answers_cannot_be_reimported_as_baseline_evidence(client, forecast, mock_models, intake):
    record=client.post('/api/predictions',json=forecast).json(); feedback=answer(forecast['participant_id'])
    assert client.post(f"/api/predictions/{record['id']}/feedback",json=feedback).status_code==200
    intake['sources'][0]['text'] += feedback['quote']
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code==422


def test_duplicates_cannot_be_rerun_to_select_good_outcomes(client, forecast, mock_models):
    assert client.post('/api/predictions',json=forecast).status_code==200
    forecast['campaign']=' '.join(forecast['campaign'])
    assert client.post('/api/predictions',json=forecast).status_code==422


def test_same_person_can_have_separate_trip_predictions(client, forecast, mock_models):
    state=store._load();person=store.find(state,forecast['participant_id'])
    person['episodes'].append({'id':'E2','title':'独立情境测试','source_ids':[],'time_scope':'historical'})
    store._save(state)
    first=client.post('/api/predictions',json=forecast).json()
    second=client.post('/api/predictions',json={**forecast,'episode_id':'E2'})
    assert second.status_code==200 and second.json()['id']!=first['id']
    assert second.json()['snapshot']['facts']==[]


def test_model_receives_only_scoped_redacted_facts_never_feedback(client, forecast, monkeypatch):
    payloads=[]
    def capture(system,payload):
        payloads.append(deepcopy(payload))
        return {'decision':'insufficient','missing_information':['需确认本次安排']}
    monkeypatch.setattr(predictions,'_json_call',capture)
    forecast['campaign'] += ' 联系 13800138000 test@example.com'
    assert client.post('/api/predictions',json=forecast).status_code==200
    generic=next(p for p in payloads if p['mode']=='generic')
    evidence=next(p for p in payloads if p['mode']=='evidence_model')
    assert 'facts' not in generic and 'researcher_analysis' not in generic
    assert len(evidence['facts'])==4 and evidence['researcher_analysis']
    assert not any(k in evidence for k in ['feedback','subject_key','profile_url','participant_id'])
    assert '13800138000' not in str(payloads) and 'test@example.com' not in str(payloads)


def test_metrics_count_abstentions_and_independent_participants(client, forecast, mock_models):
    record=client.post('/api/predictions',json=forecast).json()
    assert all(v['accuracy_all_feedback'] is None for v in predictions.listing()['metrics'][0]['variants'].values())
    assert client.post(f"/api/predictions/{record['id']}/feedback",json=answer(forecast['participant_id'])).status_code==200
    first=predictions.listing()['predictions'][0]
    second=deepcopy(first); second['id']='test-second'; second['results']['evidence_model']=predictions.insufficient(['资料缺失'])
    metrics=predictions.metrics([first,second])[0]
    v=metrics['variants']['evidence_model']
    assert metrics['cases']==2 and metrics['participants']==1 and metrics['feedback_participants']==1
    assert v['coverage']==.5 and v['insufficient_rate']==.5
    assert v['accuracy_on_answered']==1 and v['accuracy_all_feedback']==.5
    assert v['confusion']['advance']['insufficient']==1
    assert v['macro_f1']==pytest.approx((2/3)/4)
    failed=deepcopy(first);failed.update(status='failed',results={},feedback=None)
    with_failure=predictions.metrics([first,failed])[0]
    assert with_failure['failed_cases']==1 and with_failure['completed_cases']==1
    assert with_failure['variants']['evidence_model']['coverage']==.5

import pytest
from datetime import date, timedelta
from services import participant_store as store, participant_predictions as predictions


def test_historical_context_cannot_be_treated_as_current(client, forecast, monkeypatch):
    monkeypatch.setattr(predictions,'request_model',lambda *a:pytest.fail('Insufficient inputs must not call model'))
    forecast['context_mode']='current'
    result=client.post('/api/predictions',json=forecast).json()
    assert result['status']=='completed'
    assert all(r['decision']=='insufficient' for r in result['results'].values())


def test_expired_current_confirmation_blocks_prediction(client, forecast, monkeypatch):
    state=store._load(); person=store.find(state,forecast['participant_id'])
    person['episodes'][0].update(time_scope='current',current_valid_until=(date.today()-timedelta(days=1)).isoformat())
    store._save(state)
    monkeypatch.setattr(predictions,'request_model',lambda *a:pytest.fail('Expired context called model'))
    result=client.post('/api/predictions',json={**forecast,'context_mode':'current'}).json()
    assert result['results']['evidence_model']['decision']=='insufficient'


def test_one_comment_cannot_borrow_another_trip_budget(client, monkeypatch):
    monkeypatch.setattr(predictions,'request_model',lambda *a:pytest.fail('Sparse episode called model'))
    person=store.listing()['participants'][0]
    episode=next(e for e in person['episodes'] if len(predictions.scoped_context(person,e['id'])[1])<2)
    response=client.post('/api/predictions',json={'participant_id':person['id'],'episode_id':episode['id'],'campaign':'周末出行方案可免费改期'})
    result=response.json()
    assert response.status_code==200 and result['results']['evidence_model']['decision']=='insufficient'
    assert all(set(f['source_ids'])<=set(episode['source_ids']) for f in result['snapshot']['facts'])


def test_prediction_never_changes_person_facts(client, forecast, mock_models):
    before=store.get(forecast['participant_id'])
    assert client.post('/api/predictions',json=forecast).status_code==200
    after=store.get(forecast['participant_id'])
    for key in ('facts','sources','insights','episodes','revision'):
        assert after[key]==before[key]
    assert client.post('/api/predictions',json={**forecast,'campaign':'a'}).status_code==422
    assert client.post('/api/predictions',json={**forecast,'episode_id':'another-person-trip','campaign':'另一旅游方案'}).status_code==422


def test_unchecked_source_is_never_sent_to_model(client, forecast, monkeypatch):
    state=store._load(); person=store.find(state,forecast['participant_id'])
    person['sources'][0]['review_status']='pending';store._save(state)
    monkeypatch.setattr(predictions,'request_model',lambda *a:pytest.fail('Unchecked evidence reached model'))
    record=client.post('/api/predictions',json=forecast).json()
    assert record['snapshot']['facts']==[] and record['snapshot']['sources']==[]
    assert record['results']['evidence_model']['decision']=='insufficient'

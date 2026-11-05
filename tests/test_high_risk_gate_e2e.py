import pytest
from services import participant_predictions as predictions


@pytest.mark.parametrize('invalid',[{'decision':'advance','supporting_fact_ids':['other-person-F1'],'campaign_quotes':['免费改期']},
    {'decision':'reject','supporting_fact_ids':['F1'],'campaign_quotes':['方案不包含的文字']},
    {'decision':'advance','supporting_fact_ids':['F1'],'campaign_quotes':[]},
    {'decision':'advance','supporting_fact_ids':['F1'],'campaign_quotes':['免费改期'],'biography':'虚构职业'}])
def test_model_cannot_invent_refs_promises_or_biography(client,forecast,monkeypatch,invalid):
    def model(mode,*args):
        return {'decision':'insufficient'} if mode=='generic' else invalid
    monkeypatch.setattr(predictions,'request_model',model)
    assert client.post('/api/predictions',json=forecast).status_code in (422,502)
    record=client.get('/api/predictions').json()['predictions'][0]
    assert record['status']=='failed' and record['results']=={}


def test_missing_relevance_cannot_be_reported_as_not_applicable(client,forecast,monkeypatch):
    monkeypatch.setattr(predictions,'request_model',lambda mode,*args: {'decision':'na','supporting_fact_ids':[] if mode=='generic' else ['F1']})
    record=client.post('/api/predictions',json=forecast).json()
    assert record['results']['evidence_model']['decision']=='insufficient'

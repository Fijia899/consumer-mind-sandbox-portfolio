import csv
import io
import json
from copy import deepcopy
from datetime import date, timedelta

import pytest

from services import participant_store as store, participant_predictions as predictions


def test_migration_keeps_six_distinct_accounts_and_contexts(client):
    data = client.get('/api/participants').json()
    assert data['counts'] == {'accepted': 6, 'pending': 0, 'excluded': 0}
    assert sum(len(p['sources']) for p in data['participants']) == 24
    assert sum(len(p['facts']) for p in data['participants']) == 33
    for p in data['participants']:
        assert p['identity_level'] == 'account_traceable'
        assert not p['eligibility_issues']
        assert 'subject_key' not in p and 'age' not in p and 'budget' not in p
        assert len(p['episodes']) == 4
        assert all(e['time_scope'] != 'current' and len(e['source_ids']) == 1 for e in p['episodes'])
        assert all(f['representation'] == 'checked_summary' for f in p['facts'])


def test_single_questionnaire_can_be_accepted_without_two_posts(client, accepted):
    p = client.get('/api/participants/' + accepted).json()
    assert p['status'] == 'accepted' and not p['eligibility_issues']
    assert len(p['sources']) == 1 and p['identity_level'] == 'consented_response'


@pytest.mark.parametrize('mutation', ['no-source', 'invented', 'other-person', 'unknown-attribute', 'analysis-as-fact', 'duplicate-quote'])
def test_unsupported_or_mixed_facts_rejected(client, intake, mutation):
    if mutation == 'no-source': intake['sources'] = []
    if mutation == 'invented': intake['facts'][0]['quote'] = '本人有两万元预算'
    if mutation == 'other-person': intake['sources'][0]['subject_key'] = 'another-account'
    if mutation == 'unknown-attribute': intake['age'] = 30
    if mutation == 'analysis-as-fact': intake['facts'][0]['source_id'] = 'I1'
    if mutation == 'duplicate-quote': intake['facts'][1]['quote'] = intake['facts'][0]['quote']
    assert client.post('/api/participants/import', json={'records':[intake]}).status_code == 422
    assert client.get('/api/participants').json()['counts']['pending'] == 0


def test_draft_remains_pending_and_cannot_predict(client, intake):
    intake['facts'] = intake['facts'][:1]; intake['insights'] = []
    pid = client.post('/api/participants/import', json={'records':[intake]}).json()['ids'][0]
    assert client.post('/api/predictions', json={'participant_id':pid,'episode_id':'E1','campaign':'测试旅游方案'}).status_code == 422
    assert client.post(f'/api/participants/{pid}/review',json={'status':'accepted','reviewer':'test','note':'测试审核但信息不足','identity_level':'consented_response'}).status_code == 422


def test_network_sources_require_own_notes_and_matching_profile(client, intake):
    intake.update(platform='小红书',profile_url='https://www.xiaohongshu.com/user/profile/test-person-1')
    s = intake['sources'][0]; s.update(platform='小红书',kind='note',locator='https://www.xiaohongshu.com/user/profile/other/note1',usage_basis='public_research')
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code == 422
    s['locator'] = 'https://www.xiaohongshu.com/user/profile/test-person-1/note1'
    pid = client.post('/api/participants/import',json={'records':[intake]}).json()['ids'][0]
    assert any('两篇' in issue for issue in store.get(pid)['eligibility_issues'])
    intake['profile_url'] = 'https://www.xiaohongshu.com/user/profile/other'
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code == 422


def test_deduplication_and_batch_atomicity(client, intake):
    result = client.post('/api/participants/import',json={'records':[intake]}).json()
    assert result['added'] == 1
    assert client.post('/api/participants/import',json={'records':[intake]}).json()['duplicates'] == 1
    before = store.STATE_PATH.read_bytes()
    another = deepcopy(intake); another['subject_key'] = another['sources'][0]['subject_key'] = 'test-person-2'
    fresh = deepcopy(another); fresh['sources'][0]['locator'] = 'test-only/response/2'
    bad = deepcopy(intake); bad['subject_key'] = bad['sources'][0]['subject_key'] = 'test-person-3'
    # Fresh row followed by a conflicting original response must not partially save.
    assert client.post('/api/participants/import',json={'records':[fresh,bad]}).status_code == 422
    assert store.STATE_PATH.read_bytes() == before
    assert client.post('/api/participants/import',json={'records':[intake,intake]}).status_code == 422


def test_json_and_flat_questionnaire_csv_import(client, intake):
    assert client.post('/api/participants/import-file',json={'format':'json','content':json.dumps({'records':[intake]})}).json()['added'] == 1
    row = {'respondent_key':'test-person-2','platform':intake['platform'],'label':'隔离 CSV 测试',
           'record_locator':'test-only/response/2','instrument_version':'test-v1','collected_at':date.today().isoformat(),
           'response_text':intake['sources'][0]['text'],'quotes':'\n'.join(f['quote'] for f in intake['facts']),
           'episode_title':'周末旅行','usage_basis':'consented','reviewer':'test','review_note':'隔离核查记录'}
    buf=io.StringIO(); writer=csv.DictWriter(buf,fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    response=client.post('/api/participants/import-file',json={'format':'csv','content':buf.getvalue()})
    assert response.status_code == 200, response.text
    assert response.json()['added'] == 1
    assert not store.get(response.json()['ids'][0])['eligibility_issues']
    for content in ['{}','[]','{"records": [null]}']:
        assert client.post('/api/participants/import-file',json={'format':'json','content':content}).status_code == 422
    assert client.get('/api/participants/template').json()['records'] == []


def test_identity_verification_requires_separate_record(client, accepted):
    body={'status':'accepted','reviewer':'test','note':'来源核对通过但不证明身份','identity_level':'identity_verified'}
    assert client.post(f'/api/participants/{accepted}/review',json=body).status_code == 422


def test_current_context_requires_confirmation_quote_and_dates(client, intake):
    episode=intake['episodes'][0]; episode['time_scope']='current'
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code == 422
    episode.update(current_confirmed_at=date.today().isoformat(),current_valid_until=(date.today()+timedelta(days=7)).isoformat(),confirmation_quote='这次想独自旅行')
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code == 200
    episode['confirmation_quote']='已确认下月出发'
    assert client.post('/api/participants/import',json={'records':[intake]}).status_code == 422


def test_extraction_is_exact_quote_proposal_and_never_persists(client, intake, monkeypatch):
    store.initialize(); before=store.STATE_PATH.read_bytes()
    monkeypatch.setattr(predictions,'_json_call',lambda *args:{'facts':intake['facts'],'insights':intake['insights']})
    response=client.post('/api/participants/extract',json=intake)
    assert response.status_code == 200 and response.json()['status']=='proposal_only'
    assert store.STATE_PATH.read_bytes() == before
    monkeypatch.setattr(predictions,'_json_call',lambda *args:{'facts':[{'id':'F1','source_id':'S1','quote':'预算五万元'}],'insights':[]})
    assert client.post('/api/participants/extract',json=intake).status_code == 502
    assert store.STATE_PATH.read_bytes() == before


def test_archive_is_byte_exact_read_only_and_detects_tampering(client, tmp_path, monkeypatch):
    original=tmp_path/'personas.json'; raw=b'[\r\n {"id":"legacy-test"}\r\n]\r\n'; original.write_bytes(raw)
    monkeypatch.setattr(store,'LEGACY_PATHS',[original])
    archived=client.get('/api/archive').json()
    assert archived['read_only'] and archived['personas'][0]['id']=='legacy-test'
    backup=store.ARCHIVE_DIR/archived['manifest']['archive_id']/'personas.json'
    assert backup.read_bytes()==raw and original.read_bytes()==raw
    assert client.post('/api/archive',json={}).status_code==405
    backup.write_bytes(b'[]')
    assert client.get('/api/archive').status_code==422
    assert original.read_bytes()==raw


def test_record_urls_keep_distinct_answer_identifiers():
    assert store.canonical('https://example.com/answers?id=1&utm_source=test') == 'https://example.com/answers?id=1'
    assert store.canonical('https://example.com/answers?id=1') != store.canonical('https://example.com/answers?id=2')

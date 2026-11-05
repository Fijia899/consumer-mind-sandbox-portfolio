"""Regression checks for the reviewed 2026-10-25 public-source batch.

These verify preservation and provenance structure, not that online accounts are
verified identities or that every reported experience actually happened.
"""
import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from participant_schemas import ParticipantImport
from services import observed_profiles, participant_predictions as predictions, participant_store as store

PATH = Path(__file__).resolve().parents[1] / 'data/participant_imports/xiaohongshu_travel_20261025.json'


@pytest.fixture
def batch():
    return json.loads(PATH.read_text(encoding='utf-8'))


def test_reviewed_batch_is_fourteen_additional_accounts(batch):
    parsed = ParticipantImport.model_validate(batch)
    old = {p['account_id'] for p in observed_profiles.load()['profiles']}
    keys = [r.subject_key for r in parsed.records]
    assert len(keys) == len(set(keys)) == 14
    assert not old.intersection(keys)
    assert sum(len(r.sources) for r in parsed.records) == 48
    assert sum(len(r.facts) for r in parsed.records) == 124
    note_ids = set()
    for r in parsed.records:
        assert len(r.facts) >= 6
        assert r.platform == '小红书'
        assert r.limitations and r.unknowns
        assert all(e.time_scope != 'current' for e in r.episodes)
        assert all(s.review_method == 'assisted' and s.review_status == 'checked' for s in r.sources)
        assert all(i.method == 'assisted' for i in r.insights)
        page_excerpt_chars = defaultdict(int)
        for s in r.sources:
            url = urlsplit(s.locator)
            assert url.scheme == 'https' and url.hostname == 'www.xiaohongshu.com'
            parts = url.path.split('/')
            assert parts[3] == r.subject_key
            assert len(parts[4]) == 24
            if s.kind == 'note':
                assert parts[4] not in note_ids
                note_ids.add(parts[4])
            else:
                assert s.kind == 'comment' and url.fragment.startswith('comment-')
            page_excerpt_chars[url.path] += len(s.text.replace('\n[…]\n', ''))
        assert max(page_excerpt_chars.values()) <= 50
        assert not store.eligibility(store._imported(r))
    assert len(note_ids) == 46


def test_import_review_repeat_preserves_original_six_and_predictions(client, batch):
    before = client.get('/api/participants').json()['participants']
    predictions_before = deepcopy(store._load()['predictions'])
    response = client.post('/api/participants/import-file', json={'format': 'json', 'content': json.dumps(batch)})
    assert response.status_code == 200, response.text
    result = response.json()
    assert (result['added'], result['updated'], result['duplicates']) == (14, 0, 0)
    assert client.get('/api/participants').json()['counts'] == {'accepted': 6, 'pending': 14, 'excluded': 0}
    for pid in result['ids']:
        reviewed = client.post(f'/api/participants/{pid}/review', json={
            'status':'accepted', 'reviewer':'公开页面核查（AI辅助）',
            'note':'测试已核查批次的导入与采纳，不代表现实身份核验',
            'identity_level':'account_traceable', 'identity_evidence':'仅核对站内作者账号一致，未核验现实身份'})
        assert reviewed.status_code == 200, reviewed.text
    state = client.get('/api/participants').json()
    assert state['counts'] == {'accepted':20, 'pending':0, 'excluded':0}
    assert [p for p in state['participants'] if p['id'] in {p['id'] for p in before}] == before
    assert all(p['identity_level'] == 'account_traceable' for p in state['participants'])
    exact = store.STATE_PATH.read_bytes()
    repeated = client.post('/api/participants/import', json=batch)
    assert repeated.status_code == 200 and repeated.json()['duplicates'] == 14
    assert store.STATE_PATH.read_bytes() == exact
    assert store._load()['predictions'] == predictions_before


def test_real_batch_rejects_cross_account_and_invented_quotes_atomically(client, batch):
    client.get('/api/participants')
    before = store.STATE_PATH.read_bytes()
    mixed = deepcopy(batch)
    mixed['records'][-1]['sources'][0]['locator'] = batch['records'][0]['sources'][0]['locator']
    assert client.post('/api/participants/import', json=mixed).status_code == 422
    invented = deepcopy(batch)
    invented['records'][-1]['facts'][0]['quote'] = '当前人均预算五千元且确定下周出发'
    assert client.post('/api/participants/import', json=invented).status_code == 422
    assert store.STATE_PATH.read_bytes() == before


def test_updated_plans_and_past_trips_keep_their_context(batch):
    rows = {r['label']:r for r in batch['records']}
    le = rows['乐崽']
    episode = le['episodes'][0]
    texts = '\n'.join(s['text'] for s in le['sources'] if s['id'] in episode['source_ids'])
    assert '下周就去大同了' in texts and '跨年、一月底和二月底' in texts
    assert episode['time_scope'] == 'undated'
    assert not {'飞飞鱼Yvvvv', '在银河系遛狗'} & rows.keys()
    momo = rows['momo']
    assert [e['source_ids'] for e in momo['episodes']] == [['S1'],['S2'],['S3'],['S4']]
    wang = rows['小王妈妈很爱玩']
    assert wang['sources'][3]['published_at'] == '2022-05-07'
    assert wang['episodes'][3]['time_scope'] == 'historical'
    assert wang['sources'][0]['published_at'] is None
    for row in rows.values():
        assert not any(e['current_confirmed_at'] for e in row['episodes'])
        assert not {'age','income','personality','budget','identity_verified'} & row.keys()


def test_each_episode_keeps_its_analysis_without_borrowing_other_trip_facts(batch):
    count = 0
    for item in ParticipantImport.model_validate(batch).records:
        person = store._imported(item)
        for episode in person['episodes']:
            _, facts, insights, sources = predictions.scoped_context(person, episode['id'])
            assert len(insights) == 1, 'Per-person summaries must not disappear at episode filtering'
            fact_ids = {f['id'] for f in facts}
            assert set(insights[0]['fact_ids']) == fact_ids
            assert {s['id'] for s in sources} == set(episode['source_ids'])
            assert insights[0]['terms']
            result = predictions.simple_rule('方案主题：' + insights[0]['terms'][0], facts, insights)
            assert result['decision'] == 'hesitate'
            assert set(result['supporting_fact_ids']) <= fact_ids
            count += 1
    assert count == 46

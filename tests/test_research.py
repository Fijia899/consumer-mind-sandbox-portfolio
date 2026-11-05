import csv
import io
import json
from copy import deepcopy

import pytest

from research_schemas import EvidenceInput, ReviewRequest
from services import research_store as store, travel_harness as harness


@pytest.fixture(autouse=True)
def isolated_research(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "research.json")
    # Fix the local salt for reproducible tests without touching production data.
    state = store._load()
    state["salt"] = "a1" * 32
    store._save(state)


def record(index=1, **changes):
    row = {"source_url": f"https://example.com/travel/{index}", "platform": "test",
           "author_key": f"author-{index}", "usage_basis": "consented",
           "text": f"第{index}次旅行我的人均预算是2000元，担心总花费超预算，需要费用明细。",
           "job_id": "J3", "stage": "比价决策",
           "labels": [{"factor_id": "B1", "quote": "担心总花费超预算", "terms": ["超预算"]}],
           "profile": [{"field": "budget_per_person", "value": 2000, "quote": "我的人均预算是2000元"}]}
    row.update(changes)
    return row


def add(row):
    return store.import_records([EvidenceInput.model_validate(row)])["ids"][0]


def approve(record_id, **changes):
    row = next(r for r in store.dashboard()["records"] if r["id"] == record_id)
    body = {key: row[key] for key in ("job_id", "stage", "perspective", "labels", "profile")}
    body.update(status="approved", reviewer="test-researcher", note="已核对原文；不证明真人身份")
    body.update(changes)
    return store.review(record_id, ReviewRequest.model_validate(body))


def corpus():
    # Distinct authors and sources, both partitions, fixed before seeing labels.
    for index in range(1, 16):
        approve(add(record(index)))
    assert {r["split"] for r in store.dashboard()["records"]} == {"train", "holdout"}
    return store.calibrate("测试版本")




def test_same_author_and_source_stay_in_one_partition():
    first = add(record(1))
    second = add(record(2, author_key="AUTHOR-1"))
    third = add(record(3, source_url="https://example.com/travel/1?tracking=foo"))
    rows = {r["id"]: r for r in store.dashboard()["records"]}
    assert rows[first]["split"] == rows[second]["split"] == rows[third]["split"]
    assert "?" not in rows[third]["source_url"]








def test_suspected_marketing_cannot_be_approved():
    rid = add(record(authenticity="suspected_marketing"))
    with pytest.raises(ValueError, match="营销"):
        approve(rid)


def test_review_requires_specific_annotations_and_valid_quotes():
    rid = add(record())
    with pytest.raises(ValueError, match="任务"):
        approve(rid, job_id="")
    with pytest.raises(ValueError, match="原文"):
        approve(rid, labels=[{"factor_id":"B1", "quote":"编造原文"}])


def test_versions_only_use_train_and_invalidate_on_edit(monkeypatch):
    version = corpus()
    state = store.dashboard()
    assert set(version["record_ids"]) == {r["id"] for r in state["records"] if r["split"] == "train"}
    assert version["factor_author_counts"]["B1"] <= version["unique_groups"]
    approve(version["record_ids"][0], note="修订说明，需重建校准")
    assert store.dashboard()["active_version"] is None
    with pytest.raises(ValueError, match="有效校准"):
        harness.generate_personas(1, use_evidence=True)
    store.calibrate("重新建立")
    monkeypatch.setattr(store,"signature",lambda:"changed-config")
    assert store.dashboard()["active_version"] is None


def test_holdout_never_grounds_personas_and_inference_stays_out():
    version = corpus()
    rid = version["record_ids"][0]
    approve(rid, profile=[{"field":"budget_per_person","value":100,"quote":"总花费","basis":"inferred"}])
    store.calibrate("推断隔离")
    personas = harness.generate_personas(12, job_ids=["J3"], use_evidence=True)
    for p in personas:
        assert p.research["record_ids"]
        assert set(p.research["record_ids"]) <= set(store.dashboard()["active_version"]["record_ids"])
        if p.research["record_ids"] == [rid]:
            assert p.travel.budget_per_person == p.research["base_persona"]["travel"]["budget_per_person"]
            assert "travel.budget_per_person" not in p.research["field_sources"]
        else:
            assert p.travel.budget_per_person == 2000
        assert {"synthetic", "hypothesis"} <= set(p.evidence_refs)
    no_match = harness.generate_personas(1,job_ids=["J7"],use_evidence=True)[0]
    assert not no_match.research["record_ids"]
    assert "无匹配证据" in no_match.research["note"]


def test_profiles_have_measurable_effect_without_altering_raw_sources():
    corpus()
    profile = harness.generate_personas(1,job_ids=["J3"],use_evidence=True)[0]
    comments = harness.generate_personas(1,job_ids=["J3"],use_evidence=True,use_profile=False)[0]
    assert profile.travel.budget_per_person == 2000
    assert comments.travel.budget_per_person != 2000
    campaign = "人均总价3000元，费用透明，包含全部费用，无隐藏费用。"
    factors, outcomes = harness.load_factors(),harness.load_outcomes()
    hits = harness.identify_factors(campaign,factors)
    assert harness.simulate_persona(profile,campaign,factors,outcomes,hits).decision == "reject"
    assert harness.simulate_persona(comments,campaign,factors,outcomes,hits).decision == "advance"


def test_llm_cannot_forge_provenance_or_override_observed_attributes(monkeypatch):
    corpus()
    blueprint = harness.generate_personas(1,job_ids=["J3"],use_evidence=True)[0].model_dump()
    fake = deepcopy(blueprint)
    fake["evidence_refs"] = ["fake-actual-interview"]
    fake["travel"]["budget_per_person"] = 99999
    fake["research"] = {"record_ids":["forged"]}
    monkeypatch.setattr(harness,"_client",lambda:object())
    monkeypatch.setattr(harness,"_complete",lambda *args,**kwargs:json.dumps(fake,ensure_ascii=False))
    actual = harness.generate_personas(1,job_ids=["J3"],use_evidence=True,use_llm=True)[0]
    assert actual.travel.budget_per_person == 2000
    assert "fake-actual-interview" not in actual.evidence_refs
    assert actual.research["record_ids"] == blueprint["research"]["record_ids"]


def test_evaluation_reports_metrics_and_repeat_exposure():
    corpus()
    first = store.evaluate()
    second = store.evaluate()
    assert first["run_number"] == 1 and second["run_number"] == 2
    assert first["baseline"]["n"] == first["calibrated"]["n"] > 0
    assert first["calibrated"]["micro_f1"] <= 1
    assert "不代表" in first["scope"]
    assert "holdout_revisions" in first


def test_no_holdout_does_not_manufacture_accuracy():
    corpus()
    state = store._load()
    state["records"] = [r for r in state["records"] if r["split"] == "train"]
    store._save(state)
    with pytest.raises(ValueError, match="留出集"):
        store.evaluate()


def test_delete_removes_derived_versions_and_reports():
    version = corpus()
    store.evaluate()
    result = store.delete_record(version["record_ids"][0])
    assert result["invalidated_versions"] == 1
    state = store.dashboard()
    assert not state["versions"] and not state["evaluations"] and not state["active_version"]








def test_holdout_revision_marks_old_report_stale():
    corpus()
    report = store.evaluate()
    assert not store.dashboard()["evaluations"][0]["stale"]
    approve(report["record_ids"][0], note="核对标注修订")
    assert store.dashboard()["evaluations"][0]["stale"]


def test_cross_partition_leakage_is_rejected():
    corpus()
    state = store._load()
    train = next(r for r in state["records"] if r["split"] == "train")
    held = next(r for r in state["records"] if r["split"] == "holdout")
    held["group"] = train["group"]
    store._save(state)
    with pytest.raises(ValueError, match="泄漏"):
        store.evaluate()


def test_budget_rejection_cannot_be_softened_by_llm(monkeypatch):
    corpus()
    persona = harness.generate_personas(1,job_ids=["J3"],use_evidence=True)[0]
    monkeypatch.setattr(harness,"_client",lambda:object())
    monkeypatch.setattr(harness,"_complete",lambda *args,**kwargs:json.dumps({"decision":"hesitate", "reaction":"预算没有问题", "willingness":9}))
    campaign = "人均总价3000元，包含全部费用。"
    factors = harness.load_factors()
    result = harness.simulate_persona(persona,campaign,factors,harness.load_outcomes(),harness.identify_factors(campaign,factors),use_llm=True)
    assert result.decision == "reject" and result.willingness <= 3
    assert "超过" in result.reaction


def test_loading_existing_personas_does_not_rewrite_for_new_optional_metadata(tmp_path, monkeypatch):
    from services import persona_store
    persona = harness.generate_personas(1)[0].model_dump()
    persona.pop("research")
    original = json.dumps([persona],ensure_ascii=False,indent=2)
    target = tmp_path / "existing_personas.json"
    target.write_text(original,encoding="utf-8")
    monkeypatch.setattr(persona_store,"PERSONAS_PATH",target)
    monkeypatch.setattr(persona_store,"_personas",[])
    monkeypatch.setattr(persona_store,"_loaded_mtime",0)
    persona_store.load_persisted_personas()
    assert target.read_text(encoding="utf-8") == original


def test_discussion_query_and_v2ex_aliases_are_preserved():
    assert store._source('https://global.v2ex.com/t/123?p=2') == 'https://www.v2ex.com/t/123'
    assert 'tid=123' in store._source('https://www.flyert.com.cn/forum.php?mod=viewthread&tid=123&tracking=x')
    assert store._source('https://www.flyert.com.cn/forum.php?tid=123') != store._source('https://www.flyert.com.cn/forum.php?tid=124')


def test_curated_chinese_corpus_is_applied_without_manual_work(monkeypatch, tmp_path):
    from services import persona_evidence, persona_store
    original = harness.generate_personas(7)
    target = tmp_path / 'personas.json'
    target.write_text(json.dumps([p.model_dump() for p in original], ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(persona_store,'PERSONAS_PATH',target)
    monkeypatch.setattr(persona_store,'_personas',[])
    monkeypatch.setattr(persona_store,'_loaded_mtime',0)
    monkeypatch.setattr(persona_evidence,'BACKUP_DIR',tmp_path/'backups')
    before = target.read_bytes()
    result = persona_evidence.optimize_existing()
    assert result['summary']['chinese_records'] == 16
    assert result['summary']['discussions'] == 14
    assert result['summary']['adjusted'] > 0
    assert [p['id'] for p in result['personas']] == [p.id for p in original]
    assert [p['name'] for p in result['personas']] == [p.name for p in original]
    assert next((tmp_path/'backups').glob('*.json')).read_bytes() == before
    for report in result['reports']:
        for source in report['sources']:
            assert next(r for r in store.dashboard()['records'] if r['id']==source['id'])['split'] == 'train'
        for claim in report['claims']:
            for source in claim['comparisons']:
                assert next(r for r in store.dashboard()['records'] if r['id']==source['id'])['split'] == 'holdout'
    second = persona_evidence.optimize_existing()
    assert [p['research']['record_ids'] for p in second['personas']] == [p['research']['record_ids'] for p in result['personas']]
    assert all('research' not in p['research']['base_persona'] for p in second['personas'])


def test_context_sensitive_child_concern_cannot_ground_parent_persona():
    from services.persona_evidence import compatible
    row = {'job_id':'J6','text':'担心孩子长时间坐车','context':'计划带幼儿旅行',
           'labels':[{'factor_id':'B13'}],'profile':[]}
    parent = next(bp for bp in harness._blueprints(7) if bp['jtbd']['job_id']=='J6')
    assert '父母' in parent['family']
    assert not compatible(parent,row)


def test_unknown_synthetic_budget_cannot_trigger_evidence_rejection():
    from schemas import Persona
    persona = Persona.model_validate(harness._blueprints(1,job_ids=['J3'])[0])
    persona.research = {'evidence_only':True,'field_sources':{}}
    campaign='人均总价499999元，费用透明，包含全部费用，无隐藏费用。'
    factors=harness.load_factors()
    result=harness.simulate_persona(persona,campaign,factors,harness.load_outcomes(),harness.identify_factors(campaign,factors))
    assert result.decision != 'reject'
    prompt=harness._simulation_prompt(persona,campaign,result,harness.load_outcomes())
    assert '"age":' not in prompt and '"budget_per_person":' not in prompt


def test_new_evidence_dimension_is_added_to_old_persona_weight_map():
    from services.persona_evidence import install_curated_evidence
    install_curated_evidence()
    version, rows = store.active_context()
    row = next(r for r in rows if any(l['factor_id'] in {'A12','B12','B13'} for l in r['labels']) and r['perspective']=='planning')
    bp = harness._blueprints(1,job_ids=[row['job_id']])[0]
    for fid in ('A12','B12','B13'):
        bp['factor_weights'].pop(fid,None)
    grounded = store.ground_blueprints([bp],record_ids=[row['id']])[0]
    for feature in grounded['dominant_features']:
        assert grounded['factor_weights'][feature['code']] == feature['weight']

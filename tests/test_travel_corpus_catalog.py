"""Keep the travel corpus catalog aligned with the reviewed source data."""
import json
from collections import Counter
from pathlib import Path

import pytest

from participant_schemas import ParticipantImport, ParticipantReview
from services import participant_store as store

ROOT = Path(__file__).resolve().parents[1]


def read_json(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture
def catalog_state():
    """Reproduce the catalog from versioned sources, never a private local ledger."""
    store.initialize()
    batch = ParticipantImport.model_validate(read_json("participant_imports/xiaohongshu_travel_20261025.json"))
    imported = store.import_records(batch.records)
    for identifier in imported["ids"]:
        store.review(identifier, ParticipantReview(
            status="accepted", reviewer="公开批次结构回归测试",
            note="仅复现已提交公开材料的编目状态，不代表新增研究核查或身份验证",
            identity_level="account_traceable",
            identity_evidence="仅核对站内作者账号一致，未核验现实身份",
        ))
    return store._load()


def test_catalog_inventory_matches_current_corpus(catalog_state):
    excerpts = read_json("travel_evidence_zh.json")
    state = catalog_state
    participants = [p for p in state["participants"] if p["status"] == "accepted"]
    sources = [s for p in participants for s in p["sources"]]
    facts = [f for p in participants for f in p["facts"]]
    insights = [i for p in participants for i in p["insights"]]
    episodes = [e for p in participants for e in p["episodes"]]

    assert len(excerpts["records"]) == 16
    assert len({r["source_url"] for r in excerpts["records"]}) == 14
    assert len(participants) == 20
    assert len(sources) == 72
    assert len(facts) == 157
    assert len(insights) == 64
    assert len(episodes) == 70
    assert Counter(f.get("representation") for f in facts) == {
        "verbatim": 124,
        "checked_summary": 33,
    }
    assert Counter(e.get("time_scope") for e in episodes) == {
        "historical": 48,
        "undated": 22,
    }

    catalog = (ROOT / "docs" / "travel-corpus-catalog-20261104.md").read_text(encoding="utf-8")
    for expected in ("16 条摘录、14 个讨论来源", "20 个已采纳档案、72 条来源", "157 项事实记录", "64 项研究洞察", "70 个独立旅行情境", "124 项", "33 项", "48 个标记为历史、22 个时间范围未确认"):
        assert expected in catalog


def test_catalog_source_links_resolve_to_existing_facts_and_episodes(catalog_state):
    state = catalog_state
    for participant in state["participants"]:
        source_ids = {source["id"] for source in participant["sources"]}
        fact_ids = {fact["id"] for fact in participant["facts"]}
        assert all(set(fact.get("source_ids", [])) <= source_ids for fact in participant["facts"])
        assert all(set(insight.get("fact_ids", [])) <= fact_ids for insight in participant["insights"])
        assert all(set(episode.get("source_ids", [])) <= source_ids for episode in participant["episodes"])

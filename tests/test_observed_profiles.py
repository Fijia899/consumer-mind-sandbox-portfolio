import copy
import json

import pytest

from services import observed_profiles as observed


def test_curated_collection_has_traceable_sources_and_honest_counts():
    data = observed.load()
    assert data["counts"] == {"screened": 20, "included": 6, "excluded": 14,
                              "sources": 24, "distinct_note_pages": 21, "claims": 33}
    assert {p["id"] for p in data["profiles"]} == {"XHS-05", "XHS-07", "XHS-09", "XHS-10", "XHS-12", "XHS-17"}
    for profile in data["profiles"]:
        assert not ({"age", "gender", "occupation", "income", "budget_per_person", "booked", "personality"} & profile.keys())
        assert profile["unknowns"]
        assert all(s["checked_at"] == data["checked_at"] for s in profile["sources"])
        assert all("?" not in s["canonical_url"] for s in profile["sources"])
    source_dates = [s["date_display"] for p in data["profiles"] for s in p["sources"]]
    assert any("未显示年份" in d for d in source_dates)
    assert any("2023-04-09" in d for d in source_dates)


@pytest.mark.parametrize("damage", ["author", "reference", "one_note", "excluded", "comment_page", "unsafe_url", "duplicate_account"])
def test_invalid_provenance_is_rejected(damage):
    data = copy.deepcopy(observed.load())
    profile = data["profiles"][0]
    if damage == "author":
        profile["sources"][1]["author_profile_url"] = data["profiles"][1]["profile_url"]
    elif damage == "reference":
        profile["claims"][0]["source_ids"] = ["XHS-07-N1"]
    elif damage == "one_note":
        for claim in profile["claims"]:
            claim["source_ids"] = [profile["sources"][0]["id"], profile["sources"][1]["id"]]
    elif damage == "excluded":
        next(r for r in data["screening"] if r["id"] == profile["id"])["decision"] = "excluded"
    elif damage == "comment_page":
        source = profile["sources"][0]
        source["url"] = source["canonical_url"] = "https://www.xiaohongshu.com/search_result/000000000000000000000000"
    elif damage == "unsafe_url":
        profile["profile_url"] = "javascript:alert(1)"
    elif damage == "duplicate_account":
        data["screening"][1]["account_id"] = data["screening"][0]["account_id"]
    with pytest.raises(ValueError):
        observed.validate_bundle(data)


def test_negative_and_positive_promises_are_only_mentions(client):
    for text in ("酒店门票不支持退款，不能退改。", "酒店门票支持退款和免费退改。"):
        response = client.post("/api/research/observed-profiles/check", json={"campaign": text, "profile_ids": ["XHS-17"]})
        assert response.status_code == 200
        body = response.json()
        assert body["method"] == "literal_topic_mentions"
        assert [p["id"] for p in body["profiles"]] == ["XHS-17"]
        need = body["profiles"][0]["needs"][0]
        assert need["status"] == "mentioned_not_resolved"
        assert text.rstrip("。") in need["mentions"]
        assert need["question"]
        assert need["source_ids"]
        assert not any(key in json.dumps(body) for key in ('"probability"', '"decision"', '"willingness"', '"score"'))


def test_unrelated_text_does_not_resolve_any_need(client):
    body = client.post("/api/research/observed-profiles/check", json={"campaign": "欢迎报名。"}).json()
    assert len(body["profiles"]) == 6
    assert all(n["status"] == "not_mentioned" and not n["mentions"]
               for p in body["profiles"] for n in p["needs"])


@pytest.mark.parametrize("payload", [
    {"campaign": "  \n "}, {"campaign": "x" * 12001},
    {"campaign": "周边旅行", "profile_ids": []},
    {"campaign": "周边旅行", "profile_ids": ["XHS-01"]},
    {"campaign": "周边旅行", "profile_ids": ["unknown"]},
    {"campaign": "周边旅行", "predict": True},
])
def test_invalid_checks_cannot_include_excluded_people(client, payload):
    assert client.post("/api/research/observed-profiles/check", json=payload).status_code == 422


def test_api_does_not_change_personas_or_research_state(client):
    from services import persona_store, research_store
    paths = [observed.DATA_PATH, persona_store.PERSONAS_PATH, research_store.STATE_PATH]
    before = {p: p.read_bytes() if p.exists() else None for p in paths}
    response = client.get("/api/research/observed-profiles")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.json()["counts"]["excluded"] == 14
    assert client.post("/api/research/observed-profiles/check", json={"campaign": "周边一日游，留出休息时间。"}).status_code == 200
    assert {p: p.read_bytes() if p.exists() else None for p in paths} == before

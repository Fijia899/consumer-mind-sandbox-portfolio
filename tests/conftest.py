import sys
from pathlib import Path
from datetime import date

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

@pytest.fixture(autouse=True)
def isolated_simulation_research(tmp_path, monkeypatch):
    from services import research_store, participant_store, agent_store, persona_store
    from routes import travel
    monkeypatch.setattr(research_store, "STATE_PATH", tmp_path / "simulation_research.json")
    monkeypatch.setattr(participant_store, "STATE_PATH", tmp_path / "participants.json")
    monkeypatch.setattr(participant_store, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(participant_store, "LEGACY_PATHS", [])
    monkeypatch.setattr(agent_store, "DB_PATH", tmp_path / "agent.sqlite3")
    monkeypatch.setattr(agent_store, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(persona_store, "PERSONAS_PATH", tmp_path / "personas.json")
    monkeypatch.setattr(persona_store, "_personas", [])
    monkeypatch.setattr(persona_store, "_loaded_mtime", 0.0)
    monkeypatch.setattr(persona_store, "_last_write_at", None)
    monkeypatch.setattr(persona_store, "_last_write_reason", "")
    monkeypatch.setattr(travel, "MEMORY_PATH", tmp_path / "travel_memories.json")


@pytest.fixture(scope="session")
def client():
    from main import app

    return TestClient(app)


@pytest.fixture
def intake():
    """Explicit test-only questionnaire; never saved to the user's ledger."""
    quotes = ["这次想独自旅行", "只有周末两天时间", "担心夜间到达不安全", "希望可免费改期"]
    return {"subject_key": "test-person-1", "platform": "隔离测试问卷", "label": "隔离测试受访者",
            "sources": [{"id": "S1", "kind": "questionnaire", "subject_key": "test-person-1",
                         "platform": "隔离测试问卷", "locator": "test-only/response/1", "title": "测试答卷",
                         "text": "。".join(quotes), "collected_at": date.today().isoformat(),
                         "usage_basis": "consented", "instrument_version": "test-v1", "review_status": "checked",
                         "reviewer": "test", "review_note": "隔离测试核对记录"}],
            "facts": [{"id": f"F{i+1}", "source_id": "S1", "quote": q} for i, q in enumerate(quotes)],
            "insights": [{"id": "I1", "label": "退改条件", "question": "需要怎样的免费改期条件？",
                          "fact_ids": ["F4"], "terms": ["改期"], "method": "human"}],
            "episodes": [{"id": "E1", "title": "测试周末出游", "source_ids": ["S1"], "time_scope": "undated"}]}


@pytest.fixture
def accepted(client, intake):
    result = client.post("/api/participants/import", json={"records": [intake]})
    assert result.status_code == 200, result.text
    pid = result.json()["ids"][0]
    response = client.post(f"/api/participants/{pid}/review", json={"status": "accepted", "reviewer": "test",
        "note": "四项旅行信息已核对，测试记录", "identity_level": "consented_response"})
    assert response.status_code == 200, response.text
    return pid


@pytest.fixture
def forecast(accepted):
    return {"participant_id": accepted, "episode_id": "E1", "campaign": "周末独行方案，含接站，可免费改期。"}


@pytest.fixture
def mock_models(monkeypatch):
    from services import participant_predictions as predictions
    def model(mode, campaign, facts, insights, context):
        return {"decision": "hesitate" if mode == "generic" else "advance",
                "supporting_fact_ids": [facts[0]["id"]] if facts else [], "counter_fact_ids": [],
                "campaign_quotes": [campaign], "missing_information": ["请本人确认该方案是否值得继续了解？"]}
    monkeypatch.setattr(predictions, "request_model", model)
    return model

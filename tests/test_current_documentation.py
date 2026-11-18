"""Keep current product documentation aligned with its runnable workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_describes_original_travel_workbench(client):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = client.get("/").text
    for label in ("旅行方案测试", "多人总览", "导出 Excel", "任务后台"):
        assert label in page and label in readme
    assert "2026-11-16" in readme
    assert "7747517" in readme


def test_agent_report_and_event_endpoints_are_available(client):
    from main import app
    paths = set(app.openapi()["paths"])
    for path in ("/api/agent/analyses", "/api/agent/runs/{identifier}/events", "/api/agent/runs/{identifier}/report"):
        assert path in paths
    assert client.get("/participants").status_code == 404

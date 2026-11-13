"""Keep current product documentation aligned with its runnable workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_describes_agent_and_rule_mode_separately(client):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = client.get("/").text
    for label in ("分析并复测", "快速规则仿真"):
        assert label in page and label in readme
    assert "同组" in readme or "同一批" in readme
    assert "6 个内置旅游假设画像" in readme
    assert "质检" in readme and "保留上次" in readme.replace("保留上一次成功", "保留上次")
    assert "2026-11-13" in readme
    assert "archetype_fallback" not in readme


def test_agent_report_and_event_endpoints_are_available(client):
    from main import app
    paths = set(app.openapi()["paths"])
    for path in ("/api/agent/analyses", "/api/agent/runs/{identifier}/events", "/api/agent/runs/{identifier}/report"):
        assert path in paths
    assert client.get("/participants").status_code == 404

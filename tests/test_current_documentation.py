"""Keep current product documentation aligned with its runnable workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_describes_original_travel_workbench(client):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = client.get("/").text
    for label in ("旅行方案测试", "多人总览", "导出 Excel", "任务后台"):
        assert label in page and label in readme
    assert "7747517" in readme


def test_agent_report_and_event_endpoints_are_available(client):
    from main import app
    paths = set(app.openapi()["paths"])
    for path in ("/api/agent/analyses", "/api/agent/runs/{identifier}/events", "/api/agent/runs/{identifier}/report"):
        assert path in paths
    assert client.get("/participants").status_code == 404


def test_readme_starts_with_product_use_and_links_the_three_pages(client):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    introduction = readme.split("## 快速启动", 1)[0]
    assert "生成旅游画像 → 旅行方案测试 → 逐人反馈 → 多人总览 → 导出 Excel" in introduction
    assert "7 个主任务、14 个步骤、9 个期望结果" in introduction
    assert "恢复的原工作台" not in readme
    assert "当前工作台不调用" not in readme
    assert "不能代替" not in readme
    for path in ("/", "/jobs", "/admin"):
        assert f"http://127.0.0.1:8000{path}" in readme
        assert client.get(path).status_code == 200

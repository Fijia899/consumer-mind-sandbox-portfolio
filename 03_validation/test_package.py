"""Validate the published checkout, documentation and deployment contract."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit, parse_qsl

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "README.md", "AGENTS.md", "SPEC.md", "DEPLOY.md", "使用手册.md",
    "launcher.py", "start.ps1", "Dockerfile", "docker-compose.yml", ".dockerignore",
    ".env.example", "backend/main.py", "backend/requirements.txt",
    "backend/requirements-dev.txt", "backend/routes/travel.py",
    "backend/services/travel_harness.py", "frontend/index.html", "frontend/admin.html",
    "frontend/css/travel.css", "frontend/js/travel.js", "data/jobs.json",
    "data/outcomes.json", "data/factors.json", "data/persona_seeds.json",
    "data/personas.json", "tests/conftest.py", "tests/travel_browser.cjs",
    "docs/README.md", "docs/repository-audit-20261105.md",
    "01_BP/消费者心智沙盘_BP.pptx", "03_validation/test_package.py",
    "package.json", "package-lock.json", "pytest.ini", ".github/workflows/ci.yml",
    "scripts/smoke_deployment.py",
}


def text(name):
    return (ROOT / name).read_text(encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")


def test_bp_is_included_and_matches_user_file():
    bp = ROOT / "01_BP" / "消费者心智沙盘_BP.pptx"
    assert hashlib.sha256(bp.read_bytes()).hexdigest() == (
        "86c9d274b339e91f15a501c1d4a741a0c732229e88fa2cfdf13a0054005259b9"
    )


def test_clean_checkout_contains_and_tracks_the_complete_application():
    tracked = set(git("ls-files", "-z").strip("\0").split("\0"))
    assert REQUIRED <= tracked, f"Required files missing from Git: {REQUIRED - tracked}"
    assert all((ROOT / name).is_file() for name in REQUIRED)
    # Packed Git objects and locally installed dependencies are normal; only the
    # tracked publication must be free from embedded repositories/private state.
    for name in tracked:
        parts = Path(name).parts
        assert not {".git", "node_modules", "__pycache__", "02_implementation_delta"}.intersection(parts), name
        assert not any(part.startswith(".codex-") for part in parts), name
        assert not (Path(name).name.startswith(".env") and name != ".env.example"), name
        assert name not in {"data/participants_state.json", "data/research_state.json", "data/travel_memories.json"}
        assert not name.startswith(("data/agent.sqlite3", "data/agent_media/", "data/legacy_archive/")), name
    assert json.loads(git("show", ":data/personas.json")) == []


def test_readme_uses_the_reference_guide_structure_in_order():
    headings = re.findall(r"^## (.+)$", text("README.md"), re.M)
    assert headings == [
        "环境要求", "环境配置", "如何打开（启动服务）", "打开界面", "使用流程",
        "目录结构", "API", "与研究仓库的关系", "常见问题", "验收对照",
    ]
    readme = text("README.md")
    assert "旅游意向人群" in readme
    assert "github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox" in readme
    assert "7747517a36ccd92fb4a5c68866bc565ab18329c1" in readme
    factors = json.loads(text("data/factors.json"))["factors"]
    assert f"{len(factors)} 个旅游决策维度" in readme
    assert f"{len(factors)} 个维度" in text("SPEC.md")


def test_markdown_navigation_and_page_assets_resolve():
    documents = [ROOT / name for name in ("README.md", "DEPLOY.md", "使用手册.md", "SPEC.md")]
    documents += list((ROOT / "docs").glob("*.md"))
    for document in documents:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            path = (document.parent / unquote(target.split("#", 1)[0])).resolve()
            assert path.is_relative_to(ROOT), (document, target)
            assert path.is_file(), (document, target)
    for name in ("index.html", "admin.html"):
        for asset in re.findall(r'(?:src|href)="(/static/[^\"]+)"', text(f"frontend/{name}")):
            assert (ROOT / "frontend" / asset.removeprefix("/static/")).is_file(), asset


def test_readme_api_table_matches_registered_application_routes():
    routes = set()
    for filename, prefix in (("backend/main.py", ""), ("backend/routes/travel.py", "/api")):
        tree = ast.parse(text(filename))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr in {"get", "post", "put", "delete"} and decorator.args:
                            routes.add(prefix + ast.literal_eval(decorator.args[0]))
    api_section = text("README.md").split("## API\n", 1)[1].split("\n---", 1)[0]
    for endpoint in re.findall(r"`(/api/[^`]+)`", api_section):
        assert endpoint in routes, endpoint


def test_credentials_and_local_state_are_excluded_from_git_and_docker():
    samples = [".env", ".env.production", "node_modules/playwright/index.js",
               "data/travel_memories.json", "data/participants_state.json",
               "data/agent.sqlite3", "data/agent_media/private.wav"]
    for sample in samples:
        result = subprocess.run(["git", "check-ignore", "--no-index", sample], cwd=ROOT, capture_output=True)
        assert result.returncode == 0, sample
    template = dict(line.split("=", 1) for line in text(".env.example").splitlines() if line and not line.startswith("#"))
    assert template["DEEPSEEK_API_KEY"] == ""
    for entry in (".env", ".env.*", "data/participants_state.*", "data/agent.sqlite3*", "data/agent_media"):
        assert entry in text(".dockerignore").splitlines()


def test_published_source_urls_do_not_carry_share_parameters():
    for document in (ROOT / "docs").glob("*.md"):
        assert not re.search(r"[?&](?:xsec_token|xsec_source|share_id)=", document.read_text(encoding="utf-8")), document

    def urls(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from urls(item)
        elif isinstance(value, list):
            for item in value:
                yield from urls(item)
        elif isinstance(value, str) and value.startswith(("https://", "http://")):
            yield value
    for source in (ROOT / "data").rglob("*.json"):
        if source.name in {"participants_state.json", "research_state.json", "travel_memories.json"}:
            continue
        for url in urls(json.loads(source.read_text(encoding="utf-8"))):
            keys = {key.lower() for key, _ in parse_qsl(urlsplit(url).query)}
            assert not {"xsec_token", "xsec_source", "share_id"}.intersection(keys), source


def test_docker_and_compose_keep_one_process_and_matching_health_port():
    dockerfile = text("Dockerfile")
    command = json.loads(next(line[4:] for line in dockerfile.splitlines() if line.startswith("CMD ")))
    assert command[:4] == ["python", "-m", "uvicorn", "main:app"]
    assert command[command.index("--workers") + 1] == "1"
    assert command[command.index("--port") + 1] == "8000"
    assert "http://127.0.0.1:8000/api/health" in dockerfile
    compose = yaml.safe_load(text("docker-compose.yml"))["services"]["mindsim"]
    assert compose["ports"] == ["127.0.0.1:8000:8000"]
    assert "./data:/app/data" in compose["volumes"]
    assert "./.env:/app/.env:ro" in compose["volumes"]
    assert "network_mode" not in compose


def test_ci_installs_declared_dependencies_and_runs_both_suites():
    package = json.loads(text("package.json"))
    lock = json.loads(text("package-lock.json"))
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]
    assert lock["packages"]["node_modules/playwright"]["version"] == package["devDependencies"]["playwright"]
    workflow = yaml.load(text(".github/workflows/ci.yml"), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}
    python_steps = workflow["jobs"]["python"]["steps"]
    browser_steps = workflow["jobs"]["browser"]["steps"]
    container_steps = workflow["jobs"]["container"]["steps"]
    assert any(step.get("run") == "python -m pytest -q" for step in python_steps)
    for command in ("npm ci", "npm run test:syntax", "npm run test:browser"):
        assert any(step.get("run") == command for step in browser_steps)
    assert any(step.get("run") == "docker compose up -d --build" for step in container_steps)
    smoke = next(step["run"] for step in container_steps if step.get("name") == "Verify container pages and rule-mode workflow")
    assert smoke == "python scripts/smoke_deployment.py"
    ast.parse(text("scripts/smoke_deployment.py"))
    assert "03_validation" in text("pytest.ini")

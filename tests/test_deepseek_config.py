from pathlib import Path
import json

import httpx
from openai import OpenAI

import config
from services import travel_harness


def test_default_official_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_ENV", tmp_path / "missing.env")
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "MANCHUANG_ENV_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert config.get_base_url() == "https://api.deepseek.com"
    assert config.get_model_name() == "deepseek-v4-flash-0731"
    assert not config.llm_configured()


def test_local_proxy_config_overrides_shared_file(tmp_path, monkeypatch):
    shared = tmp_path / "shared.env"
    shared.write_text("DEEPSEEK_MODEL=shared-model\nDEEPSEEK_API_KEY=sk-shared-fixture\n", encoding="utf-8")
    local = tmp_path / ".env"
    local.write_text(
        f"MANCHUANG_ENV_FILE={shared}\n"
        "DEEPSEEK_API_KEY=sk-local-fixture\n"
        "DEEPSEEK_BASE_URL=https://www.tgkw.top/v1\n"
        "DEEPSEEK_MODEL=deepseek-v4-flash-0731\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "LOCAL_ENV", local)
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "MANCHUANG_ENV_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert config.get_api_key() == "sk-local-fixture"
    assert config.get_model_name() == "deepseek-v4-flash-0731"
    assert config.get_base_url() == "https://www.tgkw.top/v1"


def test_proxy_completion_uses_configured_model_and_api_path(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash-0731")

    def handle(request):
        assert str(request.url) == "https://www.tgkw.top/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer sk-test-fixture"
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-v4-flash-0731"
        assert payload["messages"] == [{"role": "user", "content": "输出旅游方案 JSON"}]
        assert payload["thinking"] == {"type": "disabled"}
        return httpx.Response(200, json={
            "id": "test-completion", "object": "chat.completion", "created": 0,
            "model": payload["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"ok": true}'}, "finish_reason": "stop"}],
        })

    with OpenAI(api_key="sk-test-fixture", base_url="https://www.tgkw.top/v1",
                http_client=httpx.Client(transport=httpx.MockTransport(handle))) as api:
        assert travel_harness._complete(api, "输出旅游方案 JSON") == '{"ok": true}'


def test_reuses_manchuang_env_without_exposing_credentials(tmp_path, monkeypatch):
    shared = tmp_path / "manchuang.env"
    shared.write_text(
        "DEEPSEEK_API_KEY=sk-test-fixture\n"
        "DEEPSEEK_BASE_URL=https://api.deepseek.com\n"
        "DEEPSEEK_MODEL=deepseek/deepseek-v4-flash\n",
        encoding="utf-8",
    )
    project_env = tmp_path / ".env"
    project_env.write_text(f"MANCHUANG_ENV_FILE={shared}\n", encoding="utf-8")
    monkeypatch.setattr(config, "LOCAL_ENV", project_env)
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "MANCHUANG_ENV_FILE"):
        monkeypatch.delenv(name, raising=False)

    assert config.load_env() == shared
    assert config.llm_configured()
    assert config.get_base_url() == "https://api.deepseek.com"
    assert config.get_model_name() == "deepseek-v4-flash"


def test_config_status_never_returns_api_key(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert "api_key" not in response.json()
    assert "secret" not in response.text.lower()

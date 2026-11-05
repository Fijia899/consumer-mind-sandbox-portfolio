import importlib.util
import io
import json
from unittest.mock import Mock
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("sandbox_launcher", Path(__file__).resolve().parents[1] / "launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class Response(io.BytesIO):
    status = 200


def test_ready_requires_legacy_travel_workbench(monkeypatch):
    health = {"status":"ok", "app_id":"travel-mind-sandbox", "capabilities":["legacy-travel-simulator-v1"]}
    def respond(url, **kwargs):
        return Response(json.dumps(health).encode() if url.endswith("health") else b'<div id="persona-list"></div>')
    monkeypatch.setattr(launcher,"urlopen",respond)
    assert launcher.service_ready(8000)
    health.pop("capabilities")
    assert not launcher.service_ready(8000)


@pytest.mark.parametrize("value", [{"status":"ok","audience":"旅游意向人群"}, [], {"app_id":"other"}])
def test_legacy_or_unrelated_service_is_not_ready(monkeypatch, value):
    monkeypatch.setattr(launcher,"urlopen",lambda *args,**kwargs:Response(json.dumps(value).encode()))
    assert not launcher.service_ready(8000)


def test_missing_workbench_route_is_not_ready(monkeypatch):
    health = {"status":"ok", "app_id":"travel-mind-sandbox", "capabilities":["legacy-travel-simulator-v1"]}
    monkeypatch.setattr(launcher,"urlopen",lambda url,**kwargs:Response(json.dumps(health).encode() if url.endswith("health") else b'{"detail":"Not Found"}'))
    assert not launcher.service_ready(8000)


def test_occupied_old_port_uses_confirmed_new_service(monkeypatch):
    monkeypatch.setattr(launcher,"port_open",lambda p:True)
    monkeypatch.setattr(launcher,"service_ready",lambda p:p==8001)
    assert launcher.choose_service() == (8001,True)


def test_old_service_selects_free_alternative(monkeypatch):
    monkeypatch.setattr(launcher,"port_open",lambda p:p==8000)
    monkeypatch.setattr(launcher,"service_ready",lambda p:False)
    assert launcher.choose_service() == (8001,False)


def test_default_port_preferred_when_free(monkeypatch):
    monkeypatch.setattr(launcher,"port_open",lambda p:False)
    assert launcher.choose_service() == (8000,False)


def test_no_usable_port_has_clear_error(monkeypatch):
    monkeypatch.setattr(launcher,"port_open",lambda p:True)
    monkeypatch.setattr(launcher,"service_ready",lambda p:False)
    with pytest.raises(RuntimeError,match="端口均被占用"):
        launcher.choose_service()


def test_api_advertises_required_capability(client):
    data = client.get("/api/health").json()
    assert data["app_id"] == "travel-mind-sandbox"
    assert "real-participants-v1" in data["capabilities"]


def test_failed_start_does_not_open_broken_page(monkeypatch):
    monkeypatch.setattr(launcher,"choose_service",lambda:(8000,False))
    monkeypatch.setattr(launcher,"find_python",lambda:"python")
    monkeypatch.setattr(launcher,"wait_ready",lambda **kwargs:False)
    proc = Mock()
    proc.poll.return_value = 1
    monkeypatch.setattr(launcher.subprocess,"Popen",lambda *args,**kwargs:proc)
    open_browser = Mock()
    monkeypatch.setattr(launcher.webbrowser,"open",open_browser)
    assert launcher.main() == 1
    open_browser.assert_not_called()

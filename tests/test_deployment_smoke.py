"""A readiness probe must tolerate Docker's startup connection resets."""
import importlib.util
import json
from pathlib import Path
from urllib.error import URLError

import pytest

spec = importlib.util.spec_from_file_location(
    "deployment_smoke", Path(__file__).resolve().parents[1] / "scripts/smoke_deployment.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize("error", [ConnectionResetError("starting"), URLError("starting"), TimeoutError("starting")])
def test_readiness_retries_startup_network_errors(monkeypatch, error):
    requests, sleeps = [], []

    def respond(base, path):
        requests.append((base, path))
        if len(requests) == 1:
            raise error
        return json.dumps({"status": "ok", "app_id": "travel-mind-sandbox"})

    monkeypatch.setattr(smoke, "call", respond)
    monkeypatch.setattr(smoke.time, "sleep", sleeps.append)
    smoke.wait_ready("http://test.invalid", attempts=2)
    assert len(requests) == 2 and sleeps == [1]


def test_readiness_has_a_finite_retry_budget(monkeypatch):
    attempts = []

    def reset(*args):
        attempts.append(1)
        raise ConnectionResetError("starting")

    monkeypatch.setattr(smoke, "call", reset)
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="did not become ready"):
        smoke.wait_ready("http://test.invalid", attempts=3)
    assert len(attempts) == 3


def test_readiness_rejects_an_unrelated_service_without_writing_to_it(monkeypatch):
    monkeypatch.setattr(smoke, "call", lambda *args: json.dumps({"status": "ok", "app_id": "other"}))
    with pytest.raises(RuntimeError, match="unexpected"):
        smoke.wait_ready("http://test.invalid")

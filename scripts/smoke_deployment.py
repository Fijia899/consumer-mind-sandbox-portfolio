"""Check a running local/container deployment without model credentials."""
import argparse
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def call(base, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(base + path, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        return response.read().decode()


def wait_ready(base, attempts=60, interval=1):
    for attempt in range(attempts):
        try:
            health = json.loads(call(base, "/api/health"))
        except (URLError, OSError):
            # Docker can accept the socket before Uvicorn is ready to respond.
            if attempt + 1 < attempts:
                time.sleep(interval)
            continue
        if health.get("status") != "ok" or health.get("app_id") != "travel-mind-sandbox":
            raise RuntimeError("The port belongs to an unexpected or unhealthy service")
        return
    raise RuntimeError("Container did not become ready")


def verify(base):
    wait_ready(base)
    assert 'id="persona-list"' in call(base, "/")
    assert 'id="factor-list"' in call(base, "/admin")
    assert not json.loads(call(base, "/api/config"))["llm_configured"]
    personas = json.loads(call(base, "/api/generate", {"count": 2, "use_llm": False}))
    assert len(personas) == 2
    result = json.loads(call(base, "/api/simulate", {
        "campaign": "周末短途旅行，费用包含交通与住宿，可免费改期。",
        "use_llm": False, "use_memory": True,
    }))
    assert len(result["results"]) == sum(result["summary"].values()) == 2
    assert json.loads(call(base, "/api/memories/reset", {}))["status"] == "ok"
    print("Container health, pages, generation, simulation and memory reset passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    verify(arguments.base_url.rstrip("/"))

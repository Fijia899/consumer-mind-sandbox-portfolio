import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

PERSONAS_PATH = ROOT / "data" / "personas.json"
EVOLUTION_PATH = ROOT / "data" / "evolution.json"


@pytest.fixture(scope="session")
def client():
    from main import app

    return TestClient(app)


@pytest.fixture(autouse=True, scope="session")
def backup_and_restore_data():
    backups = {}
    for p in (PERSONAS_PATH, EVOLUTION_PATH):
        backups[str(p)] = p.read_text(encoding="utf-8") if p.exists() else None
    yield
    for p, content in backups.items():
        path = Path(p)
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.write_text(content, encoding="utf-8")
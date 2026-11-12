"""Test setup: an isolated SQLite database and upload folder per test session."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

_tmp = tempfile.mkdtemp(prefix="pitchvision-test-")
os.environ["PITCHVISION_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["PITCHVISION_UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["PITCHVISION_SECRET_KEY"] = "test-only-secret-key-not-used-anywhere-else"
os.environ["PITCHVISION_MAX_UPLOAD_MB"] = "5"

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:          # runs the Alembic migration on startup
        yield c


@pytest.fixture(scope="session")
def auth(client):
    """Headers for the admin (first registered account)."""
    r = client.post("/api/auth/register", json={"email": "coach@example.com", "name": "Test Coach", "password": "longenough1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def tmpdir_session():
    return _tmp

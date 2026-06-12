"""Test fixtures.

Each test session uses a dedicated SQLite file so pytest never touches
the developer's working DB. The env var must be set before any
``app.*`` import resolves the engine, which is why this conftest does
the configuration in module scope.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Configure a private DB before app modules import.
_TMP_DIR = tempfile.mkdtemp(prefix="linguistos-tests-")
_DB_PATH = os.path.join(_TMP_DIR, "linguistos-test.db")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"
os.environ["LINGUISTOS_DISABLE_ENRICHMENT"] = "1"


@pytest.fixture(scope="session")
def client():
    """A TestClient bound to the test app, with startup events fired."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def workspace(client) -> dict:
    """Create a fresh workspace for the test and return its serialized form."""
    import uuid

    name = f"Test {uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/workspaces",
        json={"name": name, "language": "es", "emoji_or_flag": "🇪🇸"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()

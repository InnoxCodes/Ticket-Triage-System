"""Shared fixtures.

The database URL is pointed at a throwaway file *before* anything imports
``app.config``, because settings (and the engine built from them) are created
at import time. A temp file rather than ``:memory:`` keeps the test run close
to how the app actually runs, WAL pragmas included.

One app instance serves the whole session. Tests assert on the tickets they
create rather than on global counts, so they stay independent without wiping
the database between them.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.mkdtemp(prefix="triageai-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

OUTAGE = {
    "subject": "Checkout is down for every customer",
    "body": "Our entire production checkout is down and we are losing revenue every minute. "
    "Nobody can pay. Please escalate immediately.",
    "requester_email": "ops@northwind.co",
}


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ticket(client: TestClient) -> dict:
    response = client.post("/api/tickets", json=OUTAGE)
    assert response.status_code == 201, response.text
    return response.json()

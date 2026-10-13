"""Pytest fixtures: isolated temp database/storage, AI disabled."""
import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="smart_retail_test_")
os.environ["SMART_DATABASE_URL"] = f"sqlite:///{(Path(_tmp) / 'test.db').as_posix()}"
os.environ["SMART_STORAGE_DIR"] = str(Path(_tmp) / "storage")
os.environ["SMART_SECRET_KEY"] = "t" * 48
os.environ["SMART_AI_ENABLED"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

ADMIN_PW = "admin-password-123"
CASHIER_PW = "cashier-password-123"


@pytest.fixture(scope="session")
def client():
    init_db()
    with SessionLocal() as db:
        db.add(User(username="admin", full_name="Admin", role="admin", password_hash=hash_password(ADMIN_PW)))
        db.add(User(username="cashier", full_name="Cashier", role="cashier", password_hash=hash_password(CASHIER_PW)))
        db.commit()
    with TestClient(app) as c:
        yield c


def _login(client, user, pw):
    r = client.post("/api/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin", ADMIN_PW)


@pytest.fixture(scope="session")
def cashier(client):
    return _login(client, "cashier", CASHIER_PW)

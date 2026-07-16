"""Тесты аутентификации админа: login/logout/me и защита роутов."""

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.config import settings
from app.main import app

PASSWORD = "correct-horse"


@pytest.fixture(autouse=True)
def _configure_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_password_hash", hash_password(PASSWORD))
    monkeypatch.setattr(settings, "secret_key", "test-secret")
    monkeypatch.setattr(settings, "login_fail_delay_seconds", 0.0)


def test_me_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/admin/me")
    assert response.status_code == 401


def test_login_wrong_password() -> None:
    client = TestClient(app)
    response = client.post("/api/admin/login", json={"password": "nope"})
    assert response.status_code == 401


def test_login_success_and_me() -> None:
    client = TestClient(app)
    login = client.post("/api/admin/login", json={"password": PASSWORD})
    assert login.status_code == 200

    me = client.get("/api/admin/me")
    assert me.status_code == 200
    assert me.json() == {"admin": True}


def test_logout_clears_session() -> None:
    client = TestClient(app)
    client.post("/api/admin/login", json={"password": PASSWORD})
    assert client.get("/api/admin/me").status_code == 200

    client.post("/api/admin/logout")
    assert client.get("/api/admin/me").status_code == 401

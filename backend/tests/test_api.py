"""API smoke tests: app importable + đăng ký routes + Auth flow без DB qua monkeypatch."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_has_auth_endpoints() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec.get("paths", {})
    assert "/auth/login" in paths
    assert "/auth/signup" in paths
    assert "/auth/me" in paths
    assert "/jobs" in paths
    assert "/runs/{run_id}/events" in paths
    assert "/results" in paths
    assert "/users" in paths


def test_missing_token_returns_401() -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_invalid_token_returns_401() -> None:
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_results_requires_job_id_for_non_admin() -> None:
    """Mà không cần token thì sẽ 401 trước — kiểm tra intercept."""
    r = client.get("/results")
    assert r.status_code == 401


def test_jobs_list_requires_auth() -> None:
    r = client.get("/jobs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_signup_blocked_when_not_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force production env tạm thời
    from app.config import get_settings
    s = get_settings().model_copy(update={"app_env": "production"})
    monkeypatch.setattr("app.api.auth._settings", s)
    r = client.post("/auth/signup", json={"email": "u@e.com", "password": "password123"})
    assert r.status_code == 403


def test_signup_dev_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đăng signup thành công khi dev + chưa có user → first user trở superuser (mocked)."""

    async def fake_signup(db, email, password, full_name=None, scopes=None, is_superuser=False, make_first_user_superuser=True):
        from app.models import User
        return User(id="u1", email=email, hashed_password="x", full_name=full_name, is_active=True, is_superuser=True, scopes=["*"])

    async def fake_persist(db, *, user, raw_token, user_agent=None, ip=None):
        from app.models import RefreshToken
        return RefreshToken(id="rt1", user_id=user.id, token_hash="x", expires_at="2099-01-01T00:00:00Z")

    monkeypatch.setattr("app.services.auth_service.signup", fake_signup)
    monkeypatch.setattr("app.services.auth_service.persist_refresh_token", fake_persist)

    # Patch issue_token_pair để không cần RSA keys
    def fake_issue(user):
        return ("fake-access-token", "fake-refresh-token", 900)
    monkeypatch.setattr("app.services.auth_service.issue_token_pair", fake_issue)

    r = client.post("/auth/signup", json={"email": "u@e.com", "password": "password123"})
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"] == "fake-access-token"
    assert body["refresh_token"] == "fake-refresh-token"
    assert body["token_type"] == "Bearer"

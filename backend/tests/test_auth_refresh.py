import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import backend.core.db as db_module
from backend.core.rate_limit import REFRESH_LIMIT, limiter
from backend.main import app
from backend.models.refresh_token import RefreshToken


def _extract_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    data = cast(dict[str, Any], payload.get("data", payload))
    return data


@pytest.fixture(autouse=True)
def reset_rate_limits() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    test_db_path = tmp_path / "test_auth_refresh.db"
    test_db_url = f"sqlite:///{test_db_path}"

    previous_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_db_url

    original_engine = db_module.engine
    test_engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    db_module.engine = test_engine

    def override_get_session() -> Iterator[Session]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[db_module.get_session] = override_get_session

    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(db_module.get_session, None)
        SQLModel.metadata.drop_all(test_engine)
        test_engine.dispose()
        db_module.engine = original_engine
        if previous_db_url is not None:
            os.environ["DATABASE_URL"] = previous_db_url
        else:
            os.environ.pop("DATABASE_URL", None)
        if test_db_path.exists():
            test_db_path.unlink()


def test_refresh_token_hashed_and_tamper_rejected(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "StrongPass!234"

    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert signup_response.status_code == 200, signup_response.text
    tokens = _extract_tokens(cast(dict[str, Any], signup_response.json()))

    with Session(db_module.engine) as session:
        row = session.exec(select(RefreshToken)).first()
        assert row is not None
        assert row.token_hash != tokens["refresh_token"]
        assert row.jti is not None

    tampered = tokens["refresh_token"][:-1] + ("A" if tokens["refresh_token"][-1] != "A" else "B")
    tamper_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tampered},
    )
    assert tamper_response.status_code == 401
    assert tamper_response.headers.get("X-Request-ID")


def test_refresh_rotation_revokes_old_token(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "StrongPass!234"

    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert signup_response.status_code == 200, signup_response.text
    tokens = _extract_tokens(cast(dict[str, Any], signup_response.json()))

    first_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert first_refresh.status_code == 200, first_refresh.text
    first_tokens = _extract_tokens(cast(dict[str, Any], first_refresh.json()))
    assert first_tokens["refresh_token"] != tokens["refresh_token"]

    reuse_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reuse_response.status_code == 401

    # After reuse attempt, all tokens for the user are revoked, so the latest should fail too
    second_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_tokens["refresh_token"]},
    )
    assert second_refresh.status_code == 401


def test_reuse_triggers_global_revocation(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "StrongPass!234"

    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert signup_response.status_code == 200
    tokens = _extract_tokens(cast(dict[str, Any], signup_response.json()))

    second_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert second_login.status_code == 200
    _extract_tokens(cast(dict[str, Any], second_login.json()))

    # Manually revoke first token to simulate reuse detection
    with Session(db_module.engine) as session:
        row = session.exec(select(RefreshToken).order_by(RefreshToken.id.asc())).first()
        assert row is not None
        row.revoked = True
        row.revoked_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        user_id = row.user_id

    reuse_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reuse_response.status_code == 401

    with Session(db_module.engine) as session:
        rows = session.exec(select(RefreshToken).where(RefreshToken.user_id == user_id)).all()
        assert rows
        assert all(r.revoked for r in rows)


def test_refresh_rate_limit_returns_429(client: TestClient) -> None:
    bad_token = "bad-token"
    original_limit = REFRESH_LIMIT.limit
    REFRESH_LIMIT.limit = 1
    try:
        resp1 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": bad_token},
        )
        assert resp1.status_code in {401, 429}
        resp2 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": bad_token},
        )
        assert resp2.status_code == 429
        body = resp2.json()
        assert body.get("success") is False
        assert body.get("error", {}).get("code") == "rate_limited"
        assert resp2.headers.get("Retry-After")
        assert resp2.headers.get("X-Request-ID")
    finally:
        REFRESH_LIMIT.limit = original_limit

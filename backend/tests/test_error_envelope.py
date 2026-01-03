import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import backend.core.db as db_module
from backend.core import rate_limit
from backend.main import app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    test_db_path = tmp_path / "test_error.db"
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
    rate_limit.limiter.reset()

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
        rate_limit.limiter.reset()


def test_422_envelope_and_request_id(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert resp.headers.get("X-Request-ID")


def test_429_envelope_and_request_id(client: TestClient) -> None:
    original = rate_limit.REFRESH_LIMIT.limit
    rate_limit.REFRESH_LIMIT.limit = 1
    try:
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "bad"},
        )
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "bad"},
        )
        assert resp.status_code == 429
        body: dict[str, Any] = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "rate_limited"
        assert resp.headers.get("Retry-After") is not None
        assert resp.headers.get("X-Request-ID")
    finally:
        rate_limit.REFRESH_LIMIT.limit = original
        rate_limit.limiter.reset()

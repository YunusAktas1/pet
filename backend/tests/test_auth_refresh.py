import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import backend.core.db as db_module
from backend.main import app


def _extract_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    data = cast(dict[str, Any], payload.get("data", payload))
    return data


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

    second_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_tokens["refresh_token"]},
    )
    assert second_refresh.status_code == 200, second_refresh.text
    second_tokens = _extract_tokens(cast(dict[str, Any], second_refresh.json()))
    assert second_tokens["refresh_token"] != first_tokens["refresh_token"]

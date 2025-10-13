from __future__ import annotations

import os
from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import backend.core.db as db_module
from backend.main import app
from backend.models.user import User

TEST_DB_FILENAME = "test_pairs_messages.db"
TEST_DB_URL = f"sqlite:///./{TEST_DB_FILENAME}"


def _signup_login(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return cast(str, response.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_pet(client: TestClient, token: str, *, name: str) -> int:
    response = client.post(
        "/api/v1/pets",
        headers=_auth_headers(token),
        json={"name": name, "species": "cat", "gender": "male"},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _get_user_id(email: str) -> int:
    with Session(db_module.engine) as session:
        user_id = session.exec(select(User.id).where(User.email == email)).first()
        assert user_id is not None
        return int(user_id)


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    previous_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DB_URL
    original_engine = db_module.engine
    test_engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    db_module.engine = test_engine

    def override_get_session() -> Iterator[Session]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[db_module.get_session] = override_get_session
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(db_module.get_session, None)
    SQLModel.metadata.drop_all(test_engine)
    test_engine.dispose()
    if previous_db_url is not None:
        os.environ["DATABASE_URL"] = previous_db_url
    else:
        os.environ.pop("DATABASE_URL", None)
    db_module.engine = original_engine
    if os.path.exists(TEST_DB_FILENAME):
        os.remove(TEST_DB_FILENAME)


def test_pairs_and_messages_flow(client: TestClient) -> None:
    email_a = f"a_{uuid4().hex[:8]}@example.com"
    email_b = f"b_{uuid4().hex[:8]}@example.com"
    password = "Aa!123456"

    token_a = _signup_login(client, email_a, password)
    token_b = _signup_login(client, email_b, password)

    pet_a = _create_pet(client, token_a, name="A-Cat")
    pet_b = _create_pet(client, token_b, name="B-Cat")

    response = client.post(
        f"/api/v1/matches/{pet_b}/decision",
        headers=_auth_headers(token_a),
        json={"decision": "liked"},
    )
    assert response.status_code == 200, response.text

    response = client.get(
        "/api/v1/pairs",
        headers=_auth_headers(token_a),
    )
    assert response.status_code == 200
    assert response.headers.get("X-Total-Count") == "0"
    assert response.json() == []

    response = client.post(
        f"/api/v1/matches/{pet_a}/decision",
        headers=_auth_headers(token_b),
        json={"decision": "liked"},
    )
    assert response.status_code == 200, response.text

    user_b_id = _get_user_id(email_b)

    response = client.get(
        "/api/v1/pairs",
        headers=_auth_headers(token_a),
    )
    assert response.status_code == 200
    assert response.headers.get("X-Total-Count") == "1"
    pairs = response.json()
    assert len(pairs) == 1
    pair_record = pairs[0]
    assert pair_record["other_user_id"] == user_b_id
    pair_id = pair_record["id"]

    response = client.post(
        f"/api/v1/matches/{pet_a}/decision",
        headers=_auth_headers(token_b),
        json={"decision": "liked"},
    )
    assert response.status_code == 200

    response = client.get(
        "/api/v1/pairs",
        headers=_auth_headers(token_a),
    )
    assert response.status_code == 200
    assert response.headers.get("X-Total-Count") == "1"

    response = client.post(
        "/api/v1/messages",
        headers=_auth_headers(token_a),
        json={"pair_id": pair_id, "body": "Hi there!"},
    )
    assert response.status_code == 200, response.text
    msg_one = response.json()
    assert msg_one["body"] == "Hi there!"

    response = client.post(
        "/api/v1/messages",
        headers=_auth_headers(token_b),
        json={"pair_id": pair_id, "body": "Hello!"},
    )
    assert response.status_code == 200, response.text

    response = client.get(
        "/api/v1/messages",
        headers=_auth_headers(token_a),
        params={"pair_id": pair_id},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Total-Count") == "2"
    messages = response.json()
    assert [m["body"] for m in messages] == ["Hi there!", "Hello!"]

    response = client.get(
        "/api/v1/messages",
        headers=_auth_headers(token_a),
        params={"pair_id": pair_id, "limit": 1, "offset": 1},
    )
    assert response.status_code == 200
    paged_messages = response.json()
    assert len(paged_messages) == 1
    assert paged_messages[0]["body"] == "Hello!"

    email_c = f"c_{uuid4().hex[:8]}@example.com"
    token_c = _signup_login(client, email_c, password)

    response = client.post(
        "/api/v1/messages",
        headers=_auth_headers(token_c),
        json={"pair_id": pair_id, "body": "Should fail"},
    )
    assert response.status_code == 403

    response = client.get(
        "/api/v1/messages",
        headers=_auth_headers(token_c),
        params={"pair_id": pair_id},
    )
    assert response.status_code == 403

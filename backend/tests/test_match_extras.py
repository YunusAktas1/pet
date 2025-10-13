from __future__ import annotations

import os
from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import backend.core.db as db_module
from backend.main import app

TEST_DB_FILENAME = "test_match_extras.db"
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


def test_match_pagination_delete_and_stats(client: TestClient) -> None:
    email_a = f"a_{uuid4().hex[:8]}@example.com"
    email_b = f"b_{uuid4().hex[:8]}@example.com"

    token_a = _signup_login(client, email_a, "Aa!123456")
    token_b = _signup_login(client, email_b, "Bb!123456")

    pet_ids: list[int] = []
    for idx in range(2):
        response = client.post(
            "/api/v1/pets",
            headers=_auth_headers(token_b),
            json={"name": f"Tom-{idx}", "species": "cat", "gender": "male"},
        )
        assert response.status_code == 200, response.text
        pet_ids.append(int(response.json()["id"]))

    for pet_id in pet_ids:
        response = client.post(
            f"/api/v1/matches/{pet_id}/decision",
            headers=_auth_headers(token_a),
            json={"decision": "liked"},
        )
        assert response.status_code == 200, response.text

    stats_response = client.get(
        "/api/v1/matches/stats",
        headers=_auth_headers(token_a),
    )
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()
    assert stats["liked"] >= 2
    assert {"liked", "passed", "undecided"} <= stats.keys()

    list_response = client.get(
        "/api/v1/matches",
        headers=_auth_headers(token_a),
        params={"decision": "liked", "limit": 1, "offset": 0},
    )
    assert list_response.status_code == 200, list_response.text
    assert list_response.headers.get("X-Total-Count") is not None
    first_page = list_response.json()
    assert len(first_page) == 1
    first_match_id = first_page[0]["target_pet_id"]

    list_response = client.get(
        "/api/v1/matches",
        headers=_auth_headers(token_a),
        params={"decision": "liked", "limit": 1, "offset": 1},
    )
    assert list_response.status_code == 200, list_response.text
    second_page = list_response.json()
    assert len(second_page) <= 1
    if second_page:
        assert second_page[0]["target_pet_id"] != first_match_id

    delete_response = client.delete(
        f"/api/v1/matches/{first_match_id}",
        headers=_auth_headers(token_a),
    )
    assert delete_response.status_code == 204, delete_response.text

    list_response = client.get(
        "/api/v1/matches",
        headers=_auth_headers(token_a),
        params={"decision": "liked"},
    )
    assert list_response.status_code == 200, list_response.text
    assert all(
        match["target_pet_id"] != first_match_id for match in list_response.json()
    )

    stats_response = client.get(
        "/api/v1/matches/stats",
        headers=_auth_headers(token_a),
    )
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()
    assert {"liked", "passed", "undecided"} <= stats.keys()

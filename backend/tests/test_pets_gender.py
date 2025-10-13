import os
from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import backend.core.db as db_module
from backend.main import app
from backend.models.pet import Gender

TEST_DB_FILENAME = "test_pets_gender.db"
TEST_DB_URL = f"sqlite:///./{TEST_DB_FILENAME}"


def _signup(client: TestClient, email: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    data = cast(dict[str, str], response.json())
    return data["access_token"]


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


def test_create_pet_includes_gender(client: TestClient) -> None:
    password = "StrongPass123$"
    email = f"{uuid4().hex}@example.com"

    _signup(client, email, password)
    token = _login(client, email, password)

    response = client.post(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Max",
            "species": "dog",
            "gender": Gender.male.value,
        },
    )
    assert response.status_code == 200, response.text
    pet_payload = response.json()
    assert pet_payload["gender"] == Gender.male.value

    list_response = client.get(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    pets = list_response.json()
    assert any(p["gender"] == Gender.male.value for p in pets)

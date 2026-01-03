import os
from collections.abc import Iterator
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import backend.core.db as db_module
from backend.main import app
from backend.models.pet import Gender

TEST_DB_FILENAME = "test_pagination.db"
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
    payload = cast(dict[str, Any], response.json())
    data = cast(dict[str, Any], payload.get("data", payload))
    return cast(str, data["access_token"])


def _create_pet(
    client: TestClient,
    token: str,
    *,
    name: str,
    species: str,
    gender: Gender,
) -> None:
    response = client.post(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "species": species,
            "gender": gender.value,
        },
    )
    assert response.status_code == 200, response.text


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


def test_pets_pagination_and_filters(client: TestClient) -> None:
    password = "StrongPass123$"
    email = f"{uuid4().hex}@example.com"

    _signup(client, email, password)
    token = _login(client, email, password)

    pet_payloads = [
        ("Whiskers", "cat", Gender.male),
        ("Bella", "cat", Gender.female),
        ("Rex", "dog", Gender.male),
        ("Milo", "dog", Gender.unknown),
    ]
    for name, species, gender in pet_payloads:
        _create_pet(client, token, name=name, species=species, gender=gender)

    list_response = client.get(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 1, "page_size": 2},
    )
    assert list_response.status_code == 200, list_response.text
    page_one = list_response.json()
    assert len(page_one) == 2
    first_ids = {pet["id"] for pet in page_one}

    list_response = client.get(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 2, "page_size": 2},
    )
    assert list_response.status_code == 200, list_response.text
    page_two = list_response.json()
    assert len(page_two) == 2
    second_ids = {pet["id"] for pet in page_two}
    assert first_ids.isdisjoint(second_ids)

    cat_response = client.get(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
        params={"species": "cat"},
    )
    assert cat_response.status_code == 200, cat_response.text
    cats = cat_response.json()
    assert cats
    assert all(p["species"] == "cat" for p in cats)

    male_response = client.get(
        "/api/v1/pets",
        headers={"Authorization": f"Bearer {token}"},
        params={"gender": "male"},
    )
    assert male_response.status_code == 200, male_response.text
    male_pets = male_response.json()
    assert male_pets
    assert all(p["gender"] == Gender.male.value for p in male_pets)


def test_matches_pagination(client: TestClient) -> None:
    password = "StrongPass123$"
    owner_email = f"owner-{uuid4().hex}@example.com"
    other_email = f"other-{uuid4().hex}@example.com"

    _signup(client, owner_email, password)
    _signup(client, other_email, password)

    owner_token = _login(client, owner_email, password)
    other_token = _login(client, other_email, password)

    for index in range(4):
        _create_pet(
            client,
            other_token,
            name=f"Target {index}",
            species="cat",
            gender=Gender.male,
        )

    generate_response = client.post(
        "/api/v1/matches/generate",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"limit": 10},
    )
    assert generate_response.status_code == 200, generate_response.text
    generated = generate_response.json()
    assert generated["created"] >= 3

    list_response = client.get(
        "/api/v1/matches",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"limit": 2},
    )
    assert list_response.status_code == 200, list_response.text
    page_one = list_response.json()
    assert page_one["limit"] == 2
    assert len(page_one["items"]) == 2
    first_ids = {m["id"] for m in page_one["items"]}
    assert page_one["next_cursor"]

    list_response = client.get(
        "/api/v1/matches",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"limit": 2, "cursor": page_one["next_cursor"]},
    )
    assert list_response.status_code == 200, list_response.text
    page_two = list_response.json()
    assert len(page_two["items"]) >= 1
    second_ids = {m["id"] for m in page_two["items"]}
    assert first_ids.isdisjoint(second_ids)

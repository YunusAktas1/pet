import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import backend.core.db as db_module
from backend.core.config import settings
from backend.main import app


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
    data = cast(dict[str, Any], response.json())
    return cast(str, data["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_pet(client: TestClient, token: str, name: str = "Zoe") -> int:
    response = client.post(
        "/api/v1/pets",
        headers=_auth_headers(token),
        json={"name": name, "species": "cat"},
    )
    assert response.status_code == 200, response.text
    data = cast(dict[str, Any], response.json())
    return cast(int, data["id"])


def _upload_photo(
    client: TestClient,
    token: str,
    pet_id: int,
    *,
    filename: str,
    content: bytes,
    content_type: str = "image/jpeg",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/pets/{pet_id}/photos",
        headers=_auth_headers(token),
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    test_db_path = tmp_path / "test_photos.db"
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

    previous_media_dir = settings.MEDIA_DIR
    test_media_dir = str(tmp_path / "media")
    settings.MEDIA_DIR = test_media_dir

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.MEDIA_DIR = previous_media_dir
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
        media_path = Path(test_media_dir)
        if media_path.exists():
            shutil.rmtree(media_path, ignore_errors=True)


def test_upload_and_primary_autoset(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "SecurePass!234"
    _signup(client, email, password)
    token = _login(client, email, password)
    pet_id = _create_pet(client, token)

    photo = _upload_photo(
        client,
        token,
        pet_id,
        filename="first.jpg",
        content=b"\xff\xd8\xff\xdb\x00",
    )
    assert photo["is_primary"] is True
    assert photo["url"].startswith(settings.MEDIA_BASE_URL)

    pets_response = client.get("/api/v1/pets", headers=_auth_headers(token))
    assert pets_response.status_code == 200, pets_response.text
    assert pets_response.headers.get("X-Total-Count") == "1"
    pets = cast(list[dict[str, Any]], pets_response.json())
    assert pets
    pet_payload = pets[0]
    assert pet_payload["primary_photo_url"] == photo["url"]
    assert len(pet_payload["photos"]) == 1
    assert pet_payload["photos"][0]["is_primary"] is True


def test_primary_switch_and_delete(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "SecurePass!234"
    _signup(client, email, password)
    token = _login(client, email, password)
    pet_id = _create_pet(client, token)

    first = _upload_photo(
        client,
        token,
        pet_id,
        filename="first.jpg",
        content=b"\xff\xd8\xff\xdb\x00",
    )
    second = _upload_photo(
        client,
        token,
        pet_id,
        filename="second.jpg",
        content=b"\xff\xd8\xff\x00\x01",
    )

    make_primary = client.post(
        f"/api/v1/photos/{second['id']}/primary",
        headers=_auth_headers(token),
    )
    assert make_primary.status_code == 200, make_primary.text
    payload = cast(dict[str, Any], make_primary.json())
    assert payload["id"] == second["id"]
    assert payload["is_primary"] is True

    delete_response = client.delete(
        f"/api/v1/photos/{second['id']}",
        headers=_auth_headers(token),
    )
    assert delete_response.status_code == 204, delete_response.text

    photo_list = client.get(
        f"/api/v1/pets/{pet_id}/photos",
        headers=_auth_headers(token),
    )
    assert photo_list.status_code == 200, photo_list.text
    assert photo_list.headers.get("X-Total-Count") == "1"
    photos = cast(list[dict[str, Any]], photo_list.json())
    assert len(photos) == 1
    assert photos[0]["id"] == first["id"]
    assert photos[0]["is_primary"] is True

    pets_response = client.get("/api/v1/pets", headers=_auth_headers(token))
    assert pets_response.status_code == 200, pets_response.text
    pet_payload = cast(list[dict[str, Any]], pets_response.json())[0]
    assert pet_payload["primary_photo_url"] == photos[0]["url"]


def test_list_with_total_count_header(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "SecurePass!234"
    _signup(client, email, password)
    token = _login(client, email, password)
    pet_id = _create_pet(client, token)

    for idx in range(3):
        _upload_photo(
            client,
            token,
            pet_id,
            filename=f"photo_{idx}.jpg",
            content=b"\xff\xd8\xff" + bytes([idx]),
        )

    response = client.get(
        f"/api/v1/pets/{pet_id}/photos",
        headers=_auth_headers(token),
        params={"limit": 2, "offset": 1},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("X-Total-Count") == "3"
    photos = cast(list[dict[str, Any]], response.json())
    assert len(photos) == 2


def test_validation_rejects_big_or_bad_mime(client: TestClient) -> None:
    email = f"{uuid4().hex}@example.com"
    password = "SecurePass!234"
    _signup(client, email, password)
    token = _login(client, email, password)
    pet_id = _create_pet(client, token)

    big_content = b"x" * (settings.PHOTO_MAX_BYTES + 1)
    too_big = client.post(
        f"/api/v1/pets/{pet_id}/photos",
        headers=_auth_headers(token),
        files={"file": ("huge.jpg", big_content, "image/jpeg")},
    )
    assert too_big.status_code == 413, too_big.text

    bad_mime = client.post(
        f"/api/v1/pets/{pet_id}/photos",
        headers=_auth_headers(token),
        files={"file": ("not_image.txt", b"hello", "text/plain")},
    )
    assert bad_mime.status_code == 400, bad_mime.text

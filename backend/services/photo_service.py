from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import cast
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import desc, func
from sqlalchemy.sql.schema import Table
from sqlmodel import Session, select

from backend.core.config import settings
from backend.models.pet import Pet
from backend.models.photo import Photo

CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming large files
CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
PHOTO_TABLE = cast(Table, Photo.__table__)  # type: ignore[attr-defined]


def ensure_media_dir() -> Path:
    media_path = Path(settings.MEDIA_DIR)
    media_path.mkdir(parents=True, exist_ok=True)
    return media_path


def _build_photo_url(filename: str) -> str:
    base = settings.MEDIA_BASE_URL.rstrip("/")
    if not base:
        return f"/{filename}"
    return f"{base}/{filename}"


def _validate_pet_exists(session: Session, pet_id: int) -> Pet:
    pet = session.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="pet not found",
        )
    return pet


def save_photo(session: Session, pet_id: int, file: UploadFile) -> Photo:
    pet = _validate_pet_exists(session, pet_id)
    pet_identifier = pet.id
    if pet_identifier is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pet missing identifier",
        )

    content_type = (file.content_type or "").lower()
    if content_type not in settings.PHOTO_ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported photo type",
        )

    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported photo type",
        )
    media_path = ensure_media_dir()
    unique_name = f"{pet_id}_{uuid4().hex}{extension}"
    destination = media_path / unique_name

    size = 0
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.PHOTO_MAX_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="photo too large",
                    )
                buffer.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    photo = Photo(
        pet_id=pet_identifier,
        filename=unique_name,
        mime_type=content_type,
        size_bytes=size,
        url=_build_photo_url(unique_name),
    )

    existing_primary = session.exec(
        select(PHOTO_TABLE.c.id)
        .where(
            PHOTO_TABLE.c.pet_id == pet_identifier,
            PHOTO_TABLE.c.is_primary.is_(True),
        )
        .limit(1)
    ).first()
    if existing_primary is None:
        photo.is_primary = True

    session.add(photo)
    try:
        session.commit()
    except Exception:
        session.rollback()
        destination.unlink(missing_ok=True)
        raise
    session.refresh(photo)
    return photo


def list_photos(
    session: Session,
    pet_id: int,
    limit: int,
    offset: int,
) -> tuple[list[Photo], int]:
    _validate_pet_exists(session, pet_id)

    total_result = session.exec(
        select(func.count(PHOTO_TABLE.c.id)).where(PHOTO_TABLE.c.pet_id == pet_id)
    )
    total_count = int(total_result.first() or 0)

    statement = (
        select(Photo)
        .where(PHOTO_TABLE.c.pet_id == pet_id)
        .order_by(desc(PHOTO_TABLE.c.created_at))
        .offset(offset)
        .limit(limit)
    )
    photos = list(session.exec(statement).all())
    return photos, total_count


def _ensure_owner(pet: Pet, current_user_id: int) -> None:
    if pet.owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to modify this pet photo",
        )


def _reset_primary(
    session: Session,
    pet_id: int,
    exclude_photo_ids: Iterable[int] | None = None,
) -> None:
    excluded_ids: tuple[int, ...] | None = (
        tuple(exclude_photo_ids) if exclude_photo_ids else None
    )
    statement = select(Photo).where(
        PHOTO_TABLE.c.pet_id == pet_id,
        PHOTO_TABLE.c.is_primary.is_(True),
    )
    if excluded_ids:
        statement = statement.where(PHOTO_TABLE.c.id.notin_(excluded_ids))
    for other in session.exec(statement):
        if other.is_primary:
            other.is_primary = False


def delete_photo(session: Session, current_user_id: int, photo_id: int) -> None:
    photo = session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="photo not found",
        )

    pet = _validate_pet_exists(session, photo.pet_id)
    _ensure_owner(pet, current_user_id)
    pet_identifier = pet.id
    if pet_identifier is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pet missing identifier",
        )

    was_primary = photo.is_primary
    filename = photo.filename

    session.delete(photo)
    session.flush()

    if was_primary:
        replacement = session.exec(
            select(Photo)
            .where(PHOTO_TABLE.c.pet_id == pet_identifier)
            .order_by(desc(PHOTO_TABLE.c.created_at))
            .limit(1)
        ).first()
        if replacement and replacement.id is not None:
            _reset_primary(
                session,
                pet_identifier,
                exclude_photo_ids=[replacement.id],
            )
            replacement.is_primary = True

    session.commit()

    media_path = Path(settings.MEDIA_DIR)
    with suppress(OSError):  # pragma: no cover - best effort cleanup
        (media_path / filename).unlink(missing_ok=True)


def set_primary(
    session: Session,
    current_user_id: int,
    photo_id: int,
) -> Photo:
    photo = session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="photo not found",
        )

    pet = _validate_pet_exists(session, photo.pet_id)
    _ensure_owner(pet, current_user_id)
    pet_identifier = pet.id
    if pet_identifier is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pet missing identifier",
        )
    photo_identifier = photo.id
    if photo_identifier is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="photo missing identifier",
        )

    _reset_primary(session, pet_identifier, exclude_photo_ids=[photo_identifier])
    photo.is_primary = True

    session.add(photo)
    session.commit()
    session.refresh(photo)
    return photo

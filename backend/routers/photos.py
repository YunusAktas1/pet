from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlmodel import Session

from backend.core.db import get_session
from backend.core.pagination import decode_cursor, parse_cursor_datetime, parse_limit
from backend.models.pet import Pet
from backend.models.user import User
from backend.routers.pets import get_current_user
from backend.schemas.photo import PhotoOut
from backend.services.photo_service import (
    delete_photo,
    list_photos,
    save_photo,
    set_primary,
)

router = APIRouter(tags=["photos"])

SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _require_user_id(user: User) -> int:
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )
    return user.id


def _assert_pet_owner(session: Session, pet_id: int, user_id: int) -> Pet:
    pet = session.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="pet not found",
        )
    if pet.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to manage photos for this pet",
        )
    return pet


@router.post(
    "/pets/{pet_id}/photos",
    response_model=PhotoOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_pet_photo(
    pet_id: int,
    session: SessionDep,
    current: CurrentUserDep,
    file: UploadFile = File(...),
) -> PhotoOut:
    user_id = _require_user_id(current)
    _assert_pet_owner(session, pet_id, user_id)
    photo = save_photo(session, pet_id=pet_id, file=file)
    return PhotoOut.model_validate(photo, from_attributes=True)


@router.get("/pets/{pet_id}/photos")
def get_pet_photos(
    pet_id: int,
    session: SessionDep,
    current: CurrentUserDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    user_id = _require_user_id(current)
    _assert_pet_owner(session, pet_id, user_id)

    parsed_limit = parse_limit(limit, default=20, max_limit=100)
    parsed_cursor = None
    if cursor:
        payload = decode_cursor(cursor)
        payload["created_at"] = parse_cursor_datetime(str(payload.get("created_at")))
        parsed_cursor = payload

    photos, next_cursor = list_photos(
        session,
        pet_id=pet_id,
        limit=parsed_limit,
        cursor=parsed_cursor,
    )
    return {
        "items": [PhotoOut.model_validate(photo, from_attributes=True) for photo in photos],
        "next_cursor": next_cursor,
        "limit": parsed_limit,
    }


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_pet_photo(
    photo_id: int,
    session: SessionDep,
    current: CurrentUserDep,
) -> None:
    user_id = _require_user_id(current)
    delete_photo(session, current_user_id=user_id, photo_id=photo_id)


@router.post("/photos/{photo_id}/primary", response_model=PhotoOut)
def mark_primary_photo(
    photo_id: int,
    session: SessionDep,
    current: CurrentUserDep,
) -> PhotoOut:
    user_id = _require_user_id(current)
    photo = set_primary(session, current_user_id=user_id, photo_id=photo_id)
    return PhotoOut.model_validate(photo, from_attributes=True)


from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import desc, func
from sqlalchemy.sql.schema import Table
from sqlmodel import Session, select

from backend.core.db import get_session
from backend.core.pagination import decode_cursor, encode_cursor, parse_cursor_datetime, parse_limit
from backend.core.security import decode_token
from backend.models.pet import Gender, Pet, PetCreate, PetOut
from backend.models.photo import Photo
from backend.models.user import User
from backend.schemas.photo import PhotoOut
from backend.services.photo_service import delete_photo, set_primary

router = APIRouter(prefix="/pets", tags=["pets"])
bearer = HTTPBearer()

SessionDep = Annotated[Session, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials, Depends(bearer)]


def get_current_user(creds: CredentialsDep, session: SessionDep) -> User:
    try:
        payload = decode_token(creds.credentials)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from err

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _require_user_id(user: User) -> int:
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )
    return user.id


def _get_owned_pet(session: Session, pet_id: int, owner_id: int) -> Pet:
    pet = session.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="pet not found",
        )
    if pet.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to access this pet",
        )
    return pet


def _serialize_pet(session: Session, pet: Pet) -> PetOut:
    if pet.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pet missing identifier",
        )
    pet_out = PetOut.model_validate(pet, from_attributes=True)
    pet_id = pet.id
    photo_table = cast(Table, Photo.__table__)  # type: ignore[attr-defined]
    photo_rows = session.exec(
        select(Photo)
        .where(photo_table.c.pet_id == pet_id)
        .order_by(desc(photo_table.c.created_at))
    ).all()
    pet_out.photos = [
        PhotoOut.model_validate(photo, from_attributes=True) for photo in photo_rows
    ]
    pet_out.primary_photo_url = next(
        (photo.url for photo in photo_rows if photo.is_primary),
        None,
    )
    return pet_out


@router.post("", response_model=PetOut)
def create_pet(
    payload: PetCreate,
    current: CurrentUserDep,
    session: SessionDep,
) -> Pet:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    pet = Pet(
        owner_id=current.id,
        name=payload.name,
        species=payload.species,
        gender=payload.gender or Gender.unknown,
        age=payload.age,
        bio=payload.bio,
    )

    try:
        session.add(pet)
        session.commit()
        session.refresh(pet)
    except Exception as err:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create pet",
        ) from err
    return pet


@router.get("")
def list_my_pets(
    current: CurrentUserDep,
    session: SessionDep,
    species: Annotated[str | None, Query()] = None,
    gender: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    user_id = _require_user_id(current)

    conditions = [Pet.owner_id == user_id]

    if species:
        conditions.append(Pet.species == species)

    gender_filter: Gender | None = None
    if gender:
        normalized = gender.lower()
        if normalized in {
            Gender.male.value,
            Gender.female.value,
            Gender.unknown.value,
        }:
            gender_filter = Gender(normalized)
    if gender_filter:
        conditions.append(Pet.gender == gender_filter)

    pet_table = cast(Table, Pet.__table__)  # type: ignore[attr-defined]

    parsed_limit = parse_limit(limit, default=20, max_limit=100)
    parsed_cursor = None
    if cursor:
        payload = decode_cursor(cursor)
        payload["created_at"] = parse_cursor_datetime(str(payload.get("created_at")))
        parsed_cursor = payload

    statement = select(Pet).where(*conditions)

    if parsed_cursor:
        cur_created = parsed_cursor.get("created_at")
        cur_id = parsed_cursor.get("id")
        if cur_created is not None and cur_id is not None:
            statement = statement.where(
                (pet_table.c.created_at < cur_created)
                | (
                    (pet_table.c.created_at == cur_created)
                    & (pet_table.c.id < int(cur_id))
                )
            )

    statement = statement.order_by(desc(pet_table.c.created_at), desc(pet_table.c.id))
    statement = statement.limit(parsed_limit + 1)

    pets = session.exec(statement).all()
    has_more = len(pets) > parsed_limit
    pets = pets[:parsed_limit]
    pet_ids = [pet.id for pet in pets if pet.id is not None]

    photos_by_pet: dict[int, list[Photo]] = {pet_id: [] for pet_id in pet_ids}
    if pet_ids:
        photo_table = cast(Table, Photo.__table__)  # type: ignore[attr-defined]
        photo_rows = session.exec(
            select(Photo)
            .where(photo_table.c.pet_id.in_(pet_ids))
            .order_by(
                photo_table.c.pet_id,
                desc(photo_table.c.created_at),
            )
        ).all()
        for photo in photo_rows:
            photos_by_pet.setdefault(photo.pet_id, []).append(photo)

    results: list[PetOut] = []
    for pet in pets:
        pet_out = PetOut.model_validate(pet, from_attributes=True)
        pet_photos = photos_by_pet.get(pet.id or 0, [])
        pet_out.photos = [
            PhotoOut.model_validate(photo, from_attributes=True) for photo in pet_photos
        ]
        pet_out.primary_photo_url = next(
            (photo.url for photo in pet_photos if photo.is_primary),
            None,
        )
        results.append(pet_out)

    next_cursor = None
    if has_more and pets:
        last = pets[-1]
        next_cursor = encode_cursor(
            {
                "created_at": last.created_at.isoformat(),
                "id": last.id,
            }
        )

    return {"items": results, "next_cursor": next_cursor, "limit": parsed_limit}


@router.get("/{pet_id}", response_model=PetOut)
def get_pet(
    pet_id: int,
    current: CurrentUserDep,
    session: SessionDep,
) -> PetOut:
    user_id = _require_user_id(current)
    pet = _get_owned_pet(session, pet_id, user_id)
    return _serialize_pet(session, pet)


@router.put("/{pet_id}", response_model=PetOut)
def update_pet(
    pet_id: int,
    payload: PetCreate,
    current: CurrentUserDep,
    session: SessionDep,
) -> PetOut:
    user_id = _require_user_id(current)
    pet = _get_owned_pet(session, pet_id, user_id)

    pet.name = payload.name
    pet.species = payload.species
    pet.gender = payload.gender or Gender.unknown
    pet.age = payload.age
    pet.bio = payload.bio

    try:
        session.add(pet)
        session.commit()
        session.refresh(pet)
    except Exception as err:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update pet",
        ) from err

    return _serialize_pet(session, pet)


@router.patch("/{pet_id}/primary_photo", response_model=PetOut)
def update_primary_photo(
    pet_id: int,
    photo_id: Annotated[int, Query(ge=1)],
    current: CurrentUserDep,
    session: SessionDep,
) -> PetOut:
    user_id = _require_user_id(current)
    _get_owned_pet(session, pet_id, user_id)
    set_primary(session, current_user_id=user_id, photo_id=photo_id)
    pet = _get_owned_pet(session, pet_id, user_id)
    return _serialize_pet(session, pet)


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet(
    pet_id: int,
    current: CurrentUserDep,
    session: SessionDep,
) -> None:
    user_id = _require_user_id(current)
    pet = _get_owned_pet(session, pet_id, user_id)

    photo_records = session.exec(select(Photo).where(Photo.pet_id == pet.id)).all()
    for photo in photo_records:
        if photo.id is not None:
            delete_photo(session, current_user_id=user_id, photo_id=photo.id)

    pet = _get_owned_pet(session, pet_id, user_id)
    try:
        session.delete(pet)
        session.commit()
    except Exception as err:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete pet",
        ) from err

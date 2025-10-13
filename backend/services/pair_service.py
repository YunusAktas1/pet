# mypy: ignore-errors
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlmodel import Session

from backend.models.match import Match, MatchDecision
from backend.models.pair import Pair
from backend.models.pet import Pet


def _sorted_users(a_user_id: int, b_user_id: int) -> tuple[int, int]:
    return (a_user_id, b_user_id) if a_user_id < b_user_id else (b_user_id, a_user_id)


def _pet_ids_for_owner(session: Session, owner_user_id: int) -> set[int]:
    stmt: Any = select(Pet.id).where(Pet.owner_id == owner_user_id)
    pet_ids = session.exec(stmt).scalars().all()
    return {int(pet_id) for pet_id in pet_ids if pet_id is not None}


def _liked_pet_ids(session: Session, owner_user_id: int) -> set[int]:
    stmt: Any = select(Match.target_pet_id).where(
        Match.owner_user_id == owner_user_id,
        Match.decision == MatchDecision.liked,
    )
    target_ids = session.exec(stmt).scalars().all()
    return {int(target_id) for target_id in target_ids if target_id is not None}


def upsert_pair_for_users(
    session: Session,
    a_user_id: int,
    b_user_id: int,
) -> Pair | None:
    if a_user_id == b_user_id:
        return None

    low, high = _sorted_users(a_user_id, b_user_id)
    existing_stmt: Any = (
        select(Pair).where(Pair.user_low_id == low).where(Pair.user_high_id == high)
    )
    existing = cast(Pair | None, session.exec(existing_stmt).first())
    if existing is not None:
        return existing

    pair = Pair(user_low_id=low, user_high_id=high)
    session.add(pair)
    session.commit()
    session.refresh(pair)
    return pair


def try_create_pair_on_mutual_like(
    session: Session,
    liker_user_id: int,
    target_pet_id: int,
) -> Pair | None:
    pet = session.get(Pet, target_pet_id)
    if pet is None or pet.owner_id == liker_user_id:
        return None

    target_owner_id = pet.owner_id

    liker_liked_targets = _liked_pet_ids(session, liker_user_id)
    target_owner_pets = _pet_ids_for_owner(session, target_owner_id)
    if not liker_liked_targets.intersection(target_owner_pets):
        return None

    target_liked_targets = _liked_pet_ids(session, target_owner_id)
    liker_pets = _pet_ids_for_owner(session, liker_user_id)
    if not target_liked_targets.intersection(liker_pets):
        return None

    return upsert_pair_for_users(
        session=session,
        a_user_id=liker_user_id,
        b_user_id=target_owner_id,
    )


def list_pairs_for_user(
    session: Session,
    user_id: int,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], int]:
    pairs_stmt: Any = select(Pair)
    pairs = cast(list[Pair], session.exec(pairs_stmt).scalars().all())
    filtered = [
        pair
        for pair in pairs
        if pair.user_low_id == user_id or pair.user_high_id == user_id
    ]
    filtered.sort(key=lambda pair: pair.created_at, reverse=True)
    total_count = len(filtered)

    page = filtered[offset : offset + limit]

    items: list[dict[str, object]] = []
    for pair in page:
        other_user_id = (
            pair.user_high_id if pair.user_low_id == user_id else pair.user_low_id
        )
        items.append(
            {
                "id": pair.id,
                "other_user_id": other_user_id,
                "created_at": pair.created_at,
            }
        )
    return items, total_count

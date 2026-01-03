from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import desc, func
from backend.core.pagination import encode_cursor
from sqlalchemy.sql.schema import Table
from sqlmodel import Session, select

from backend.models.match import Match, MatchDecision
from backend.models.pet import Gender, Pet
from backend.services.pair_service import try_create_pair_on_mutual_like


def decide_match(
    owner_user_id: int,
    target_pet_id: int,
    decision: MatchDecision,
    session: Session,
) -> Match:
    match = ensure_match_for_decision(
        owner_user_id=owner_user_id,
        target_pet_id=target_pet_id,
        session=session,
    )

    if match.decision != decision:
        match.decision = decision
        session.flush()

    session.commit()
    session.refresh(match)

    if decision == MatchDecision.liked:
        try_create_pair_on_mutual_like(
            session=session,
            liker_user_id=owner_user_id,
            target_pet_id=target_pet_id,
        )

    return match


def delete_match(
    owner_user_id: int,
    target_pet_id: int,
    session: Session,
) -> bool:
    statement = select(Match).where(
        Match.owner_user_id == owner_user_id,
        Match.target_pet_id == target_pet_id,
    )
    match = session.exec(statement).first()
    if match is None:
        return False
    session.delete(match)
    session.commit()
    return True


def count_by_decision(owner_user_id: int, session: Session) -> dict[str, int]:
    match_table = cast(Table, Match.__table__)  # type: ignore[attr-defined]
    statement = (
        select(match_table.c.decision, func.count())
        .where(match_table.c.owner_user_id == owner_user_id)
        .group_by(match_table.c.decision)
    )
    counts = {decision.value: 0 for decision in MatchDecision}
    for decision_value, total in session.exec(statement):
        key = (
            decision_value.value
            if isinstance(decision_value, MatchDecision)
            else str(decision_value)
        )
        counts[key] = int(total)
    return counts



def list_matches(
    owner_user_id: int,
    *,
    session: Session,
    limit: int,
    cursor: dict | None = None,
    decision: MatchDecision | None = None,
) -> tuple[list[Match], str | None]:
    match_table = cast(Table, Match.__table__)  # type: ignore[attr-defined]
    pet_table = cast(Table, Pet.__table__)  # type: ignore[attr-defined]

    statement = select(Match).join(
        pet_table,
        match_table.c.target_pet_id == pet_table.c.id,
    )
    statement = statement.where(match_table.c.owner_user_id == owner_user_id)
    if decision is not None:
        statement = statement.where(match_table.c.decision == decision)

    if cursor:
        cur_created = cursor.get("created_at")
        cur_id = cursor.get("id")
        if cur_created is not None and cur_id is not None:
            statement = statement.where(
                (match_table.c.created_at < cur_created)
                | (
                    (match_table.c.created_at == cur_created)
                    & (match_table.c.id < int(cur_id))
                )
            )

    statement = statement.order_by(desc(match_table.c.created_at), desc(match_table.c.id))
    statement = statement.limit(limit + 1)
    records = list(session.exec(statement).all())

    has_more = len(records) > limit
    items = records[:limit]
    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(
            {
                "created_at": last.created_at.isoformat(),
                "id": last.id,
            }
        )

    return items, next_cursor


def ensure_match_for_decision(
    owner_user_id: int,
    target_pet_id: int,
    session: Session,
) -> Match:
    pet = session.exec(select(Pet).where(Pet.id == target_pet_id)).first()
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target pet not found.",
        )
    if pet.owner_id == owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot match against own pet.",
        )

    existing = session.exec(
        select(Match).where(
            Match.owner_user_id == owner_user_id,
            Match.target_pet_id == target_pet_id,
        )
    ).first()
    if existing:
        return existing

    match = Match(
        owner_user_id=owner_user_id,
        target_pet_id=target_pet_id,
        decision=MatchDecision.undecided,
    )
    session.add(match)
    session.flush()
    session.refresh(match)
    return match


def generate_matches(
    current_user_id: int,
    *,
    species: str | None,
    gender: str | None,
    limit: int,
    session: Session,
) -> tuple[int, list[Pet]]:
    if limit <= 0:
        return 0, []

    existing_result = session.exec(
        select(Match.target_pet_id).where(Match.owner_user_id == current_user_id)
    )
    existing_ids = {
        match_id for match_id in existing_result.all() if match_id is not None
    }

    statement = select(Pet).where(Pet.owner_id != current_user_id)
    if species:
        statement = statement.where(Pet.species == species)
    if gender:
        gender_enum = Gender(gender)
        statement = statement.where(Pet.gender == gender_enum)
    if existing_ids:
        statement = statement.where(Pet.id.notin_(existing_ids))  # type: ignore[union-attr]
    statement = statement.limit(limit)

    candidates_result: Sequence[Pet] = session.exec(statement).all()
    candidates = list(candidates_result)

    if not candidates:
        return 0, []

    created = 0
    now = datetime.now(timezone.utc)
    for pet in candidates:
        pet_id = pet.id
        if pet_id is None or pet_id in existing_ids:
            continue
        match = Match(
            owner_user_id=current_user_id,
            target_pet_id=pet_id,
            decision=MatchDecision.undecided,
            created_at=now,
        )
        session.add(match)
        existing_ids.add(pet_id)
        created += 1

    if created:
        session.commit()

    return created, candidates

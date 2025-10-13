from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, SQLModel

from backend.core.db import get_session
from backend.models.match import MatchDecision, MatchOut
from backend.models.pet import Gender, PetOut
from backend.models.user import User
from backend.routers.pets import get_current_user
from backend.services.match_service import (
    count_by_decision,
    decide_match,
    delete_match,
    generate_matches,
    list_matches,
)

router = APIRouter(prefix="/matches", tags=["matches"])

SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


class GenerateRequest(SQLModel):
    species: str | None = None
    gender: str | None = None
    limit: int = 10


class GenerateResponse(SQLModel):
    created: int
    candidates: list[PetOut]


@router.post("/generate", response_model=GenerateResponse)
def generate(
    payload: GenerateRequest,
    session: SessionDep,
    current: CurrentUserDep,
) -> GenerateResponse:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    if not 1 <= payload.limit <= 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 50",
        )

    gender_value = payload.gender
    if gender_value:
        try:
            Gender(gender_value)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid gender",
            ) from err

    created, candidates = generate_matches(
        current_user_id=current.id,
        species=payload.species,
        gender=gender_value,
        limit=payload.limit,
        session=session,
    )
    return GenerateResponse(
        created=created,
        candidates=[
            PetOut.model_validate(candidate, from_attributes=True)
            for candidate in candidates
        ],
    )


class DecisionIn(SQLModel):
    decision: MatchDecision


@router.post("/{target_pet_id}/decision", response_model=MatchOut)
def set_decision(
    target_pet_id: int,
    payload: DecisionIn,
    session: SessionDep,
    current: CurrentUserDep,
) -> MatchOut:
    """Apply a decision to a match, auto-creating it if missing."""
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    try:
        match = decide_match(
            owner_user_id=current.id,
            target_pet_id=target_pet_id,
            decision=payload.decision,
            session=session,
        )
    except Exception as err:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to set decision",
        ) from err

    return MatchOut.model_validate(match, from_attributes=True)


@router.get("", response_model=list[MatchOut])
def list_my_matches(
    current: CurrentUserDep,
    session: SessionDep,
    response: Response,
    decision: Annotated[
        MatchDecision | None,
        Query(description="Filter by decision (liked, passed, undecided)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MatchOut]:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    total_count, matches = list_matches(
        owner_user_id=current.id,
        session=session,
        limit=limit,
        offset=offset,
        decision=decision,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return [MatchOut.model_validate(match, from_attributes=True) for match in matches]


@router.delete("/{target_pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_match(
    target_pet_id: int,
    current: CurrentUserDep,
    session: SessionDep,
) -> None:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    deleted = delete_match(
        owner_user_id=current.id,
        target_pet_id=target_pet_id,
        session=session,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="match not found",
        )


@router.get("/stats")
def match_stats(
    current: CurrentUserDep,
    session: SessionDep,
) -> dict[str, int]:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    counts = count_by_decision(
        owner_user_id=current.id,
        session=session,
    )
    return counts

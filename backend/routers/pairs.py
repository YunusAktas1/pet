from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from backend.core.db import get_session
from backend.core.pagination import decode_cursor, parse_cursor_datetime, parse_limit
from backend.models.pair import PairOut
from backend.models.user import User
from backend.routers.pets import get_current_user
from backend.services.pair_service import list_pairs_for_user

router = APIRouter(prefix="/pairs", tags=["pairs"])

SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("")
def list_my_pairs(
    current: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    parsed_limit = parse_limit(limit, default=20, max_limit=100)
    parsed_cursor = None
    if cursor:
        payload = decode_cursor(cursor)
        payload["created_at"] = parse_cursor_datetime(str(payload.get("created_at")))
        parsed_cursor = payload

    items, next_cursor = list_pairs_for_user(
        session=session,
        user_id=current.id,
        limit=parsed_limit,
        cursor=parsed_cursor,
    )
    return {
        "items": [PairOut(**item) for item in items],
        "next_cursor": next_cursor,
        "limit": parsed_limit,
    }

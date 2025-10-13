from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session

from backend.core.db import get_session
from backend.models.pair import PairOut
from backend.models.user import User
from backend.routers.pets import get_current_user
from backend.services.pair_service import list_pairs_for_user

router = APIRouter(prefix="/pairs", tags=["pairs"])

SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[PairOut])
def list_my_pairs(
    current: CurrentUserDep,
    session: SessionDep,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PairOut]:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    items, total_count = list_pairs_for_user(
        session=session,
        user_id=current.id,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return [PairOut(**item) for item in items]

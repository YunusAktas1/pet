from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, SQLModel

from backend.core.db import get_session
from backend.core.pagination import decode_cursor, parse_cursor_datetime, parse_limit
from backend.models.message import MessageOut
from backend.models.user import User
from backend.routers.pets import get_current_user
from backend.services.message_service import list_messages, send_message

router = APIRouter(prefix="/messages", tags=["messages"])

SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


class MessageCreate(SQLModel):
    pair_id: int
    body: str


@router.post("", response_model=MessageOut)
def create_message(
    payload: MessageCreate,
    current: CurrentUserDep,
    session: SessionDep,
) -> MessageOut:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    message = send_message(
        pair_id=payload.pair_id,
        sender_user_id=current.id,
        body=payload.body,
        session=session,
    )
    return MessageOut.model_validate(message, from_attributes=True)


@router.get("")
def list_pair_messages(
    pair_id: Annotated[int, Query()],
    current: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    parsed_limit = parse_limit(limit, default=50, max_limit=100)
    parsed_cursor = None
    if cursor:
        payload = decode_cursor(cursor)
        payload["created_at"] = parse_cursor_datetime(str(payload.get("created_at")))
        parsed_cursor = payload

    messages, next_cursor = list_messages(
        pair_id=pair_id,
        requester_user_id=current.id,
        limit=parsed_limit,
        cursor=parsed_cursor,
        session=session,
    )
    return {
        "items": [MessageOut.model_validate(message, from_attributes=True) for message in messages],
        "next_cursor": next_cursor,
        "limit": parsed_limit,
    }

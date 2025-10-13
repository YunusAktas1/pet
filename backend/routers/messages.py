from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, SQLModel

from backend.core.db import get_session
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


@router.get("", response_model=list[MessageOut])
def list_pair_messages(
    pair_id: Annotated[int, Query()],
    current: CurrentUserDep,
    session: SessionDep,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MessageOut]:
    if current.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authenticated user missing identifier",
        )

    total_count, messages = list_messages(
        pair_id=pair_id,
        requester_user_id=current.id,
        limit=limit,
        offset=offset,
        session=session,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return [
        MessageOut.model_validate(message, from_attributes=True) for message in messages
    ]

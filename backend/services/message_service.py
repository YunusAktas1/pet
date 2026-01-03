from __future__ import annotations

from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, select
from sqlalchemy.sql.schema import Table
from sqlmodel import Session

from backend.core.pagination import encode_cursor
from backend.models.message import Message
from backend.models.pair import Pair


def _get_pair(pair_id: int, session: Session) -> Pair | None:
    return session.exec(select(Pair).where(Pair.id == pair_id)).scalars().first()


def _validate_participant(pair: Pair, user_id: int) -> None:
    if user_id not in {pair.user_low_id, pair.user_high_id}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of this pair.",
        )


def send_message(
    pair_id: int,
    sender_user_id: int,
    body: str,
    session: Session,
) -> Message:
    if not body or not body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message body cannot be empty.",
        )

    pair = _get_pair(pair_id, session)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pair not found.",
        )

    _validate_participant(pair, sender_user_id)

    message = Message(
        pair_id=pair_id,
        sender_user_id=sender_user_id,
        body=body.strip(),
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_messages(
    pair_id: int,
    requester_user_id: int,
    *,
    limit: int,
    cursor: dict | None,
    session: Session,
) -> tuple[list[Message], str | None]:
    pair = _get_pair(pair_id, session)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pair not found.",
        )
    _validate_participant(pair, requester_user_id)

    message_table = cast(
        Table,
        Message.__table__,  # type: ignore[attr-defined]
    )

    statement = select(Message).where(message_table.c.pair_id == pair_id)

    if cursor:
        cur_created = cursor.get("created_at")
        cur_id = cursor.get("id")
        if cur_created is not None and cur_id is not None:
            statement = statement.where(
                (message_table.c.created_at < cur_created)
                | (and_(message_table.c.created_at == cur_created, message_table.c.id < int(cur_id)))
            )

    statement = statement.order_by(desc(message_table.c.created_at), desc(message_table.c.id))
    statement = statement.limit(limit + 1)
    messages = list(session.exec(statement).scalars().all())

    has_more = len(messages) > limit
    page = messages[:limit]

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_cursor(
            {
                "created_at": last.created_at.isoformat(),
                "id": last.id,
            }
        )

    return page, next_cursor

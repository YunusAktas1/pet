from __future__ import annotations

from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import asc, func
from sqlalchemy.sql.schema import Table
from sqlmodel import Session, select

from backend.models.message import Message
from backend.models.pair import Pair


def _get_pair(pair_id: int, session: Session) -> Pair | None:
    return session.exec(select(Pair).where(Pair.id == pair_id)).first()


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
    offset: int,
    session: Session,
) -> tuple[int, list[Message]]:
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

    count_statement = (
        select(func.count())
        .select_from(message_table)
        .where(message_table.c.pair_id == pair_id)
    )
    total_result = session.exec(count_statement).one()
    total_count = int(
        total_result[0] if isinstance(total_result, tuple) else total_result
    )

    statement = (
        select(Message)
        .where(Message.pair_id == pair_id)
        .order_by(asc(message_table.c.created_at))
        .offset(offset)
        .limit(limit)
    )
    messages = list(session.exec(statement).all())
    return total_count, messages

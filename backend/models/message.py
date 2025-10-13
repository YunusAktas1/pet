from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pair_id: int = Field(
        foreign_key="pair.id",
        nullable=False,
        index=True,
    )
    sender_user_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        index=True,
    )
    body: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class MessageOut(SQLModel):
    id: int
    pair_id: int
    sender_user_id: int
    body: str
    created_at: datetime

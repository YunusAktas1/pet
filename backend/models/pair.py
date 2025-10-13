from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Pair(SQLModel, table=True):
    __tablename__ = "pair"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_pair_users"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_low_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    user_high_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class PairOut(SQLModel):
    id: int
    other_user_id: int
    created_at: datetime

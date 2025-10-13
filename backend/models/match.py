from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.types import Enum as SAEnum
from sqlmodel import Field, SQLModel


class MatchDecision(str, Enum):
    undecided = "undecided"
    liked = "liked"
    passed = "passed"


class Match(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(
        foreign_key="user.id",
        index=True,
        nullable=False,
    )
    target_pet_id: int = Field(
        foreign_key="pet.id",
        index=True,
        nullable=False,
    )
    decision: MatchDecision = Field(
        sa_column=Column(
            SAEnum(MatchDecision, name="matchdecision"),
            nullable=False,
            server_default="undecided",
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "target_pet_id",
            name="uq_match_owner_target",
        ),
    )


class MatchOut(SQLModel):
    id: int
    owner_user_id: int
    target_pet_id: int
    decision: MatchDecision
    created_at: datetime

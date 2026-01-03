from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False, foreign_key="user.id")

    token_hash: str = Field(index=True, unique=True, nullable=False, max_length=64)
    revoked: bool = Field(default=False, nullable=False)

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False, index=True)

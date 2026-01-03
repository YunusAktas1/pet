from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False, foreign_key="user.id")

    jti: str | None = Field(default=None, index=True, unique=True, max_length=64)
    token_hash: str = Field(index=True, unique=True, nullable=False, max_length=64)
    revoked: bool = Field(default=False, nullable=False)
    revoked_at: datetime | None = Field(default=None, nullable=True)
    replaced_by_jti: str | None = Field(default=None, nullable=True, max_length=64)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: datetime = Field(nullable=False, index=True)

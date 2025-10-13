from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, Integer, desc
from sqlmodel import Field, SQLModel


class Photo(SQLModel, table=True):
    __tablename__ = "photo"
    __table_args__ = (
        Index("ix_photo_pet_id_created_at_desc", "pet_id", desc("created_at")),
    )

    id: int | None = Field(default=None, primary_key=True)
    pet_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("pet.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    filename: str = Field(nullable=False, unique=True)
    mime_type: str = Field(nullable=False)
    size_bytes: int = Field(nullable=False)
    url: str = Field(nullable=False)
    is_primary: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column
from sqlalchemy.types import Enum as SQLEnum
from sqlmodel import Field, SQLModel

from backend.schemas.photo import PhotoOut


class Gender(str, Enum):
    unknown = "unknown"
    male = "male"
    female = "female"


class PetBase(SQLModel):
    name: str
    species: str
    gender: Gender = Field(default=Gender.unknown)
    age: int | None = None
    bio: str | None = None


class Pet(PetBase, table=True):
    __tablename__ = "pet"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    gender: Gender = Field(
        default=Gender.unknown,
        sa_column=Column(SQLEnum(Gender, name="gender"), nullable=False),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class PetCreate(PetBase):
    pass


class PetOut(PetBase):
    id: int
    owner_id: int
    primary_photo_url: str | None = None
    photos: list[PhotoOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}

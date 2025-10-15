from datetime import datetime

from sqlmodel import SQLModel


class PhotoOut(SQLModel):
    id: int
    pet_id: int
    url: str
    is_primary: bool
    created_at: datetime
    mime_type: str | None = None
    size_bytes: int | None = None

    model_config = {"from_attributes": True}

from datetime import datetime

from sqlmodel import SQLModel


class PhotoOut(SQLModel):
    id: int
    pet_id: int
    url: str
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}

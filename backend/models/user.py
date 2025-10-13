# C:\Dev\Yunus\backend\models\user.py
from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"
    # SQLAlchemy UniqueConstraint ile unique kısıt
    __table_args__ = (sa.UniqueConstraint("email", name="uq_user_email"),)

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

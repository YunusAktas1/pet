"""add refresh token table (placeholder)

Revision ID: 73fa27358f77
Revises:
Create Date: 2025-12-16 20:54:50.078440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "73fa27358f77"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op placeholder to anchor later revisions.
    pass


def downgrade() -> None:
    # No-op placeholder to anchor later revisions.
    pass

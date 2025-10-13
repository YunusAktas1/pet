"""add match table

Revision ID: b8e1801f77fb
Revises: 3a9b448a6be6
Create Date: 2025-10-08 11:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e1801f77fb"
down_revision: Union[str, Sequence[str], None] = "3a9b448a6be6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create match table."""
    op.create_table(
        "match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("target_pet_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["target_pet_id"], ["pet.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "target_pet_id",
            name="uq_match_owner_target",
        ),
    )
    op.create_index(
        "ix_match_owner_user_id",
        "match",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_match_target_pet_id",
        "match",
        ["target_pet_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop match table."""
    op.drop_index("ix_match_target_pet_id", table_name="match")
    op.drop_index("ix_match_owner_user_id", table_name="match")
    op.drop_table("match")

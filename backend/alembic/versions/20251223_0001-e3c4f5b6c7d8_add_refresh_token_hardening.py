"""add jti and revoke metadata to refresh_token

Revision ID: e3c4f5b6c7d8
Revises: d85408697a8c
Create Date: 2025-12-23 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3c4f5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d85408697a8c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_token", sa.Column("jti", sa.String(length=64), nullable=True))
    op.add_column("refresh_token", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "refresh_token",
        sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
    )
    op.create_index(op.f("ix_refresh_token_jti"), "refresh_token", ["jti"], unique=True)
    op.create_index(
        op.f("ix_refresh_token_revoked_at"),
        "refresh_token",
        ["revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_token_revoked_at"), table_name="refresh_token")
    op.drop_index(op.f("ix_refresh_token_jti"), table_name="refresh_token")
    op.drop_column("refresh_token", "replaced_by_jti")
    op.drop_column("refresh_token", "revoked_at")
    op.drop_column("refresh_token", "jti")

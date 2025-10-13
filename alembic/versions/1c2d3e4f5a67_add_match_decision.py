"""add match decision enum

Revision ID: 1c2d3e4f5a67
Revises: b8e1801f77fb
Create Date: 2025-10-08 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a67"
down_revision: Union[str, None] = "b8e1801f77fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    decision_enum = sa.Enum("undecided", "liked", "passed", name="matchdecision")
    decision_enum.create(bind, checkfirst=True)

    op.add_column(
        "match",
        sa.Column(
            "decision",
            decision_enum,
            nullable=False,
            server_default="undecided",
        ),
    )

    op.create_index(
        "ix_match_owner_decision",
        "match",
        ["owner_user_id", "decision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_match_owner_decision", table_name="match")
    op.drop_column("match", "decision")

    bind = op.get_bind()
    decision_enum = sa.Enum("undecided", "liked", "passed", name="matchdecision")
    decision_enum.drop(bind, checkfirst=True)

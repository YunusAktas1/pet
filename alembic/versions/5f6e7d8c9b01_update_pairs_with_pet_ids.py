"""update pair table with pet ids

Revision ID: 5f6e7d8c9b01
Revises: 4d2a9f1b6cde
Create Date: 2025-10-08 13:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f6e7d8c9b01"
down_revision: Union[str, None] = "4d2a9f1b6cde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("message")
    op.drop_table("pair")

    op.create_table(
        "pair",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_a_id", sa.Integer(), nullable=False),
        sa.Column("user_b_id", sa.Integer(), nullable=False),
        sa.Column("pet_a_id", sa.Integer(), nullable=False),
        sa.Column("pet_b_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pet_a_id"], ["pet.id"]),
        sa.ForeignKeyConstraint(["pet_b_id"], ["pet.id"]),
        sa.ForeignKeyConstraint(["user_a_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["user_b_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_a_id",
            "user_b_id",
            "pet_a_id",
            "pet_b_id",
            name="uq_pair_ab",
        ),
    )
    op.create_index("ix_pair_user_a_id", "pair", ["user_a_id"], unique=False)
    op.create_index("ix_pair_user_b_id", "pair", ["user_b_id"], unique=False)
    op.create_index("ix_pair_pet_a_id", "pair", ["pet_a_id"], unique=False)
    op.create_index("ix_pair_pet_b_id", "pair", ["pet_b_id"], unique=False)

    op.create_table(
        "message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pair_id", sa.Integer(), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pair_id"], ["pair.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_pair_id", "message", ["pair_id"], unique=False)
    op.create_index(
        "ix_message_sender_user_id",
        "message",
        ["sender_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_message_created_at",
        "message",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_message_created_at", table_name="message")
    op.drop_index("ix_message_sender_user_id", table_name="message")
    op.drop_index("ix_message_pair_id", table_name="message")
    op.drop_table("message")

    op.drop_index("ix_pair_pet_b_id", table_name="pair")
    op.drop_index("ix_pair_pet_a_id", table_name="pair")
    op.drop_index("ix_pair_user_b_id", table_name="pair")
    op.drop_index("ix_pair_user_a_id", table_name="pair")
    op.drop_table("pair")

    op.create_table(
        "pair",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("user_a_id", sa.INTEGER(), nullable=False),
        sa.Column("user_b_id", sa.INTEGER(), nullable=False),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.ForeignKeyConstraint(["user_a_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["user_b_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_pair_users"),
    )
    op.create_index("ix_pair_user_b_id", "pair", ["user_b_id"], unique=False)
    op.create_index("ix_pair_user_a_id", "pair", ["user_a_id"], unique=False)

    op.create_table(
        "message",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("pair_id", sa.INTEGER(), nullable=False),
        sa.Column("sender_user_id", sa.INTEGER(), nullable=False),
        sa.Column("body", sa.VARCHAR(), nullable=False),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.ForeignKeyConstraint(["pair_id"], ["pair.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_created_at", "message", ["created_at"], unique=False)
    op.create_index(
        "ix_message_sender_user_id",
        "message",
        ["sender_user_id"],
        unique=False,
    )
    op.create_index("ix_message_pair_id", "message", ["pair_id"], unique=False)

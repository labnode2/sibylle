"""discussion: the messages under a prono, and their likes

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prono_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 500", name=op.f("ck_messages_body_length")
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_messages_membership_id_memberships"),
        ),
        sa.ForeignKeyConstraint(
            ["prono_id"], ["pronos.id"], name=op.f("fk_messages_prono_id_pronos")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index("ix_messages_prono_id_id", "messages", ["prono_id", "id"], unique=False)
    op.create_index(op.f("ix_messages_membership_id"), "messages", ["membership_id"], unique=False)
    op.create_table(
        "message_likes",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_message_likes_membership_id_memberships"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_likes_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", "membership_id", name=op.f("pk_message_likes")),
    )


def downgrade() -> None:
    op.drop_table("message_likes")
    op.drop_index(op.f("ix_messages_membership_id"), table_name="messages")
    op.drop_index("ix_messages_prono_id_id", table_name="messages")
    op.drop_table("messages")

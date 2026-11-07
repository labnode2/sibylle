"""sign-in through Keycloak: accounts tied to Keycloak's, sign-ins under way; no more passwords
nor e-mailed links (specs/002-keycloak-auth/data-model.md)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-07

No account is imported: production starts again from zero, and the accounts of development
databases keep no `keycloak_id` (hence no NOT NULL). The downgrade brings back, empty, what the
upgrade drops: the passwords and the links already sent are gone for good.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("keycloak_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(op.f("uq_accounts_keycloak_id"), "accounts", ["keycloak_id"])
    op.add_column(
        "accounts", sa.Column("identity_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_column("accounts", "password_hash")

    op.add_column("sessions", sa.Column("keycloak_sid", sa.Text(), nullable=True))
    op.create_index(op.f("ix_sessions_keycloak_sid"), "sessions", ["keycloak_sid"], unique=False)

    op.drop_index(op.f("ix_email_tokens_account_id"), table_name="email_tokens")
    op.drop_table("email_tokens")

    op.create_table(
        "sign_in_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("nonce", sa.Text(), nullable=False),
        sa.Column("code_verifier", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("next_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('login', 'signup', 'password')", name=op.f("ck_sign_in_attempts_action")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sign_in_attempts")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sign_in_attempts_token_hash")),
    )


def downgrade() -> None:
    op.drop_table("sign_in_attempts")

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')", name=op.f("ck_email_tokens_purpose")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_email_tokens_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_email_tokens_account_id"), "email_tokens", ["account_id"], unique=False
    )

    op.drop_index(op.f("ix_sessions_keycloak_sid"), table_name="sessions")
    op.drop_column("sessions", "keycloak_sid")

    op.add_column("accounts", sa.Column("password_hash", sa.Text(), nullable=True))
    op.drop_column("accounts", "identity_checked_at")
    op.drop_constraint(op.f("uq_accounts_keycloak_id"), "accounts", type_="unique")
    op.drop_column("accounts", "keycloak_id")

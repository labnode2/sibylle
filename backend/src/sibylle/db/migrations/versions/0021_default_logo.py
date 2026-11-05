"""organisations.logo: every newsroom has one, the default logo until the editor changes it

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-05
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from sibylle.domain.content import DEFAULT_LOGO

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A newsroom created without a logo kept JSON null rather than NULL: both get the default.
    op.execute(
        sa.text(
            "UPDATE organisations SET logo = CAST(:logo AS jsonb)"
            " WHERE logo IS NULL OR jsonb_typeof(logo) = 'null'"
        ).bindparams(logo=json.dumps(DEFAULT_LOGO))
    )
    op.alter_column("organisations", "logo", nullable=False)
    op.create_check_constraint(
        op.f("ck_organisations_logo"), "organisations", "jsonb_typeof(logo) = 'object'"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_organisations_logo"), "organisations", type_="check")
    op.alter_column("organisations", "logo", nullable=True)

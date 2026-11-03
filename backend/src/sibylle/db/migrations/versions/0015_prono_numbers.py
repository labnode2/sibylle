"""prono_numbers: each newsroom numbers its pronos, « PRONO N° 128 »

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organisations",
        sa.Column("last_prono_number", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("pronos", sa.Column("number", sa.Integer(), nullable=True))
    # The pronos already written take their numbers in the order they were written.
    op.execute(
        """
        UPDATE pronos SET number = numbered.n
        FROM (
            SELECT id, row_number() OVER (PARTITION BY org_id ORDER BY created_at, id) AS n
            FROM pronos
        ) AS numbered
        WHERE pronos.id = numbered.id
        """
    )
    op.execute(
        """
        UPDATE organisations SET last_prono_number = counted.n
        FROM (SELECT org_id, count(*) AS n FROM pronos GROUP BY org_id) AS counted
        WHERE organisations.id = counted.org_id
        """
    )
    op.alter_column("pronos", "number", nullable=False)
    op.create_unique_constraint(op.f("uq_pronos_org_id_number"), "pronos", ["org_id", "number"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_pronos_org_id_number"), "pronos", type_="unique")
    op.drop_column("pronos", "number")
    op.drop_column("organisations", "last_prono_number")

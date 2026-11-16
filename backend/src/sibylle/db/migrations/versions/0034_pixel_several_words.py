"""pixel_puzzles: several words for one drawing

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("words", "words_normalized"):
        op.add_column(
            "pixel_puzzles",
            sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    # The word each drawing had stays its only word.
    op.execute("UPDATE pixel_puzzles SET words = jsonb_build_array(word)")
    op.execute("UPDATE pixel_puzzles SET words_normalized = jsonb_build_array(word_normalized)")
    op.alter_column("pixel_puzzles", "words", nullable=False)
    op.alter_column("pixel_puzzles", "words_normalized", nullable=False)
    op.drop_column("pixel_puzzles", "word")
    op.drop_column("pixel_puzzles", "word_normalized")


def downgrade() -> None:
    op.add_column("pixel_puzzles", sa.Column("word", sa.Text(), nullable=True))
    op.add_column("pixel_puzzles", sa.Column("word_normalized", sa.Text(), nullable=True))
    op.execute("UPDATE pixel_puzzles SET word = words->>0, word_normalized = words_normalized->>0")
    op.alter_column("pixel_puzzles", "word", nullable=False)
    op.alter_column("pixel_puzzles", "word_normalized", nullable=False)
    op.drop_column("pixel_puzzles", "words")
    op.drop_column("pixel_puzzles", "words_normalized")

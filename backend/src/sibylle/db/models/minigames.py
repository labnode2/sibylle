import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from sibylle import clock
from sibylle.db.base import Base, new_id


class RunnerRun(Base):
    """A run of the ball's race: opened by the server (seed, start), finished with a score."""

    __tablename__ = "runner_runs"
    __table_args__ = (
        CheckConstraint("score >= 0", name="score"),
        CheckConstraint("duration_ms >= 0", name="duration_ms"),
        CheckConstraint("(finished_at IS NULL) = (score IS NULL)", name="finished_with_score"),
        Index("ix_runner_runs_org_id_week_start", "org_id", "week_start"),
        Index("ix_runner_runs_membership_id_week_start", "membership_id", "week_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    # The Monday (Paris) of the week the run counts for.
    week_start: Mapped[date]
    seed: Mapped[int]
    started_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    finished_at: Mapped[datetime | None]
    score: Mapped[int | None]
    duration_ms: Mapped[int | None]


class MinigamePayout(Base):
    """A period of a mini-game already paid: the job pays each one once."""

    __tablename__ = "minigame_payouts"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"), primary_key=True)
    game: Mapped[str] = mapped_column(Text, primary_key=True)
    period_key: Mapped[str] = mapped_column(Text, primary_key=True)
    paid_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class PixelPuzzle(Base):
    """A Pixel mystère drawing: queued, then active (one per newsroom), then finished."""

    __tablename__ = "pixel_puzzles"
    __table_args__ = (
        CheckConstraint("state IN ('queued', 'active', 'finished')", name="state"),
        Index(
            "uq_pixel_puzzles_org_id_active",
            "org_id",
            unique=True,
            postgresql_where=text("state = 'active'"),
        ),
        Index("ix_pixel_puzzles_org_id_state", "org_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    author_membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    drawing: Mapped[dict[str, Any]]
    word: Mapped[str] = mapped_column(Text)
    word_normalized: Mapped[str] = mapped_column(Text)
    # The pixels in the order they show, two bytes each, drawn once at creation.
    reveal_order: Mapped[bytes] = mapped_column(LargeBinary)
    revealed_count: Mapped[int] = mapped_column(default=0, server_default="0")
    state: Mapped[str] = mapped_column(Text, default="queued", server_default="queued")
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class PixelGuess(Base):
    """A guess; three a day (Paris) per member and drawing."""

    __tablename__ = "pixel_guesses"
    __table_args__ = (
        Index("ix_pixel_guesses_puzzle_id_membership_id_day", "puzzle_id", "membership_id", "day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    puzzle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pixel_puzzles.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    guess_normalized: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool]
    day: Mapped[date]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class PixelFind(Base):
    """Who found the word, in order, and what it paid (10, 7, 5, then 3 laurels)."""

    __tablename__ = "pixel_finds"
    __table_args__ = (
        UniqueConstraint("puzzle_id", "membership_id"),
        UniqueConstraint("puzzle_id", "rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    puzzle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pixel_puzzles.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    rank: Mapped[int]
    laurels: Mapped[int]
    found_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())

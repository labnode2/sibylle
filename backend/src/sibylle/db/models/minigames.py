import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
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

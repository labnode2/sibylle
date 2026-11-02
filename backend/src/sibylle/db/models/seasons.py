import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from sibylle import clock
from sibylle.db.base import Base, new_id


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("year", "name"),
        CheckConstraint("name IN ('spring', 'summer', 'autumn', 'winter')", name="name"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]


class SeasonClosure(Base):
    """A newsroom's season is closed. Written in the same transaction as the trophies and the
    balance resets, so that a closure never runs twice."""

    __tablename__ = "season_closures"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"), primary_key=True)
    season_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("seasons.id"), primary_key=True)
    closed_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class Trophy(Base):
    """The crystal ball engraved with a member's season score."""

    __tablename__ = "trophies"
    __table_args__ = (
        UniqueConstraint("membership_id", "season_id"),
        CheckConstraint("rank >= 1", name="rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    season_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("seasons.id"))
    score: Mapped[int]
    # Rank at the end of the season, ties sharing a rank.
    rank: Mapped[int]
    podium: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())

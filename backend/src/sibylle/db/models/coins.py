import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from sibylle import clock
from sibylle.db.base import Base
from sibylle.domain.coins import CoinKind

_KINDS = ", ".join(f"'{kind.value}'" for kind in CoinKind)


class CoinEntry(Base):
    """One movement of coins: Monday's conversion or a purchase. Append-only, like the ledger."""

    __tablename__ = "coin_entries"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_KINDS})", name="kind"),
        CheckConstraint("(kind = 'weekly') = (week_start IS NOT NULL)", name="week_start"),
        CheckConstraint("kind <> 'weekly' OR amount >= 0", name="weekly_amount"),
        # One conversion per member and per week, even when the worker runs twice.
        UniqueConstraint("membership_id", "week_start"),
        Index("ix_coin_entries_membership_id_id", "membership_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    kind: Mapped[str] = mapped_column(Text)
    # Effect on the member's coins.
    amount: Mapped[int]
    # The Monday of a conversion, and the gold laurels it converted.
    week_start: Mapped[date | None]
    gold: Mapped[int | None]
    # The catalog item of a purchase.
    item_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())

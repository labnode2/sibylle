import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sybille import clock
from sybille.db.base import Base
from sybille.domain.ledger import LedgerKind

_KINDS = ", ".join(f"'{kind.value}'" for kind in LedgerKind)


class LedgerEntry(Base):
    """One movement of laurels. Append-only: a correction adds reversing entries."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_KINDS})", name="kind"),
        Index("ix_ledger_entries_membership_id_created_at", "membership_id", "created_at"),
        Index("ix_ledger_entries_org_id_season_id_kind", "org_id", "season_id", "kind"),
        Index("ix_ledger_entries_settlement_id", "settlement_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    season_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("seasons.id"))
    kind: Mapped[str] = mapped_column(Text)
    # Effect on the balance and on the season score.
    amount: Mapped[int]
    score_delta: Mapped[int]
    prono_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pronos.id"))
    bet_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bets.id"))
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("settlements.id"))
    reverses_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ledger_entries.id")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("memberships.id"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())

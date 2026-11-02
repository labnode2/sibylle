import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sybille import clock
from sybille.db.base import Base, new_id

KINDS = "'choice', 'yes_no', 'number', 'date'"
STATES = "'proposed', 'rejected', 'scheduled', 'open', 'closed', 'resolved', 'cancelled'"


class Section(Base):
    """A newsroom's category of pronos (« rubrique »): Foot, Bureau, Projet…"""

    __tablename__ = "sections"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="name_length"),
        Index("uq_sections_org_id_name", "org_id", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    name: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    archived_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class Prono(Base):
    """A question the newsroom bets on, from its publication to its result."""

    __tablename__ = "pronos"
    __table_args__ = (
        CheckConstraint(f"kind IN ({KINDS})", name="kind"),
        CheckConstraint(f"state IN ({STATES})", name="state"),
        CheckConstraint("char_length(question) BETWEEN 5 AND 200", name="question_length"),
        CheckConstraint("base_gain >= 0", name="base_gain"),
        CheckConstraint("NOT open_ended OR kind = 'date'", name="open_ended_date"),
        CheckConstraint("open_ended = (closes_at IS NULL)", name="closing"),
        CheckConstraint("bet_count >= 0 AND pot >= 0", name="counters"),
        Index("ix_pronos_org_id_state_closes_at", "org_id", "state", "closes_at"),
        Index("ix_pronos_org_id_section_id", "org_id", "section_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"))
    kind: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(Text)
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uploads.id"))
    base_gain: Mapped[int]
    state: Mapped[str] = mapped_column(Text)
    open_ended: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    opens_at: Mapped[datetime | None]
    closes_at: Mapped[datetime | None]
    result_expected_at: Mapped[datetime | None]
    number_unit: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    validated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("memberships.id"))
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    # Every bet ever placed, replaced ones included: gives each new bet its rank.
    bet_count: Mapped[int] = mapped_column(default=0, server_default="0")
    pot: Mapped[int] = mapped_column(default=0, server_default="0")
    relaunch_count: Mapped[int] = mapped_column(default=0, server_default="0")
    result_number: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    result_date: Mapped[date | None]
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("memberships.id"))
    cancelled_at: Mapped[datetime | None]
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("memberships.id"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: clock.now(), onupdate=lambda: clock.now()
    )


class PronoOption(Base):
    __tablename__ = "prono_options"
    __table_args__ = (CheckConstraint("char_length(label) BETWEEN 1 AND 80", name="label_length"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    prono_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pronos.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(Text)
    position: Mapped[int]
    # NULL until the result is designated.
    is_correct: Mapped[bool | None]


class PronoEvent(Base):
    """The history of a prono: created, edited, opened, closed, relaunched, resolved…"""

    __tablename__ = "prono_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    prono_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pronos.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(Text)
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("memberships.id"))
    data: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class Bet(Base):
    """A member's answer to a prono (« pari »). Never changed once placed."""

    __tablename__ = "bets"
    __table_args__ = (
        CheckConstraint("stake >= 0", name="stake"),
        CheckConstraint("rank >= 1", name="rank"),
        CheckConstraint("outcome IN ('pending', 'won', 'lost', 'refunded')", name="outcome"),
        UniqueConstraint("prono_id", "rank"),
        # One active bet per member and prono; a replaced open-ended date bet steps aside.
        Index(
            "uq_bets_prono_id_membership_id_active",
            "prono_id",
            "membership_id",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    prono_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pronos.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"), index=True)
    option_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prono_options.id"))
    number_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    date_value: Mapped[date | None]
    stake: Mapped[int]
    rank: Mapped[int]
    placed_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    superseded_at: Mapped[datetime | None]
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bets.id"))
    outcome: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    payout: Mapped[int] = mapped_column(default=0, server_default="0")
    settled_at: Mapped[datetime | None]


class Settlement(Base):
    """One settlement of a prono: its resolution, a correction or its cancellation (J1).

    Every ledger entry it writes points to it. A correction or a cancellation reverses the
    previous settlement's entries and marks it with `reversed_by_id`.
    """

    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("kind IN ('resolution', 'correction', 'cancellation')", name="kind"),
        CheckConstraint("seq >= 1", name="seq"),
        UniqueConstraint("prono_id", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    prono_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pronos.id"))
    seq: Mapped[int]
    kind: Mapped[str] = mapped_column(Text)
    # The correct options or the real value, as designated.
    result: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    reversed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("settlements.id"))


class Report(Base):
    """A member's report about a prono: a wrong result or an unwelcome content."""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("kind IN ('result_error', 'content')", name="kind"),
        CheckConstraint("state IN ('open', 'resolved', 'dismissed')", name="state"),
        CheckConstraint("char_length(message) <= 500", name="message_length"),
        Index("ix_reports_org_id_state", "org_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    prono_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pronos.id"))
    reporter_membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    kind: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, default="open", server_default="open")
    handled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("memberships.id"))
    handled_at: Mapped[datetime | None]
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())

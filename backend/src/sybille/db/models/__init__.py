"""Every model, imported here so that Alembic sees the whole schema."""

from sybille.db.base import Base
from sybille.db.models.accounts import Account, AuthSession, EmailToken
from sybille.db.models.ledger import LedgerEntry
from sybille.db.models.notifications import Notification
from sybille.db.models.orgs import Invitation, Membership, Organisation
from sybille.db.models.pronos import (
    Bet,
    Prono,
    PronoEvent,
    PronoOption,
    Reaction,
    Report,
    Section,
    Settlement,
)
from sybille.db.models.seasons import Season, SeasonClosure, Trophy
from sybille.db.models.uploads import Upload

__all__ = [
    "Account",
    "AuthSession",
    "Base",
    "Bet",
    "EmailToken",
    "Invitation",
    "LedgerEntry",
    "Membership",
    "Notification",
    "Organisation",
    "Prono",
    "PronoEvent",
    "PronoOption",
    "Reaction",
    "Report",
    "Season",
    "SeasonClosure",
    "Section",
    "Settlement",
    "Trophy",
    "Upload",
]

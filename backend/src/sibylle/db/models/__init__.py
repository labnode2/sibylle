"""Every model, imported here so that Alembic sees the whole schema."""

from sibylle.db.base import Base
from sibylle.db.models.accounts import Account, AuthSession, EmailToken
from sibylle.db.models.collection import (
    CatalogItem,
    OwnedItem,
    SecretCode,
    SecretCodeRedemption,
)
from sibylle.db.models.ledger import LedgerEntry
from sibylle.db.models.notifications import Notification
from sibylle.db.models.orgs import Invitation, Membership, Organisation
from sibylle.db.models.pronos import (
    Bet,
    Prono,
    PronoEvent,
    PronoOption,
    Reaction,
    Report,
    Section,
    Settlement,
)
from sibylle.db.models.seasons import Season, SeasonClosure, Trophy
from sibylle.db.models.uploads import Upload

__all__ = [
    "SecretCodeRedemption",
    "SecretCode",
    "OwnedItem",
    "CatalogItem",
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

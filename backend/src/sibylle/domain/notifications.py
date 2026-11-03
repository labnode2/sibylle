"""Rules of the notifications (contracts/notifications.md, research.md J5)."""

from datetime import datetime, timedelta
from enum import StrEnum
from urllib.parse import urlsplit


class NotificationType(StrEnum):
    """The four notifications a member can switch off, channel by channel."""

    NEW_PRONO = "new_prono"
    CLOSING_SOON = "closing_soon"
    RESULT = "result"
    DESIGNATION_REMINDER = "designation_reminder"


class Channel(StrEnum):
    PUSH = "push"
    EMAIL = "email"


# « Ferme dans 2 h » : sent once the closing is this close.
CLOSING_SOON = timedelta(hours=2)
# How long a push message waits for a device that is off.
PUSH_TTL = timedelta(hours=12)
# Reminders after the first one: one, three and seven days later, then every week.
_FIRST_REMINDERS = (timedelta(days=1), timedelta(days=3), timedelta(days=7))

# The browsers' push services; the worker posts to nothing else (a member chooses the endpoint).
PUSH_SERVICES = (
    "fcm.googleapis.com",  # Chrome, Edge on Android, Samsung Internet, Opera
    ".push.services.mozilla.com",  # Firefox
    ".push.apple.com",  # Safari, iOS 16.4 and later
    ".notify.windows.com",  # Edge on Windows
)


def reminder_base(
    *, closes_at: datetime | None, result_expected_at: datetime | None
) -> datetime | None:
    """When the first designation reminder is due: the expected result date, or else the day
    after the closing. An open-ended prono without an expected date is never reminded."""
    if result_expected_at is not None:
        return result_expected_at
    if closes_at is not None:
        return closes_at + timedelta(days=1)
    return None


def reminder_step(base: datetime, now: datetime) -> int | None:
    """The latest reminder due at `now` (0 on the day, 1, 2 and 3 at D+1, D+3 and D+7, then one
    more each week), or None before the first."""
    if now < base:
        return None
    elapsed = now - base
    for step, offset in enumerate(_FIRST_REMINDERS):
        if elapsed < offset:
            return step
    return len(_FIRST_REMINDERS) - 1 + elapsed.days // 7


def allowed_push_endpoint(endpoint: str) -> bool:
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    host = parts.hostname or ""
    return (
        parts.scheme == "https"
        and port is None
        and "@" not in parts.netloc
        and any(host == s or (s.startswith(".") and host.endswith(s)) for s in PUSH_SERVICES)
    )

"""What the four notifications say, in the account's language: the push message
(contracts/notifications.md) and the values of the e-mail templates."""

from typing import Any

from sibylle.config import get_settings
from sibylle.db.models import Notification
from sibylle.domain.notifications import NotificationType
from sibylle.i18n import t

ICON = "/icon-192.png"


def prono_path(payload: dict[str, Any]) -> str:
    return f"/o/{payload['org_id']}/pronos/{payload['prono_id']}"


def prefs_path(payload: dict[str, Any]) -> str:
    return f"/o/{payload['org_id']}/profil#notifications"


def _result_key(payload: dict[str, Any]) -> str:
    if payload["kind"] == "cancellation":
        return "cancelled"
    prefix = "corrected_" if payload["kind"] == "correction" else ""
    if payload["outcome"] != "won":
        return f"{prefix}lost"
    return f"{prefix}won_{'one' if payload['payout'] <= 1 else 'other'}"


def lead(notification: Notification, locale: str) -> str:
    """The sentence after the question: the e-mail's lead, and the end of the push message."""
    payload = notification.payload
    if notification.type == NotificationType.RESULT:
        return t(f"notify.result.{_result_key(payload)}", locale, **payload)
    return t(f"notify.{notification.type}.lead", locale, **payload)


def push_message(notification: Notification, locale: str) -> dict[str, str]:
    payload = notification.payload
    return {
        "type": notification.type,
        "title": t(f"notify.{notification.type}.title", locale, **payload),
        "body": t(
            "notify.body", locale, question=payload["question"], lead=lead(notification, locale)
        ),
        "url": prono_path(payload),
        # A newer message about the same prono replaces the older one on the device.
        "tag": f"{notification.type}:{payload['prono_id']}",
        "icon": ICON,
    }


def email_values(notification: Notification, locale: str) -> dict[str, Any]:
    origin = get_settings().public_origin
    return {
        **notification.payload,
        "lead": lead(notification, locale),
        "link": origin + prono_path(notification.payload),
        "prefs_link": origin + prefs_path(notification.payload),
    }

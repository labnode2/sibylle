"""Notifications: the eight switches of the account and its push devices (US8)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Request

from sibylle.api.deps import CurrentAccount, CurrentMember, Db
from sibylle.api.schemas import (
    NotificationList,
    NotificationOut,
    NotificationPrefItem,
    PushSubscriptionIn,
    PushSubscriptionOut,
    VapidKey,
)
from sibylle.config import get_settings
from sibylle.services import notifications

router = APIRouter(tags=["notifications"])


async def _prefs(session: Db, account: CurrentAccount) -> list[NotificationPrefItem]:
    return [
        NotificationPrefItem.model_validate({"type": type, "channel": channel, "enabled": enabled})
        for type, channel, enabled in await notifications.prefs(session, account.id)
    ]


@router.get("/me/notification-prefs")
async def get_prefs(account: CurrentAccount, session: Db) -> list[NotificationPrefItem]:
    return await _prefs(session, account)


@router.put("/me/notification-prefs")
async def put_prefs(
    body: Annotated[list[NotificationPrefItem], Body(max_length=8)],
    account: CurrentAccount,
    session: Db,
) -> list[NotificationPrefItem]:
    """Changes the switches given; the others stay as they are."""
    await notifications.set_prefs(
        session, account.id, [(pref.type, pref.channel, pref.enabled) for pref in body]
    )
    return await _prefs(session, account)


@router.get("/push/vapid-public-key")
async def vapid_public_key(account: CurrentAccount) -> VapidKey:
    return VapidKey(key=get_settings().vapid_public_key or None)


@router.post("/me/push-subscriptions", status_code=201)
async def subscribe(
    body: PushSubscriptionIn, request: Request, account: CurrentAccount, session: Db
) -> PushSubscriptionOut:
    subscription_id = await notifications.subscribe(
        session,
        account,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        user_agent=request.headers.get("user-agent"),
    )
    return PushSubscriptionOut(id=subscription_id)


@router.delete("/me/push-subscriptions/{subscription_id}", status_code=204)
async def unsubscribe(subscription_id: uuid.UUID, account: CurrentAccount, session: Db) -> None:
    await notifications.unsubscribe(session, account, subscription_id)


org_router = APIRouter(prefix="/orgs/{org_id}/notifications", tags=["notifications"])


@org_router.get("")
async def list_notifications(
    org_id: uuid.UUID, member: CurrentMember, session: Db
) -> NotificationList:
    """The member's notifications in this newsroom, newest first, with how many are unread."""
    rows = await notifications.listing(session, member.account_id, org_id)
    return NotificationList(
        unread=await notifications.unread_count(session, member.account_id, org_id),
        items=[
            NotificationOut.model_validate(
                {
                    "id": row.id,
                    "type": row.type,
                    "prono_id": row.payload["prono_id"],
                    "question": row.payload["question"],
                    "created_at": row.created_at,
                    "read_at": row.read_at,
                }
            )
            for row in rows
        ],
    )


@org_router.post("/read", status_code=204)
async def read_all(org_id: uuid.UUID, member: CurrentMember, session: Db) -> None:
    await notifications.mark_read(session, member.account_id, org_id)


@org_router.post("/{notification_id}/read", status_code=204)
async def read_one(
    org_id: uuid.UUID, notification_id: uuid.UUID, member: CurrentMember, session: Db
) -> None:
    await notifications.mark_read(session, member.account_id, org_id, notification_id)

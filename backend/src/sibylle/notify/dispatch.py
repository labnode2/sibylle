"""Sending the outbox (contracts/notifications.md, « Envoi et reprises »).

The worker takes the due rows with `FOR UPDATE SKIP LOCKED`, sends each on its channels and
marks it `sent`. A failed channel is tried again after 1 min, 5 min, 30 min and 2 h, alone: the
channels already done are not sent twice. A notification that has lost its object, or that no
channel can carry, is `skipped`.
"""

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.db.models import Account, Notification
from sibylle.db.session import transaction
from sibylle.domain.notifications import Channel, NotificationType
from sibylle.notify import messages
from sibylle.notify.email import Mail, Renderer, Sender
from sibylle.notify.push import Device, Gone, PushSender
from sibylle.services import notifications

log = logging.getLogger(__name__)

RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
)
_CHOSEN = {type.value for type in NotificationType}


async def dispatch(
    sender: Sender, renderer: Renderer, push: PushSender | None = None, *, batch: int = 50
) -> int:
    """Sends the notifications that are due; returns how many were handled. Without `push`
    (no VAPID keys), the push channel is left out."""
    async with transaction() as session:
        due = (
            await session.scalars(
                select(Notification)
                .where(Notification.state == "pending", Notification.next_attempt_at <= clock.now())
                .order_by(Notification.next_attempt_at)
                .limit(batch)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for notification in due:
            await _handle(session, notification, sender, renderer, push)
        return len(due)


async def _handle(
    session: AsyncSession,
    notification: Notification,
    sender: Sender,
    renderer: Renderer,
    push: PushSender | None,
) -> None:
    account = (
        await session.get(Account, notification.account_id) if notification.account_id else None
    )
    if account is not None and (account.deleted_at is not None or not account.email):
        account = None
    if notification.account_id is not None and account is None:
        notification.state = "skipped"
        return
    if notification.type in _CHOSEN:
        relevant = account is not None and await notifications.still_relevant(session, notification)
        channels = await _channels(session, account, notification, push) if relevant else []
    else:
        # Address check, password reset, invitation: always by e-mail.
        channels = [Channel.EMAIL] if account or notification.payload.get("to") else []
    if not channels:
        notification.state = "skipped"
        return

    failed = False
    for channel in channels:
        if channel in notification.done_channels:
            continue
        try:
            if channel is Channel.PUSH:
                assert push is not None and account is not None
                await _push(session, notification, account, push)
            else:
                await sender.send(_mail(notification, account, renderer))
        except Exception:
            log.warning(
                "notification not sent",
                extra={
                    "notification_id": str(notification.id),
                    "type": notification.type,
                    "channel": channel.value,
                },
                exc_info=True,
            )
            failed = True
            continue
        notification.done_channels = [*notification.done_channels, channel.value]

    if not failed:
        notification.state = "sent"
        notification.sent_at = clock.now()
        return
    notification.attempts += 1
    if notification.attempts > len(RETRY_DELAYS):
        notification.state = "failed"
    else:
        notification.next_attempt_at = clock.now() + RETRY_DELAYS[notification.attempts - 1]


async def _channels(
    session: AsyncSession,
    account: Account | None,
    notification: Notification,
    push: PushSender | None,
) -> list[Channel]:
    """The channels switched on that can reach the account: push on a device that accepted it,
    e-mail to a checked address."""
    assert account is not None
    enabled = await notifications.enabled_channels(session, account.id, notification.type)
    channels = []
    if (
        Channel.PUSH in enabled
        and push is not None
        and await notifications.devices(session, account.id)
    ):
        channels.append(Channel.PUSH)
    if Channel.EMAIL in enabled and account.email_verified_at is not None:
        channels.append(Channel.EMAIL)
    return channels


async def _push(
    session: AsyncSession, notification: Notification, account: Account, push: PushSender
) -> None:
    message = messages.push_message(notification, account.locale)
    urgency = "high" if notification.type == NotificationType.CLOSING_SOON else "normal"
    errors: list[Exception] = []
    for device in await notifications.devices(session, account.id):
        try:
            await push.send(
                Device(device.endpoint, device.p256dh, device.auth), message, urgency=urgency
            )
        except Gone:
            await session.delete(device)
        except Exception as error:
            errors.append(error)
        else:
            device.last_success_at = clock.now()
    if errors:
        raise errors[0]


def _mail(notification: Notification, account: Account | None, renderer: Renderer) -> Mail:
    if account is None:
        # An invitation to an address without an account.
        return renderer.render(notification.type, notification.payload["to"], notification.payload)
    assert account.email is not None
    values = (
        messages.email_values(notification, account.locale)
        if notification.type in _CHOSEN
        else notification.payload
    )
    return renderer.render(notification.type, account.email, values, account.locale)

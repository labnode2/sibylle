"""The notifications outbox: rows written with the event that causes them, sent by the worker."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sybille import clock
from sybille.db.models import Notification


async def enqueue(
    session: AsyncSession,
    *,
    type: str,
    payload: dict[str, Any],
    dedupe_key: str,
    account_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    scheduled_at: datetime | None = None,
) -> bool:
    """Queues a notification; a second one with the same `dedupe_key` is ignored.

    Returns whether a row was added.
    """
    result = await session.execute(
        insert(Notification)
        .values(
            account_id=account_id,
            org_id=org_id,
            type=type,
            payload=payload,
            dedupe_key=dedupe_key,
            next_attempt_at=scheduled_at or clock.now(),
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(Notification.id)
    )
    return result.scalar_one_or_none() is not None

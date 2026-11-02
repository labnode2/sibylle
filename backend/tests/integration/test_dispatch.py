from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.conftest import MakeAccount

from sybille import clock
from sybille.db.models import Account, Notification
from sybille.db.session import transaction
from sybille.notify.email import MemorySender, Renderer
from sybille.services.notifications import enqueue
from sybille.worker.jobs import RETRY_DELAYS, dispatch

pytestmark = pytest.mark.integration


@pytest.fixture
def renderer(tmp_path: Path) -> Renderer:
    (tmp_path / "fr").mkdir()
    (tmp_path / "fr" / "hello.txt").write_text("Bonjour {{ name }}", encoding="utf-8")
    (tmp_path / "fr" / "hello.html").write_text("<p>Bonjour {{ name }}</p>", encoding="utf-8")
    return Renderer(tmp_path)


async def _state(key: str) -> Notification:
    async with transaction() as session:
        notification = await session.scalar(
            select(Notification).where(Notification.dedupe_key == key)
        )
        assert notification is not None
        return notification


async def test_a_due_notification_is_sent_once(
    make_account: MakeAccount, renderer: Renderer
) -> None:
    account = await make_account("cami@exemple.fr")
    async with transaction() as session:
        assert await enqueue(
            session, type="hello", payload={"name": "Cami"}, dedupe_key="k1", account_id=account.id
        )
        assert not await enqueue(
            session, type="hello", payload={"name": "Cami"}, dedupe_key="k1", account_id=account.id
        )
    sender = MemorySender()
    assert await dispatch(sender, renderer) == 1
    assert await dispatch(sender, renderer) == 0
    assert [(m.to, m.text, m.html) for m in sender.sent] == [
        ("cami@exemple.fr", "Bonjour Cami", "<p>Bonjour Cami</p>")
    ]
    assert (await _state("k1")).state == "sent"


async def test_an_address_without_account_comes_from_the_payload(
    db: None, renderer: Renderer
) -> None:
    async with transaction() as session:
        await enqueue(
            session, type="hello", payload={"name": "Léo", "to": "leo@exemple.fr"}, dedupe_key="k2"
        )
    sender = MemorySender()
    await dispatch(sender, renderer)
    assert [m.to for m in sender.sent] == ["leo@exemple.fr"]


async def test_a_scheduled_notification_waits(
    make_account: MakeAccount, renderer: Renderer, fake_clock: clock.FakeClock
) -> None:
    account = await make_account()
    async with transaction() as session:
        await enqueue(
            session,
            type="hello",
            payload={"name": "Hugo"},
            dedupe_key="k3",
            account_id=account.id,
            scheduled_at=clock.now() + timedelta(hours=2),
        )
    assert await dispatch(MemorySender(), renderer) == 0
    fake_clock.advance(timedelta(hours=2))
    assert await dispatch(MemorySender(), renderer) == 1


async def test_failures_are_retried_then_given_up(
    make_account: MakeAccount, renderer: Renderer, fake_clock: clock.FakeClock
) -> None:
    account = await make_account()
    async with transaction() as session:
        await enqueue(
            session, type="hello", payload={"name": "Inès"}, dedupe_key="k4", account_id=account.id
        )
    failing = MemorySender(fail=True)
    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        await dispatch(failing, renderer)
        notification = await _state("k4")
        assert (notification.state, notification.attempts) == ("pending", attempt)
        retry_in = notification.next_attempt_at - clock.now()
        assert delay - timedelta(seconds=5) < retry_in <= delay
        assert await dispatch(failing, renderer) == 0  # not due yet
        fake_clock.advance(delay)
    await dispatch(failing, renderer)
    assert (await _state("k4")).state == "failed"


async def test_a_deleted_account_is_skipped(make_account: MakeAccount, renderer: Renderer) -> None:
    account = await make_account()
    async with transaction() as session:
        await enqueue(
            session, type="hello", payload={"name": "X"}, dedupe_key="k5", account_id=account.id
        )
        stored = await session.get(Account, account.id)
        assert stored is not None
        stored.deleted_at = clock.now()
        stored.email = None
    sender = MemorySender()
    await dispatch(sender, renderer)
    assert sender.sent == []
    assert (await _state("k5")).state == "skipped"
    async with transaction() as session:
        assert await session.scalar(select(func.count()).select_from(Notification)) == 1

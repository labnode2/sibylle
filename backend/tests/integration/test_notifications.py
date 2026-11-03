"""The four notifications of US8 (contracts/notifications.md): who gets them, when, once, and on
which channels."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from tests.conftest import MakeAccount, MakeMember, MakeOrg, MakePerson, Person
from tests.contract.helpers import notifications
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import close, option, url

from sibylle import clock
from sibylle.db.models import Account, Membership, PushSubscription
from sibylle.db.session import transaction
from sibylle.notify.dispatch import dispatch
from sibylle.notify.email import MemorySender, Renderer
from sibylle.notify.push import MemoryPushSender
from sibylle.worker.jobs import advance_pronos, closing_soon_alerts, designation_reminders

pytestmark = pytest.mark.integration

FCM = "https://fcm.googleapis.com/fcm/send/"


async def subscribe(person: Person, device: str = "telephone") -> None:
    response = await person.client.post(
        "/api/me/push-subscriptions",
        json={"endpoint": FCM + device, "keys": {"p256dh": "cle-publique", "auth": "secret"}},
    )
    assert response.status_code == 201, response.text


async def recipients(type: str) -> set[Any]:
    return {n.account_id for n in await notifications(type)}


async def states(type: str) -> dict[Any, str]:
    return {n.account_id: n.state for n in await notifications(type)}


def emailed(sender: MemorySender) -> list[str]:
    return [mail.to for mail in sender.sent]


async def send(push: MemoryPushSender | None = None) -> MemorySender:
    sender = MemorySender()
    await dispatch(sender, Renderer(), push)
    return sender


async def leave(person: Person) -> None:
    async with transaction() as session:
        await session.execute(
            update(Membership).where(Membership.id == person.member.id).values(status="left")
        )


async def test_a_new_prono_reaches_the_active_members_but_its_author(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await leave(leo)

    prono = await publish(hugo.client, str(org.id))
    assert await recipients("new_prono") == {cami.account.id}
    [queued] = await notifications("new_prono")
    assert queued.dedupe_key == f"new_prono:{prono['id']}:{cami.account.id}"
    assert queued.org_id == org.id

    # A scheduled prono waits for its opening; the worker running twice changes nothing.
    later = await publish(
        hugo.client, str(org.id), opens_at=(clock.now() + timedelta(hours=2)).isoformat()
    )
    assert len(await notifications("new_prono")) == 1
    fake_clock.advance(timedelta(hours=2))
    await advance_pronos()
    await advance_pronos()
    keys = {n.dedupe_key for n in await notifications("new_prono")}
    assert f"new_prono:{later['id']}:{cami.account.id}" in keys
    assert len(keys) == 2


async def test_a_validated_proposal_is_news_for_the_others(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    proposal = await publish(cami.client, str(org.id))
    assert proposal["state"] == "proposed"
    assert await notifications("new_prono") == []

    response = await hugo.client.post(url(org.id, proposal["id"], "validate"), json={})
    assert response.status_code == 200, response.text
    # Neither its author nor the journalist who just validated it needs the news.
    assert await recipients("new_prono") == {leo.account.id}


async def test_closing_soon_once_and_only_without_a_bet(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")
    prono = await publish(
        hugo.client, str(org.id), closes_at=(clock.now() + timedelta(hours=3)).isoformat()
    )
    await publish(
        hugo.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    bet = await place(
        cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10
    )
    assert bet.status_code == 201, bet.text

    assert await closing_soon_alerts() == 0
    fake_clock.advance(timedelta(hours=1))
    assert await closing_soon_alerts() == 3
    assert await closing_soon_alerts() == 0
    assert await recipients("closing_soon") == {
        hugo.account.id,
        leo.account.id,
        manon.account.id,
    }
    [first, *_] = await notifications("closing_soon")
    assert first.dedupe_key.startswith(f"closing_soon:{prono['id']}:")

    # Léo bets before the worker sends: his alert has no object any more.
    await place(leo.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=10)
    sender = await send()
    assert (await states("closing_soon"))[leo.account.id] == "skipped"
    assert (await states("closing_soon"))[manon.account.id] == "sent"
    alerts = [m.to for m in sender.sent if m.subject == "Sophia Office · Plus que 2 h pour jouer"]
    assert set(alerts) == {hugo.account.email, manon.account.email}


async def test_results_reach_the_bettors_at_each_settlement(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await place(leo.client, str(org.id), prono["id"], option_id=option(prono, "Monaco"), stake=10)
    await send()  # the news of the prono
    await close(fake_clock)

    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    assert await recipients("result") == {cami.account.id, leo.account.id}

    await subscribe(cami)
    push = MemoryPushSender()
    sender = await send(push)
    [(endpoint, message, urgency)] = push.sent
    assert endpoint == FCM + "telephone"
    assert urgency == "normal"
    assert message == {
        "type": "result",
        "title": "Sophia Office · Édition spéciale",
        "body": "Nice ou Monaco samedi ? Résultat : Nice. Tu gagnes 40 lauriers.",
        "url": f"/o/{org.id}/pronos/{prono['id']}",
        "tag": f"result:{prono['id']}",
        "icon": "/icon-192.png",
    }
    subjects = {m.to: m.subject for m in sender.sent}
    assert subjects == {
        cami.account.email: "Sophia Office · Édition spéciale : Nice ou Monaco samedi ?",
        leo.account.email: "Sophia Office · Édition spéciale : Nice ou Monaco samedi ?",
    }
    [to_leo] = [m for m in sender.sent if m.to == leo.account.email]
    assert "Résultat : Nice. Pas cette fois." in to_leo.text

    corrected = await ines.client.post(
        url(org.id, prono["id"], "correct"), json={"correct_option_ids": [option(prono, "Monaco")]}
    )
    assert corrected.status_code == 200, corrected.text
    keys = {n.dedupe_key for n in await notifications("result")}
    assert f"result:{prono['id']}:2:{leo.account.id}" in keys
    assert len(keys) == 4
    push = MemoryPushSender()
    await send(push)
    [(_, message, _)] = push.sent
    assert message["body"] == "Nice ou Monaco samedi ? Résultat corrigé : Monaco. Pas cette fois."


async def test_a_cancellation_tells_the_bettors_and_drops_the_pending_news(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    response = await ines.client.post(url(org.id, prono["id"], "cancel"), json={})
    assert response.status_code == 200, response.text

    sender = await send()
    assert (await states("new_prono"))[cami.account.id] == "skipped"
    [mail] = sender.sent
    assert mail.subject == "Sophia Office · Édition spéciale : Nice ou Monaco samedi ?"
    assert "Prono annulé : ta mise t'est rendue." in mail.text


async def test_designation_reminders_follow_their_schedule(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    closes_at = clock.now() + timedelta(days=1)
    prono = await publish(hugo.client, str(org.id), closes_at=closes_at.isoformat())
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)

    # Without an expected result date, the first reminder comes the day after the closing.
    fake_clock.set(closes_at + timedelta(days=1) - timedelta(minutes=1))
    await advance_pronos()
    assert await designation_reminders() == 0
    steps = []
    for wait in (timedelta(minutes=1), timedelta(days=1), timedelta(days=2), timedelta(days=4)):
        fake_clock.advance(wait)
        assert await designation_reminders() == 1
        assert await designation_reminders() == 0
        steps.append(len(await notifications("designation_reminder")))
    assert steps == [1, 2, 3, 4]  # D, D+1, D+3, D+7
    fake_clock.advance(timedelta(days=6))
    assert await designation_reminders() == 0
    fake_clock.advance(timedelta(days=1))
    assert await designation_reminders() == 1  # then every week
    assert await recipients("designation_reminder") == {hugo.account.id}
    keys = [n.dedupe_key for n in await notifications("designation_reminder")]
    assert keys[0] == f"designation:{prono['id']}:0-0"

    sender = await send()
    assert {m.subject for m in sender.sent if m.to == hugo.account.email} == {
        "Sophia Office · Résultat à désigner : Nice ou Monaco samedi ?"
    }

    # Designated: the reminders stop.
    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    fake_clock.advance(timedelta(days=7))
    assert await designation_reminders() == 0


async def test_the_reminder_goes_to_whoever_validated_the_proposal(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    expected = clock.now() + timedelta(days=2)
    proposal = await publish(
        cami.client,
        str(org.id),
        closes_at=(clock.now() + timedelta(days=1)).isoformat(),
        result_expected_at=expected.isoformat(),
    )
    await ines.client.post(url(org.id, proposal["id"], "validate"), json={})
    fake_clock.set(expected - timedelta(minutes=1))
    await advance_pronos()
    assert await designation_reminders() == 0
    fake_clock.advance(timedelta(minutes=1))
    assert await designation_reminders() == 1
    assert await recipients("designation_reminder") == {ines.account.id}

    # A relaunch starts the schedule again from the new dates.
    relaunched = await ines.client.post(
        url(org.id, proposal["id"], "relaunch"),
        json={"closes_at": (clock.now() + timedelta(days=1)).isoformat()},
    )
    assert relaunched.status_code == 200, relaunched.text
    sender = await send()
    assert sender.sent == []
    assert {n.state for n in await notifications("designation_reminder")} == {"skipped"}
    fake_clock.advance(timedelta(days=2))
    await advance_pronos()
    assert await designation_reminders() == 1
    keys = [n.dedupe_key for n in await notifications("designation_reminder")]
    assert keys[-1] == f"designation:{proposal['id']}:1-0"


async def test_preferences_choose_the_channels_type_by_type(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await subscribe(cami)
    await subscribe(leo, "ordinateur")
    response = await cami.client.put(
        "/api/me/notification-prefs",
        json=[{"type": "new_prono", "channel": "email", "enabled": False}],
    )
    assert response.status_code == 200, response.text
    await leo.client.put(
        "/api/me/notification-prefs",
        json=[
            {"type": "new_prono", "channel": "push", "enabled": False},
            {"type": "new_prono", "channel": "email", "enabled": False},
        ],
    )

    await publish(hugo.client, str(org.id))
    push = MemoryPushSender()
    sender = await send(push)
    assert emailed(sender) == []
    assert [endpoint for endpoint, _, _ in push.sent] == [FCM + "telephone"]
    assert await states("new_prono") == {cami.account.id: "sent", leo.account.id: "skipped"}


async def test_no_notification_email_without_a_verified_address(
    make_org: MakeOrg,
    person: MakePerson,
    make_account: MakeAccount,
    make_member: MakeMember,
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    account = await make_account("zoe@exemple.fr", verified=False)
    await make_member(org, "reader", account=account, pseudo="Zoé")
    cami = await person(org, "reader", "Cami")
    await publish(hugo.client, str(org.id))

    sender = await send(MemoryPushSender())
    assert emailed(sender) == [cami.account.email]
    assert (await states("new_prono"))[account.id] == "skipped"


async def test_a_subscription_the_push_service_forgot_is_removed(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await subscribe(cami, "ancien")
    await subscribe(cami, "nouveau")
    await publish(hugo.client, str(org.id))

    push = MemoryPushSender(gone={FCM + "ancien"})
    await send(push)
    assert [endpoint for endpoint, _, _ in push.sent] == [FCM + "nouveau"]
    async with transaction() as session:
        endpoints = (await session.scalars(select(PushSubscription.endpoint))).all()
        assert endpoints == [FCM + "nouveau"]
        kept = await session.scalar(select(PushSubscription))
        assert kept is not None and kept.last_success_at is not None
    assert (await states("new_prono"))[cami.account.id] == "sent"


async def test_a_failed_channel_is_retried_alone(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await subscribe(cami)
    await publish(hugo.client, str(org.id))

    push = MemoryPushSender()
    await dispatch(MemorySender(fail=True), Renderer(), push)
    [queued] = await notifications("new_prono")
    assert (queued.state, queued.attempts, queued.done_channels) == ("pending", 1, ["push"])

    fake_clock.advance(timedelta(minutes=1))
    sender = MemorySender()
    await dispatch(sender, Renderer(), push)
    assert len(push.sent) == 1  # the push already left; only the e-mail is sent again
    assert emailed(sender) == [cami.account.email]
    assert (await states("new_prono"))[cami.account.id] == "sent"


async def test_notification_emails_link_to_their_preferences(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    [mail] = (await send()).sent
    assert mail.subject == "Sophia Office · Nouveau prono : Nice ou Monaco samedi ?"
    origin = "http://localhost:5173"
    assert f"{origin}/o/{org.id}/pronos/{prono['id']}" in mail.html
    assert f"{origin}/compte#notifications" in mail.html
    assert f"{origin}/compte#notifications" in mail.text


async def test_a_deleted_account_gets_nothing(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await publish(hugo.client, str(org.id))
    async with transaction() as session:
        await session.execute(
            update(Account)
            .where(Account.id == cami.account.id)
            .values(deleted_at=clock.now(), email=None)
        )
    assert (await send()).sent == []
    assert (await states("new_prono"))[cami.account.id] == "skipped"

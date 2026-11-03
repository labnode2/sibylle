"""US11: export one's data, delete one's account, leave a newsroom (research.md R20)."""

import httpx
import pytest
from sqlalchemy import func, select
from tests.conftest import PASSWORD, ClientFor, MakeOrg, MakePerson
from tests.contract.helpers import give_coins
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import close, option, url

from sibylle import clock
from sibylle.db.models import (
    Account,
    AuthSession,
    Bet,
    Invitation,
    LedgerEntry,
    Membership,
    Notification,
    NotificationPref,
    Organisation,
    PushSubscription,
)
from sibylle.db.session import transaction
from sibylle.domain.content import DEFAULT_AVATAR
from sibylle.services.ledger import check_caches

pytestmark = pytest.mark.contract

DEVICE = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/telephone",
    "keys": {"p256dh": "cle-publique", "auth": "secret"},
}


async def delete_me(client: httpx.AsyncClient, confirm: bool = True) -> httpx.Response:
    return await client.request("DELETE", "/api/me", json={"confirm": confirm})


async def leave(client: httpx.AsyncClient, org_id: object) -> httpx.Response:
    return await client.delete(f"/api/orgs/{org_id}/members/me")


async def test_the_export_holds_everything_about_me(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await give_coins(cami.member, 500)
    catalog = (await cami.client.get(f"/api/orgs/{org.id}/catalog")).json()
    red = next(entry["item"] for entry in catalog if entry["item"]["key"] == "color-41")
    bought = await cami.client.post(f"/api/orgs/{org.id}/catalog/{red['id']}/purchase")
    assert bought.status_code == 201, bought.text
    await cami.client.put(
        "/api/me/notification-prefs", json=[{"type": "result", "channel": "push", "enabled": False}]
    )
    await cami.client.post("/api/me/push-subscriptions", json=DEVICE, headers={"User-Agent": "Fx"})

    response = await cami.client.get("/api/me/export")
    assert response.status_code == 200, response.text
    disposition = response.headers["content-disposition"]
    assert disposition == 'attachment; filename="sibylle-mes-donnees-2026-11-02.json"'
    data = response.json()
    assert data["account"]["email"] == cami.account.email
    assert (data["account"]["first_name"], data["account"]["last_name"]) == ("Camille", "Martin")
    [newsroom] = data["newsrooms"]
    assert newsroom["newsroom"] == {"id": str(org.id), "title": "Sophia Office"}
    membership = newsroom["membership"]
    assert (membership["pseudo"], membership["role"], membership["status"]) == (
        "Cami",
        "reader",
        "active",
    )
    assert (membership["balance"], membership["coins"]) == (90, 100)
    [bet] = newsroom["bets"]
    assert (bet["question"], bet["answer"], bet["stake"], bet["outcome"]) == (
        "Nice ou Monaco samedi ?",
        "Nice",
        10,
        "pending",
    )
    assert [(e["kind"], e["amount"]) for e in newsroom["laurels"]] == [
        ("starting_balance", 100),
        ("stake", -10),
    ]
    assert [(e["kind"], e["amount"]) for e in newsroom["coins"]] == [
        ("weekly", 500),
        ("purchase", -400),
    ]
    assert [item["key"] for item in newsroom["collection"]] == ["color-41"]
    assert newsroom["trophies"] == [] and newsroom["reports"] == []
    assert {"type": "result", "channel": "push", "enabled": False} in data["notification_prefs"]
    [device] = data["push_devices"]
    assert device["user_agent"] == "Fx" and "endpoint" not in device
    # Nothing private about anybody else.
    assert ines.account.email not in response.text


async def test_deleting_my_account_keeps_the_others_history(
    make_org: MakeOrg,
    person: MakePerson,
    client_for: ClientFor,
    client: httpx.AsyncClient,
    fake_clock: clock.FakeClock,
) -> None:
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await place(leo.client, str(org.id), prono["id"], option_id=option(prono, "Monaco"), stake=10)
    await close(fake_clock)
    resolved = await ines.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    await cami.client.post("/api/me/push-subscriptions", json=DEVICE)
    email_off = [{"type": "result", "channel": "email", "enabled": False}]
    await cami.client.put("/api/me/notification-prefs", json=email_off)
    other_device = await client_for(cami.account)
    email = cami.account.email
    assert email is not None

    assert (await delete_me(cami.client, confirm=False)).status_code == 422
    response = await delete_me(cami.client)
    assert response.status_code == 204, response.text
    assert "sibylle_session=" in response.headers.get("set-cookie", "")

    # Signed out everywhere, and no way back in.
    assert (await cami.client.get("/api/me")).status_code == 401
    assert (await other_device.get("/api/me")).status_code == 401
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 401

    async with transaction() as session:
        account = await session.get(Account, cami.account.id)
        assert account is not None and account.deleted_at is not None
        assert (account.email, account.first_name, account.last_name) == (None, None, None)
        assert (account.password_hash, account.email_verified_at) == (None, None)
        for table in (AuthSession, PushSubscription, NotificationPref, Notification):
            left = await session.scalar(
                select(func.count()).select_from(table).where(table.account_id == account.id)
            )
            assert left == 0, table.__tablename__
        member = await session.get(Membership, cami.member.id)
        assert member is not None
        assert (member.status, member.pseudo) == ("anonymized", "Ancien membre")
        assert member.role == "reader"
        assert member.avatar == DEFAULT_AVATAR and member.avatar_frame_item_id is None
        bets = await session.scalar(
            select(func.count()).select_from(Bet).where(Bet.membership_id == member.id)
        )
        entries = await session.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.membership_id == member.id)
        )
        assert (bets, entries) == (1, 4)  # start, stake, base gain, pot share
        assert await check_caches(session, org.id) == []

    # The special edition still counts the winner, under her new name.
    detail = (await ines.client.get(url(org.id, prono["id"]))).json()
    edition = detail["special_edition"]
    assert [w["member"]["pseudo"] for w in edition["winners"]] == ["Ancien membre"]
    assert edition["pot"] == 20
    members = (await ines.client.get(f"/api/orgs/{org.id}/members")).json()
    assert {m["pseudo"] for m in members} == {"Inès", "Léo"}

    # The address is free again.
    again = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": PASSWORD, "first_name": "Cami", "last_name": "Neuve"},
    )
    assert again.status_code == 201, again.text


async def test_the_invitations_sent_to_my_address_go_too(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    sent = await ines.client.post(
        f"/api/orgs/{org.id}/invitations", json={"kind": "email", "email": cami.account.email}
    )
    assert sent.status_code == 201, sent.text
    assert (await delete_me(cami.client)).status_code == 204
    async with transaction() as session:
        invitations = (await session.scalars(select(Invitation.email))).all()
        assert cami.account.email not in invitations
        queued = (await session.scalars(select(Notification.payload))).all()
        assert all(payload.get("to") != cami.account.email for payload in queued)


async def test_the_only_editor_names_another_first(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")

    refused = await delete_me(ines.client)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "last_editor"
    assert refused.json()["error"]["fields"] == {"org_id": str(org.id)}
    assert (await ines.client.get("/api/me")).status_code == 200
    refused = await leave(ines.client, org.id)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "last_editor"

    promoted = await ines.client.patch(
        f"/api/orgs/{org.id}/members/{cami.member.id}/role", json={"role": "editor"}
    )
    assert promoted.status_code == 200, promoted.text
    assert (await leave(ines.client, org.id)).status_code == 204
    assert (await ines.client.get(f"/api/orgs/{org.id}")).status_code == 404
    async with transaction() as session:
        member = await session.get(Membership, ines.member.id)
        assert member is not None
        assert (member.status, member.role, member.pseudo) == ("left", "reader", "Inès")
    assert (await leave(ines.client, org.id)).status_code == 404


async def test_a_reader_leaves_and_keeps_their_bets(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    assert (await leave(cami.client, org.id)).status_code == 204
    me = (await cami.client.get("/api/me")).json()
    assert me["memberships"] == []
    detail = (await ines.client.get(url(org.id, prono["id"]))).json()
    assert detail["bet_count"] == 1 and detail["pot"] == 10


async def test_a_newsroom_goes_with_its_only_member(make_org: MakeOrg, person: MakePerson) -> None:
    alone = await make_org("Seule")
    ines = await person(alone, "editor", "Inès")
    deserted = await make_org("Désertée")
    hugo = await person(deserted, "editor", "Hugo")

    assert (await delete_me(ines.client)).status_code == 204
    # The last one out: nobody could come back to it.
    assert (await leave(hugo.client, deserted.id)).status_code == 204
    async with transaction() as session:
        for org in (alone, deserted):
            stored = await session.get(Organisation, org.id)
            assert stored is not None and stored.deleted_at is not None, org.title
            assert stored.access_code is None

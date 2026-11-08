"""GET /api/me reads an unconfirmed address again in Keycloak (US2, research.md K9): at most once
a minute, never once confirmed, and a Keycloak that does not answer changes nothing for the
person (SC-006)."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import update
from tests.conftest import ClientFor, MakeAccount, MakeMember, MakeOrg, MakePerson
from tests.contract.test_pronos import place, publish
from tests.keycloak_fake import FakeKeycloak

from sibylle import clock
from sibylle.db.models import Account, Prono
from sibylle.db.session import transaction
from sibylle.domain.lifecycle import State

pytestmark = pytest.mark.contract


async def test_an_unconfirmed_address_is_read_again_once_a_minute(
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_keycloak: FakeKeycloak,
    fake_clock: clock.FakeClock,
) -> None:
    account = await make_account(verified=False)
    signed_in = await client_for(account)

    def reads() -> list[str]:
        return fake_keycloak.calls_to(f"GET /admin/realms/sibylle/users/{account.keycloak_id}")

    assert (await signed_in.get("/api/me")).json()["email_verified"] is False
    assert len(reads()) == 1
    assert (await signed_in.get("/api/me")).json()["email_verified"] is False
    assert len(reads()) == 1  # within the minute

    # The person follows the link of Keycloak's e-mail, on another device say.
    fake_keycloak.users[str(account.keycloak_id)]["emailVerified"] = True
    fake_clock.advance(timedelta(seconds=61))
    assert (await signed_in.get("/api/me")).json()["email_verified"] is True
    assert len(reads()) == 2
    async with transaction() as session:
        stored = await session.get(Account, account.id)
        assert stored is not None
        assert stored.email_verified_at is not None and stored.identity_checked_at is not None

    # Confirmed: never read again.
    fake_clock.advance(timedelta(minutes=5))
    assert (await signed_in.get("/api/me")).json()["email_verified"] is True
    assert len(reads()) == 2


async def test_a_confirmed_account_never_asks_keycloak(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    signed_in = await client_for(await make_account(verified=True))
    assert (await signed_in.get("/api/me")).json()["email_verified"] is True
    assert fake_keycloak.calls == []


async def test_another_address_confirmed_in_keycloak_is_not_this_one(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    # The address changed in Keycloak and was confirmed there: the next sign-in copies it, with
    # its confirmation; until then, the account's own address stays unconfirmed.
    account = await make_account("ana@exemple.fr", verified=False)
    fake_keycloak.users[str(account.keycloak_id)].update(
        email="ana.b@exemple.fr", emailVerified=True
    )
    signed_in = await client_for(account)
    me = (await signed_in.get("/api/me")).json()
    assert (me["email"], me["email_verified"]) == ("ana@exemple.fr", False)


async def test_without_keycloak_the_known_state_stays(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    signed_in = await client_for(await make_account(verified=False))
    fake_keycloak.down = True
    response = await signed_in.get("/api/me")
    assert response.status_code == 200
    assert response.json()["email_verified"] is False


async def test_the_welcome_pop_up_is_closed_once_for_good(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    signed_in = await client_for(await make_account())
    assert (await signed_in.get("/api/me")).json()["welcomed"] is False
    closed = await signed_in.patch("/api/me", json={"welcomed": True})
    assert closed.status_code == 200, closed.text
    assert closed.json()["welcomed"] is True
    # It does not come back: there is no way to say false.
    assert (await signed_in.patch("/api/me", json={"welcomed": False})).status_code == 422
    assert (await signed_in.get("/api/me")).json()["welcomed"] is True


def entry(me: dict[str, Any], org_id: object) -> dict[str, Any]:
    found: dict[str, Any] = next(e for e in me["memberships"] if e["org"]["id"] == str(org_id))
    return found


async def test_each_newsroom_counts_the_open_pronos_without_my_bet(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    first = await publish(hugo.client, str(org.id))
    await publish(hugo.client, str(org.id), question="Il neige à Noël ?")
    assert entry((await cami.client.get("/api/me")).json(), org.id)["unanswered"] == 2

    nice = first["options"][0]["id"]
    assert (
        await place(cami.client, str(org.id), first["id"], option_id=nice, stake=0)
    ).status_code == 201
    assert entry((await cami.client.get("/api/me")).json(), org.id)["unanswered"] == 1
    # A closed prono no longer waits for anyone.
    async with transaction() as session:
        await session.execute(
            update(Prono).where(Prono.org_id == org.id).values(state=State.CLOSED.value)
        )
    assert entry((await cami.client.get("/api/me")).json(), org.id)["unanswered"] == 0


async def test_the_only_editor_is_told_before_leaving(
    make_org: MakeOrg, make_member: MakeMember, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    # Alone in a newsroom: leaving closes it, nobody else to name.
    alone = await make_org("Rédaction d'Inès")
    await make_member(alone, "editor", account=ines.account, pseudo="Inès")
    me = (await ines.client.get("/api/me")).json()
    assert entry(me, org.id)["sole_editor"] is False
    assert entry(me, alone.id)["sole_editor"] is False

    cami = await person(org, "reader", "Cami")
    assert entry((await ines.client.get("/api/me")).json(), org.id)["sole_editor"] is True
    assert entry((await cami.client.get("/api/me")).json(), org.id)["sole_editor"] is False

    # Another editor named: Inès may go.
    role = f"/api/orgs/{org.id}/members/{cami.member.id}/role"
    assert (await ines.client.patch(role, json={"role": "editor"})).status_code == 200
    assert entry((await ines.client.get("/api/me")).json(), org.id)["sole_editor"] is False

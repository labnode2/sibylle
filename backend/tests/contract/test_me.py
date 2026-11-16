"""GET /api/me reads an unconfirmed address again in Keycloak (US2, research.md K9): at most once
a minute, never once confirmed, and a Keycloak that does not answer changes nothing for the
person (SC-006)."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import update
from tests.conftest import ClientFor, MakeAccount, MakeMember, MakeOrg, MakePerson, Person
from tests.contract.test_pronos import publish
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


async def test_each_newsroom_bubble_adds_up_the_bubbles_of_its_menus(
    make_org: MakeOrg, make_member: MakeMember, person: MakePerson
) -> None:
    """In the lists of newsrooms, a newsroom's bubble is what its menus count: « Pronos » (the
    unread notifications that still lead to a prono) and, for the editor, « La rédaction » (the
    open reports). It goes with them: never a bubble that leads nowhere."""
    org, other = await make_org(), await make_org("Autre")
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await make_member(other, "reader", account=cami.account, pseudo="Cami")
    zoe = await person(other, "journalist", "Zoé")

    async def bubbles(who: Person) -> dict[str, int]:
        me = (await who.client.get("/api/me")).json()
        return {e["org"]["id"]: e["waiting"] for e in me["memberships"]}

    async def menus(who: Person, org_id: object) -> int:
        """« Pronos », plus « La rédaction » for whoever may read the open reports."""
        base = f"/api/orgs/{org_id}"
        count: int = (await who.client.get(f"{base}/notifications/unread")).json()["total"]
        reports = await who.client.get(f"{base}/reports", params={"state": "open"})
        return count + (len(reports.json()) if reports.status_code == 200 else 0)

    first = await publish(hugo.client, str(org.id))
    second = await publish(hugo.client, str(org.id), question="Il neige à Noël ?")
    there = await publish(zoe.client, str(other.id), question="Le pot aura-t-il lieu ?")
    assert await bubbles(cami) == {str(org.id): 2, str(other.id): 1}
    assert await bubbles(ines) == {str(org.id): 2}
    # Its author is not told of their own prono.
    assert await bubbles(hugo) == {str(org.id): 0}

    # Opening a prono reads it, in its newsroom only.
    await read(cami, org.id, first["id"])
    assert await bubbles(cami) == {str(org.id): 1, str(other.id): 1}
    await read(cami, other.id, there["id"])
    assert await bubbles(cami) == {str(org.id): 1, str(other.id): 0}

    # A report waits for the editor beside « La rédaction », so on the newsroom too.
    reported = await cami.client.post(
        f"/api/orgs/{org.id}/pronos/{second['id']}/reports", json={"kind": "content"}
    )
    assert reported.status_code == 201, reported.text
    assert await bubbles(ines) == {str(org.id): 3}
    assert await bubbles(hugo) == {str(org.id): 0}
    for who, newsroom in ((ines, org), (hugo, org), (cami, org), (cami, other)):
        assert (await bubbles(who))[str(newsroom.id)] == await menus(who, newsroom.id)

    handled = await ines.client.post(
        f"/api/orgs/{org.id}/reports/{reported.json()['id']}/handle", json={"state": "dismissed"}
    )
    assert handled.status_code == 200, handled.text
    assert await bubbles(ines) == {str(org.id): 2}

    # Closed, a new prono is no longer news: nothing left to lead to.
    async with transaction() as session:
        await session.execute(
            update(Prono).where(Prono.org_id == org.id).values(state=State.CLOSED.value)
        )
    assert await bubbles(cami) == {str(org.id): 0, str(other.id): 0}
    assert await bubbles(ines) == {str(org.id): 0}


async def read(who: Person, org_id: object, prono_id: str) -> None:
    """What opening the prono does."""
    response = await who.client.post(
        f"/api/orgs/{org_id}/notifications/read", json={"prono_id": prono_id}
    )
    assert response.status_code == 204, response.text


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

"""The bell's list: a member's notifications in a newsroom, read or not, counted."""

import pytest
from tests.conftest import MakeOrg, MakePerson, Person

from sibylle.db.models import Notification
from sibylle.db.session import transaction
from sibylle.services import notifications

pytestmark = pytest.mark.contract


async def add(person: Person, key: str, *, state: str = "sent", type: str = "new_prono") -> None:
    async with transaction() as session:
        session.add(
            Notification(
                account_id=person.account.id,
                org_id=person.member.org_id,
                type=type,
                state=state,
                dedupe_key=key,
                payload={
                    "prono_id": "00000000-0000-0000-0000-000000000001",
                    "question": key,
                    "member_id": str(person.member.id),
                },
            )
        )


async def test_list_count_and_mark_read(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org)
    await add(cami, "un")
    await add(cami, "deux")
    await add(cami, "ignoré", state="skipped")
    base = f"/api/orgs/{org.id}/notifications"

    body = (await cami.client.get(base)).json()
    assert body["unread"] == 2
    assert {n["question"] for n in body["items"]} == {"un", "deux"}
    assert all(n["read_at"] is None for n in body["items"])

    first = body["items"][0]["id"]
    assert (await cami.client.post(f"{base}/{first}/read")).status_code == 204
    body = (await cami.client.get(base)).json()
    assert body["unread"] == 1
    assert [n["read_at"] is not None for n in body["items"]].count(True) == 1

    assert (await cami.client.post(f"{base}/read")).status_code == 204
    assert (await cami.client.get(base)).json()["unread"] == 0


async def test_isolated_by_newsroom_and_account(make_org: MakeOrg, person: MakePerson) -> None:
    org, other = await make_org(), await make_org("Autre")
    cami, hugo = await person(org), await person(org)
    await add(cami, "pour-cami")
    await add(hugo, "pour-hugo")

    assert (await cami.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1
    # Not a member there: 404, so the newsroom's existence stays private.
    assert (await cami.client.get(f"/api/orgs/{other.id}/notifications")).status_code == 404

    async with transaction() as session:
        theirs = await notifications.listing(session, hugo.account.id, org.id)
    response = await cami.client.post(f"/api/orgs/{org.id}/notifications/{theirs[0].id}/read")
    assert response.status_code == 404
    assert (await hugo.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1
    assert (await cami.client.post(f"/api/orgs/{org.id}/notifications/read")).status_code == 204
    assert (await hugo.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1


async def test_second_newsroom_has_its_own_count(make_org: MakeOrg, person: MakePerson) -> None:
    org, other = await make_org(), await make_org("Autre")
    cami = await person(org)
    await add(cami, "ici")
    async with transaction() as session:
        session.add(
            Notification(
                account_id=cami.account.id,
                org_id=other.id,
                type="new_prono",
                dedupe_key="ailleurs",
                payload={"prono_id": "00000000-0000-0000-0000-000000000001", "question": "x"},
            )
        )
    assert (await cami.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1

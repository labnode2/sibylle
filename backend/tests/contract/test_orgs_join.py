import base64
import re
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from tests.conftest import ClientFor, MakeAccount
from tests.contract.helpers import (
    AVATAR,
    assert_no_private_data,
    create_org,
    notifications,
    token_from,
)

from sibylle import clock
from sibylle.db.models import Invitation, LedgerEntry, Membership, Organisation
from sibylle.db.session import transaction
from sibylle.domain.content import DEFAULT_LOGO

pytestmark = pytest.mark.contract

ACCESS_CODE = re.compile(r"^[A-Z]{1,6}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{3}$")


async def signed_in(make_account: MakeAccount, client_for: ClientFor) -> httpx.AsyncClient:
    return await client_for(await make_account())


async def invite_link(editor: httpx.AsyncClient, org_id: str, max_uses: int = 2) -> str:
    response = await editor.post(
        f"/api/orgs/{org_id}/invitations",
        json={
            "kind": "link",
            "max_uses": max_uses,
            "expires_at": (clock.now() + timedelta(days=7)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    url: str = response.json()["url"]
    return token_from(url)


def join_body(pseudo: str, **source: str) -> dict[str, Any]:
    return {**source, "pseudo": pseudo, "avatar": AVATAR, "charter_accepted": True}


async def test_creating_a_newsroom_makes_you_its_editor(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    ines = await signed_in(make_account, client_for)
    created = await create_org(ines)
    org, membership = created["org"], created["membership"]
    assert org["title"] == "Sophia Office"
    # No logo chosen: the default one, never an initial.
    assert org["logo"] == DEFAULT_LOGO
    assert ACCESS_CODE.match(org["access_code"]) and org["access_code"].startswith("SOPHIA-")
    assert (membership["role"], membership["pseudo"], membership["balance"]) == (
        "editor",
        "Inès",
        100,
    )

    async with transaction() as session:
        kinds = (
            await session.scalars(
                select(LedgerEntry.kind).where(LedgerEntry.membership_id == membership["id"])
            )
        ).all()
    assert kinds == ["starting_balance"]

    me = (await ines.get("/api/me")).json()
    assert [m["org"]["id"] for m in me["memberships"]] == [org["id"]]
    detail = (await ines.get(f"/api/orgs/{org['id']}")).json()
    assert detail["my_membership"]["role"] == "editor"
    # Its first day is the gazette's N° 1.
    assert (org["edition_number"], detail["edition_number"]) == (1, 1)


async def test_inviting_is_for_the_editor(make_account: MakeAccount, client_for: ClientFor) -> None:
    ines = await signed_in(make_account, client_for)
    org_id = (await create_org(ines))["org"]["id"]
    token = await invite_link(ines, org_id)
    cami = await signed_in(make_account, client_for)
    joined = await cami.post("/api/join", json=join_body("Cami", token=token))
    assert joined.status_code == 201

    org = (await cami.get(f"/api/orgs/{org_id}")).json()
    assert org["access_code"] is None  # only the editor sees the code
    response = await cami.post(
        f"/api/orgs/{org_id}/invitations",
        json={"kind": "link", "max_uses": 3, "expires_at": clock.now().isoformat()},
    )
    assert response.status_code == 403


async def test_join_by_link_with_preview(
    make_account: MakeAccount, client_for: ClientFor, fake_clock: clock.FakeClock
) -> None:
    ines = await signed_in(make_account, client_for)
    org_id = (await create_org(ines))["org"]["id"]
    token = await invite_link(ines, org_id, max_uses=2)

    cami = await signed_in(make_account, client_for)
    preview = (await cami.post("/api/join/preview", json={"token": token})).json()
    assert preview["org"]["title"] == "Sophia Office"
    assert (preview["places_left"], preview["member_count"]) == (2, 1)
    assert preview["invited_by_pseudo"] == "Inès"
    assert preview["charter"] and preview["already_member"] is False

    taken = await cami.post("/api/join", json=join_body("inès", token=token))
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "pseudo_taken"
    no_charter = await cami.post(
        "/api/join", json={**join_body("Cami", token=token), "charter_accepted": False}
    )
    assert no_charter.status_code == 422

    joined = await cami.post("/api/join", json=join_body("Cami", token=token))
    assert joined.status_code == 201
    membership = joined.json()["membership"]
    assert (membership["role"], membership["balance"], membership["pseudo"]) == (
        "reader",
        100,
        "Cami",
    )
    again = await cami.post("/api/join", json=join_body("Cami 2", token=token))
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_state"

    leo = await signed_in(make_account, client_for)
    assert (await leo.post("/api/join", json=join_body("Léo", token=token))).status_code == 201
    manon = await signed_in(make_account, client_for)
    full = await manon.post("/api/join", json=join_body("Manon", token=token))
    assert full.status_code == 409 and full.json()["error"]["code"] == "invitation_invalid"
    assert (await manon.post("/api/join/preview", json={"token": token})).status_code == 409


async def test_expired_or_revoked_links_are_refused(
    make_account: MakeAccount, client_for: ClientFor, fake_clock: clock.FakeClock
) -> None:
    ines = await signed_in(make_account, client_for)
    org_id = (await create_org(ines))["org"]["id"]
    expired = await invite_link(ines, org_id)
    revoked = await invite_link(ines, org_id)
    async with transaction() as session:
        await session.execute(
            update(Invitation)
            .where(Invitation.id == (await session.scalars(select(Invitation.id))).all()[-1])
            .values(revoked_at=clock.now())
        )
    fake_clock.advance(timedelta(days=8))
    cami = await signed_in(make_account, client_for)
    for token in (expired, revoked):
        response = await cami.post("/api/join", json=join_body("Cami", token=token))
        assert response.json()["error"]["code"] == "invitation_invalid"


async def test_join_by_access_code(make_account: MakeAccount, client_for: ClientFor) -> None:
    ines = await signed_in(make_account, client_for)
    org = (await create_org(ines))["org"]
    cami = await signed_in(make_account, client_for)
    preview = (await cami.post("/api/join/preview", json={"code": org["access_code"]})).json()
    assert preview["places_left"] is None and preview["invited_by_pseudo"] is None
    joined = await cami.post("/api/join", json=join_body("Cami", code=org["access_code"].lower()))
    assert joined.status_code == 201
    wrong = await cami.post("/api/join/preview", json={"code": "NOPE-AAA"})
    assert wrong.json()["error"]["code"] == "invitation_invalid"


async def test_join_by_nominative_invitation(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    ines = await signed_in(make_account, client_for)
    org_id = (await create_org(ines))["org"]["id"]
    response = await ines.post(
        f"/api/orgs/{org_id}/invitations", json={"kind": "email", "email": "hugo@exemple.fr"}
    )
    assert response.status_code == 201
    invitation = response.json()["invitation"]
    assert (invitation["max_uses"], invitation["email"]) == (1, "hugo@exemple.fr")
    [queued] = await notifications("invitation")
    assert queued.payload["to"] == "hugo@exemple.fr"
    assert queued.payload["inviter_pseudo"] == "Inès"
    token = token_from(queued.payload["link"])

    hugo = await signed_in(make_account, client_for)
    assert (await hugo.post("/api/join", json=join_body("Hugo", token=token))).status_code == 201
    other = await signed_in(make_account, client_for)
    used = await other.post("/api/join", json=join_body("Autre", token=token))
    assert used.json()["error"]["code"] == "invitation_invalid"


async def test_one_account_in_two_newsrooms(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    ines = await signed_in(make_account, client_for)
    sophia = (await create_org(ines))["org"]
    hugo = await signed_in(make_account, client_for)
    foot = (await create_org(hugo, title="Foot du jeudi", pseudo="Hugo"))["org"]
    async with transaction() as session:
        await session.execute(
            update(Organisation).where(Organisation.id == foot["id"]).values(starting_balance=50)
        )

    cami_account = await make_account()
    cami = await client_for(cami_account)
    await cami.post("/api/join", json=join_body("Cami", code=sophia["access_code"]))
    other_avatar = {**AVATAR, "pixels": base64.b64encode(bytes([2] * 256)).decode()}
    await cami.post(
        "/api/join",
        json={**join_body("Camille", code=foot["access_code"]), "avatar": other_avatar},
    )
    me = (await cami.get("/api/me")).json()
    by_title = {m["org"]["title"]: m["membership"] for m in me["memberships"]}
    assert by_title["Sophia Office"]["pseudo"] == "Cami"
    assert by_title["Foot du jeudi"]["pseudo"] == "Camille"
    assert by_title["Sophia Office"]["balance"] == 100
    assert by_title["Foot du jeudi"]["balance"] == 50
    assert by_title["Sophia Office"]["avatar"] != by_title["Foot du jeudi"]["avatar"]


async def test_members_and_profile(make_account: MakeAccount, client_for: ClientFor) -> None:
    ines = await signed_in(make_account, client_for)
    org = (await create_org(ines))["org"]
    cami = await signed_in(make_account, client_for)
    await cami.post("/api/join", json=join_body("Cami", code=org["access_code"]))

    members = (await cami.get(f"/api/orgs/{org['id']}/members")).json()
    assert sorted(m["pseudo"] for m in members) == ["Cami", "Inès"]
    assert_no_private_data(members)
    one = (await cami.get(f"/api/orgs/{org['id']}/members/{members[0]['id']}")).json()
    assert_no_private_data(one)

    renamed = await cami.patch(f"/api/orgs/{org['id']}/members/me", json={"pseudo": "Camille"})
    assert renamed.status_code == 200 and renamed.json()["pseudo"] == "Camille"
    taken = await cami.patch(f"/api/orgs/{org['id']}/members/me", json={"pseudo": "INÈS"})
    assert taken.json()["error"]["code"] == "pseudo_taken"
    bad = await cami.patch(
        f"/api/orgs/{org['id']}/members/me", json={"avatar": {**AVATAR, "pixels": "AA"}}
    )
    assert bad.status_code == 422


async def test_a_departed_member_comes_back_with_their_profile(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    ines = await signed_in(make_account, client_for)
    org = (await create_org(ines))["org"]
    cami = await signed_in(make_account, client_for)
    first = (await cami.post("/api/join", json=join_body("Cami", code=org["access_code"]))).json()
    async with transaction() as session:
        await session.execute(
            update(Membership)
            .where(Membership.id == first["membership"]["id"])
            .values(status="left", left_at=clock.now())
        )
    assert (await cami.get(f"/api/orgs/{org['id']}")).status_code == 404
    back = await cami.post("/api/join", json=join_body("Autre pseudo", code=org["access_code"]))
    assert back.status_code == 201
    membership = back.json()["membership"]
    assert (membership["id"], membership["pseudo"]) == (first["membership"]["id"], "Cami")


async def test_outsiders_get_404_everywhere(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    ines = await signed_in(make_account, client_for)
    org_id = (await create_org(ines))["org"]["id"]
    outsider = await signed_in(make_account, client_for)
    responses = [
        await outsider.get(f"/api/orgs/{org_id}"),
        await outsider.get(f"/api/orgs/{org_id}/members"),
        await outsider.patch(f"/api/orgs/{org_id}/members/me", json={"pseudo": "Intrus"}),
        await outsider.post(
            f"/api/orgs/{org_id}/invitations", json={"kind": "email", "email": "x@exemple.fr"}
        ),
    ]
    assert [r.status_code for r in responses] == [404, 404, 404, 404]
    assert all(r.json()["error"]["code"] == "not_found" for r in responses)


async def test_content_is_public(client: httpx.AsyncClient) -> None:
    content = (await client.get("/api/content")).json()
    assert len(content["avatars"]) == 7 and content["avatars"][0]["name"] == "Cami"
    assert "mer" in content["backgrounds"]
    assert "politique" in content["charter"]


async def test_joining_is_limited_per_account_not_per_office(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    """Someone guessing access codes is stopped after ten tries; their colleagues, who join from
    behind the same address (and through the same API process), are not."""
    from sibylle.main import create_app

    app = create_app()

    async def through_app(person: httpx.AsyncClient) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://testserver",
            headers=dict(person.headers),
        )
        client.cookies.set("sibylle_session", person.cookies.get("sibylle_session") or "")
        return client

    ines = await signed_in(make_account, client_for)
    code = (await create_org(ines))["org"]["access_code"]
    body = {"pseudo": "Devin", "avatar": AVATAR, "charter_accepted": True}
    async with await through_app(await signed_in(make_account, client_for)) as guesser:
        for attempt in range(10):
            wrong = await guesser.post("/api/join", json={**body, "code": f"FAUX-{attempt:03d}"})
            assert wrong.status_code == 409, wrong.text
        blocked = await guesser.post("/api/join", json={**body, "code": code})
        assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"
    for name in ("Cami", "Léo", "Manon"):
        async with await through_app(await signed_in(make_account, client_for)) as colleague:
            joined = await colleague.post("/api/join", json={**body, "code": code, "pseudo": name})
            assert joined.status_code == 201, joined.text

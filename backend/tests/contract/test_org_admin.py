from datetime import timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import ClientFor, MakeAccount, MakeOrg, MakePerson
from tests.contract.helpers import AVATAR, assert_no_private_data, token_from
from tests.contract.test_pronos import publish, section_id
from tests.contract.test_results import url

from sibylle import clock
from sibylle.domain.content import DEFAULT_LOGO, LOGO_TEMPLATES

pytestmark = pytest.mark.contract


def org_url(org_id: object, path: str = "") -> str:
    return f"/api/orgs/{org_id}{path}"


async def preview(client: httpx.AsyncClient, **source: str) -> int:
    return (await client.post("/api/join/preview", json=source)).status_code


async def test_the_card_and_the_laurels(
    make_org: MakeOrg,
    person: MakePerson,
    make_account: MakeAccount,
    client_for: ClientFor,
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    logo = LOGO_TEMPLATES[0]["image"]
    changes = {
        "title": "La Gazette du 3e",
        "background_key": "nuit",
        "logo": logo,
        "starting_balance": 150,
        "max_base_gain": 30,
        "early_bird_pct": 10,
        "early_bird_count": 3,
        "editor_note": "Pot vendredi à 18 h.",
        "charter": "Soyons bienveillants.",
    }
    response = await ines.client.patch(org_url(org.id), json=changes)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert {k: updated[k] for k in changes} == changes

    # A logo of her own, then none: the default logo comes back.
    drawn = await ines.client.patch(org_url(org.id), json={"logo": AVATAR})
    assert drawn.json()["logo"] == AVATAR
    removed = await ines.client.patch(org_url(org.id), json={"logo": None})
    assert removed.status_code == 200, removed.text
    assert removed.json()["logo"] == DEFAULT_LOGO

    for field, value in [
        ("title", ""),
        ("title", "x" * 41),
        ("starting_balance", -1),
        ("max_base_gain", -5),
        ("early_bird_pct", 101),
        ("early_bird_count", -1),
        ("background_key", "lune"),
        ("logo", {**logo, "pixels": "pas-du-tout"}),
        ("charter", ""),
    ]:
        refused = await ines.client.patch(org_url(org.id), json={field: value})
        assert refused.status_code == 422, (field, value, refused.text)

    # The new ceiling applies to the next pronos.
    over = await hugo.client.post(
        org_url(org.id, "/pronos"),
        json={
            "kind": "yes_no",
            "question": "Le pot aura-t-il lieu ?",
            "section_id": await section_id(hugo.client, str(org.id)),
            "base_gain": 40,
            "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
        },
    )
    assert over.status_code == 422 and "base_gain" in over.json()["error"]["fields"]

    # The new starting balance applies to whoever arrives next.
    code = (await ines.client.post(org_url(org.id, "/access-code"))).json()["access_code"]
    newcomer = await client_for(await make_account())
    joined = await newcomer.post(
        "/api/join",
        json={
            "code": code,
            "pseudo": "Zoé",
            "avatar": AVATAR,
            "charter_accepted": True,
        },
    )
    assert joined.status_code == 201, joined.text
    assert joined.json()["membership"]["balance"] == 150


async def test_the_access_code(
    make_org: MakeOrg, person: MakePerson, make_account: MakeAccount, client_for: ClientFor
) -> None:
    org = await make_org()
    ines = await person(org, "editor")
    outsider = await client_for(await make_account())
    old = (await ines.client.post(org_url(org.id, "/access-code"))).json()["access_code"]

    renewed = await ines.client.post(org_url(org.id, "/access-code"))
    assert renewed.status_code == 200, renewed.text
    new = renewed.json()["access_code"]
    assert new != old
    assert await preview(outsider, code=old) == 409
    assert await preview(outsider, code=new) == 200

    assert (await ines.client.delete(org_url(org.id, "/access-code"))).status_code == 204
    assert (await ines.client.get(org_url(org.id))).json()["access_code"] is None
    assert await preview(outsider, code=new) == 409


async def test_listing_and_revoking_invitations(
    make_org: MakeOrg, person: MakePerson, make_account: MakeAccount, client_for: ClientFor
) -> None:
    org = await make_org()
    ines = await person(org, "editor")
    outsider = await client_for(await make_account())
    created = await ines.client.post(
        org_url(org.id, "/invitations"),
        json={
            "kind": "link",
            "max_uses": 5,
            "expires_at": (clock.now() + timedelta(days=7)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    invitation = created.json()["invitation"]
    token = token_from(created.json()["url"])
    listed = (await ines.client.get(org_url(org.id, "/invitations"))).json()
    assert [(i["id"], i["places_left"], i["revoked_at"]) for i in listed] == [
        (invitation["id"], 5, None)
    ]

    path = org_url(org.id, f"/invitations/{invitation['id']}")
    assert (await ines.client.delete(path)).status_code == 204
    assert (await ines.client.get(org_url(org.id, "/invitations"))).json()[0]["revoked_at"]
    assert await preview(outsider, token=token) == 409
    other = await make_org("Autre rédaction")
    stranger = await person(other, "editor")
    assert (
        await stranger.client.delete(org_url(other.id, f"/invitations/{invitation['id']}"))
    ).status_code == 404


async def test_roles_and_the_last_editor(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    role = org_url(org.id, f"/members/{cami.member.id}/role")

    promoted = await ines.client.patch(role, json={"role": "journalist"})
    assert promoted.status_code == 200, promoted.text
    assert (promoted.json()["pseudo"], promoted.json()["role"]) == ("Cami", "journalist")
    # Cami publishes straight away.
    assert (await publish(cami.client, str(org.id)))["state"] == "open"
    assert (await ines.client.patch(role, json={"role": "admin"})).status_code == 422

    # The newsroom always keeps an editor.
    mine = org_url(org.id, f"/members/{ines.member.id}/role")
    alone = await ines.client.patch(mine, json={"role": "reader"})
    assert alone.status_code == 409 and alone.json()["error"]["code"] == "last_editor"
    assert (await ines.client.patch(role, json={"role": "editor"})).status_code == 200
    assert (await ines.client.patch(mine, json={"role": "journalist"})).status_code == 200
    # Inès is a journalist now: the members are no longer hers to manage.
    assert (await ines.client.patch(role, json={"role": "reader"})).status_code == 403

    outsider = await person(await make_org("Autre rédaction"))
    assert (
        await cami.client.patch(
            org_url(org.id, f"/members/{outsider.member.id}/role"), json={"role": "reader"}
        )
    ).status_code == 404


async def test_removing_a_member(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    leo = await person(org, "reader", "Léo")
    assert (
        await ines.client.delete(org_url(org.id, f"/members/{leo.member.id}"))
    ).status_code == 204
    assert (await leo.client.get(org_url(org.id))).status_code == 404
    pseudos = [m["pseudo"] for m in (await ines.client.get(org_url(org.id, "/members"))).json()]
    assert pseudos == ["Inès"]
    last = await ines.client.delete(org_url(org.id, f"/members/{ines.member.id}"))
    assert last.status_code == 409 and last.json()["error"]["code"] == "last_editor"


async def test_adjustments_and_the_ledger(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    leo = await person(org, "reader", "Léo")
    adjust = org_url(org.id, f"/members/{leo.member.id}/adjustments")

    taken = await ines.client.post(adjust, json={"amount": -15, "reason": "erreur de saisie"})
    assert taken.status_code == 201, taken.text
    entry = taken.json()
    assert (entry["kind"], entry["amount"], entry["score_delta"], entry["reason"]) == (
        "adjustment",
        -15,
        0,
        "erreur de saisie",
    )
    me = (await leo.client.get(org_url(org.id))).json()["my_membership"]
    assert (me["balance"], me["season_score"]) == (85, 0)
    for body in ({"amount": 0, "reason": "rien"}, {"amount": 5}, {"amount": 5, "reason": "  "}):
        assert (await ines.client.post(adjust, json=body)).status_code == 422, body

    # Léo's statement, newest first, one page at a time.
    ledger = org_url(org.id, "/members/me/ledger")
    first = (await leo.client.get(ledger, params={"limit": 1})).json()
    assert [(e["kind"], e["amount"], e["reason"]) for e in first["items"]] == [
        ("adjustment", -15, "erreur de saisie")
    ]
    assert first["next_cursor"]
    second = (
        await leo.client.get(ledger, params={"limit": 1, "cursor": first["next_cursor"]})
    ).json()
    assert [(e["kind"], e["amount"]) for e in second["items"]] == [("starting_balance", 100)]
    assert second["next_cursor"] is None
    # Everyone reads their own statement only.
    assert [e["kind"] for e in (await ines.client.get(ledger)).json()["items"]] == [
        "starting_balance"
    ]


async def test_sections(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor")
    hugo = await person(org, "journalist")
    sections = org_url(org.id, "/sections")

    foot = await ines.client.post(sections, json={"name": "Foot"})
    assert foot.status_code == 201, foot.text
    assert foot.json()["position"] == 1
    taken = await ines.client.post(sections, json={"name": "FOOT"})
    assert taken.status_code == 422 and "name" in taken.json()["error"]["fields"]
    office = (await ines.client.post(sections, json={"name": "Bureau"})).json()

    renamed = await ines.client.patch(
        f"{sections}/{foot.json()['id']}", json={"name": "Football", "position": 0}
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Football"
    assert [s["name"] for s in (await ines.client.get(sections)).json()] == [
        "Football",
        "Général",
        "Bureau",
    ]

    # A section in use is archived: its pronos keep it, the list drops it.
    prono = (
        await hugo.client.post(
            org_url(org.id, "/pronos"),
            json={
                "kind": "yes_no",
                "question": "L'OM gagnera-t-il ?",
                "section_id": foot.json()["id"],
                "base_gain": 20,
                "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
            },
        )
    ).json()
    assert (await ines.client.delete(f"{sections}/{foot.json()['id']}")).status_code == 204
    assert (await ines.client.delete(f"{sections}/{office['id']}")).status_code == 204
    assert [s["name"] for s in (await ines.client.get(sections)).json()] == ["Général"]
    assert (await hugo.client.get(url(org.id, prono["id"]))).json()["section"]["name"] == "Football"
    # The last one stays: a prono needs a section.
    general = (await ines.client.get(sections)).json()[0]["id"]
    assert (await ines.client.delete(f"{sections}/{general}")).status_code == 409


async def test_handling_reports(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    report = url(org.id, prono["id"], "reports")
    first = (
        await cami.client.post(report, json={"kind": "result_error", "message": "C'était Nice !"})
    ).json()
    second = (await cami.client.post(report, json={"kind": "content"})).json()

    open_reports = (
        await ines.client.get(org_url(org.id, "/reports"), params={"state": "open"})
    ).json()
    assert_no_private_data(open_reports)
    assert [(r["id"], r["prono"]["question"], r["reporter"]["pseudo"]) for r in open_reports] == [
        (second["id"], prono["question"], "Cami"),
        (first["id"], prono["question"], "Cami"),
    ]

    handled = await ines.client.post(
        org_url(org.id, f"/reports/{first['id']}/handle"),
        json={"state": "resolved", "note": "Résultat corrigé."},
    )
    assert handled.status_code == 200, handled.text
    assert (handled.json()["state"], handled.json()["resolution_note"]) == (
        "resolved",
        "Résultat corrigé.",
    )
    dismissed = await ines.client.post(
        org_url(org.id, f"/reports/{second['id']}/handle"), json={"state": "dismissed"}
    )
    assert dismissed.json()["state"] == "dismissed"
    again = await ines.client.post(
        org_url(org.id, f"/reports/{first['id']}/handle"), json={"state": "dismissed"}
    )
    assert again.status_code == 409
    assert (
        await ines.client.get(org_url(org.id, "/reports"), params={"state": "open"})
    ).json() == []

    # Cami sees what became of her reports on the prono.
    mine = (await cami.client.get(url(org.id, prono["id"]))).json()["my_reports"]
    assert sorted((r["kind"], r["state"], r["resolution_note"]) for r in mine) == [
        ("content", "dismissed", None),
        ("result_error", "resolved", "Résultat corrigé."),
    ]
    assert (await hugo.client.get(url(org.id, prono["id"]))).json()["my_reports"] == []


async def test_admin_routes_are_for_the_editor_only(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor")
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    invitation = (
        await ines.client.post(
            org_url(org.id, "/invitations"),
            json={
                "kind": "link",
                "max_uses": 1,
                "expires_at": (clock.now() + timedelta(days=1)).isoformat(),
            },
        )
    ).json()["invitation"]
    general = (await ines.client.get(org_url(org.id, "/sections"))).json()[0]["id"]
    prono = await publish(hugo.client, str(org.id))
    report = (
        await cami.client.post(url(org.id, prono["id"], "reports"), json={"kind": "content"})
    ).json()
    calls: list[tuple[str, str, dict[str, Any] | None]] = [
        ("PATCH", org_url(org.id), {"title": "Prise de pouvoir"}),
        ("POST", org_url(org.id, "/access-code"), None),
        ("DELETE", org_url(org.id, "/access-code"), None),
        ("GET", org_url(org.id, "/invitations"), None),
        ("DELETE", org_url(org.id, f"/invitations/{invitation['id']}"), None),
        ("PATCH", org_url(org.id, f"/members/{cami.member.id}/role"), {"role": "editor"}),
        ("DELETE", org_url(org.id, f"/members/{ines.member.id}"), None),
        (
            "POST",
            org_url(org.id, f"/members/{cami.member.id}/adjustments"),
            {"amount": 100, "reason": "merci"},
        ),
        ("POST", org_url(org.id, "/sections"), {"name": "Ailleurs"}),
        ("PATCH", org_url(org.id, f"/sections/{general}"), {"name": "Ailleurs"}),
        ("DELETE", org_url(org.id, f"/sections/{general}"), None),
        ("GET", org_url(org.id, "/reports"), None),
        ("POST", org_url(org.id, f"/reports/{report['id']}/handle"), {"state": "dismissed"}),
    ]
    for who in (hugo, cami):
        for method, path, body in calls:
            response = await who.client.request(method, path, json=body)
            assert response.status_code == 403, (who.member.role, method, path, response.text)
        # The statement is everyone's, for themselves.
        assert (await who.client.get(org_url(org.id, "/members/me/ledger"))).status_code == 200

"""Editing a prono (FR-035): all of it before the first bet; then, until its result or its
cancellation, only what keeps the meaning of the bets. Each edit goes into its history."""

from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import MakeOrg, MakePerson
from tests.contract.test_pronos import place, png, publish

from sibylle import clock
from sibylle.worker.jobs import advance_pronos

pytestmark = pytest.mark.contract

LOCKED = ["kind", "options", "open_ended", "base_gain", "number_unit", "opens_at"]


def at(days: float) -> str:
    return (clock.now() + timedelta(days=days)).isoformat()


async def published(client: httpx.AsyncClient, org_id: str, **changes: Any) -> dict[str, Any]:
    """A prono just published, with the address of its page in the API (`url`)."""
    prono = await publish(client, org_id, **changes)
    return {**prono, "url": f"/api/orgs/{org_id}/pronos/{prono['id']}"}


async def edit(client: httpx.AsyncClient, prono: dict[str, Any], **body: Any) -> httpx.Response:
    return await client.patch(prono["url"], json=body)


async def read(client: httpx.AsyncClient, prono: dict[str, Any]) -> dict[str, Any]:
    response = await client.get(prono["url"])
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


def edits(detail: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in detail["events"] if e["kind"] == "edited"]


async def test_before_the_first_bet_everything_changes(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    lea = await person(org, "journalist", "Léa")
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    prono = await published(hugo.client, str(org.id))
    assert (prono["can_edit"], prono["locked_fields"]) == (True, [])
    assert (await read(cami.client, prono))["can_edit"] is False

    changed = await edit(
        hugo.client, prono, kind="yes_no", options=[], base_gain=30, question="Nice gagne ?"
    )
    assert changed.status_code == 200, changed.text
    detail = changed.json()
    assert (detail["kind"], detail["base_gain"], detail["question"]) == (
        "yes_no",
        30,
        "Nice gagne ?",
    )
    assert [o["label"] for o in detail["options"]] == ["Oui", "Non"]
    [edited] = edits(detail)
    assert edited["by"]["pseudo"] == "Hugo"
    assert edited["data"]["changes"] == [
        {"field": "question", "before": "Nice ou Monaco samedi ?", "after": "Nice gagne ?"},
        {"field": "kind", "before": "choice", "after": "yes_no"},
        {"field": "options", "before": ["Nice", "Nul", "Monaco"], "after": ["Oui", "Non"]},
        {"field": "base_gain", "before": 20, "after": 30},
    ]

    # The author in the newsroom or the editor, as before.
    assert (await edit(cami.client, prono, question="Pas moi ?")).status_code == 403
    assert (await edit(lea.client, prono, question="Pas moi non plus ?")).status_code == 403
    assert (await edit(ines.client, prono, question="Nice gagnera ?")).status_code == 200


async def test_after_bets_the_wording_and_the_dates_change(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    closes_at = at(3)
    prono = await published(hugo.client, str(org.id), closes_at=closes_at)
    foot = await ines.client.post(f"/api/orgs/{org.id}/sections", json={"name": "Foot"})
    assert foot.status_code == 201
    image = await hugo.client.post(
        f"/api/orgs/{org.id}/uploads", files={"file": ("affiche.png", png((40, 20)), "image/png")}
    )
    nice = prono["options"][0]["id"]
    assert (
        await place(cami.client, str(org.id), prono["id"], option_id=nice, stake=20)
    ).status_code == 201
    before = await read(hugo.client, prono)
    assert (before["can_edit"], before["locked_fields"]) == (True, LOCKED)

    later = at(5)
    changed = await edit(
        hugo.client,
        prono,
        question="Nice ou Monaco, dimanche ?",
        section_id=foot.json()["id"],
        link_url="https://exemple.fr/derby",
        image_id=image.json()["id"],
        closes_at=later,
        result_expected_at=at(6),
    )
    assert changed.status_code == 200, changed.text
    detail = changed.json()
    assert detail["question"] == "Nice ou Monaco, dimanche ?"
    assert detail["section"]["name"] == "Foot"
    assert detail["link_url"] == "https://exemple.fr/derby"
    assert detail["image_url"].endswith(image.json()["id"])
    assert datetime.fromisoformat(detail["closes_at"]) == datetime.fromisoformat(later)
    # The bets stay as they were, on the same answers.
    assert [o["id"] for o in detail["options"]] == [o["id"] for o in prono["options"]]
    assert [(b["member"]["pseudo"], b["answer"], b["stake"]) for b in detail["bets"]] == [
        ("Cami", "Nice", 20)
    ]
    assert (detail["pot"], detail["bet_count"]) == (20, 1)

    # Every member reads what changed, before and after.
    [edited] = edits(await read(cami.client, prono))
    assert edited["by"]["pseudo"] == "Hugo"
    changes = {c["field"]: (c["before"], c["after"]) for c in edited["data"]["changes"]}
    assert list(changes) == [
        "question",
        "section",
        "closes_at",
        "result_expected_at",
        "link_url",
        "image",
    ]
    assert changes["question"] == ("Nice ou Monaco samedi ?", "Nice ou Monaco, dimanche ?")
    assert changes["section"] == ("Général", "Foot")
    old, new = changes["closes_at"]
    assert (datetime.fromisoformat(old), datetime.fromisoformat(new)) == (
        datetime.fromisoformat(closes_at),
        datetime.fromisoformat(later),
    )
    assert changes["link_url"] == (None, "https://exemple.fr/derby")
    assert changes["image"] == (None, image.json()["id"])

    # Postponed again by the editor, then the image taken away.
    assert (
        await edit(ines.client, prono, closes_at=at(7), result_expected_at=None)
    ).status_code == 200
    assert (await edit(ines.client, prono, image_id=None)).status_code == 200
    detail = await read(cami.client, prono)
    assert detail["image_url"] is None and detail["result_expected_at"] is None
    assert [e["by"]["pseudo"] for e in edits(detail)] == ["Hugo", "Inès", "Inès"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"kind": "yes_no", "options": []}, "kind"),
        ({"options": ["Nice", "Monaco"]}, "options"),
        ({"options": ["Nice", "Nul", "Monaco", "Lyon"]}, "options"),
        ({"base_gain": 30}, "base_gain"),
        ({"base_gain": 0}, "base_gain"),
        ({"opens_at": "2020-01-01T10:00:00+00:00"}, "opens_at"),
        ({"number_unit": "buts"}, "number_unit"),
    ],
)
async def test_after_bets_what_was_bet_on_is_refused(
    make_org: MakeOrg, person: MakePerson, body: dict[str, Any], field: str
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await published(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=prono["options"][0]["id"], stake=1)

    refused = await edit(hugo.client, prono, question="Nice ou Monaco dimanche ?", **body)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "validation_error"
    assert refused.json()["error"]["fields"][field] == "locked_after_bets"
    # Nothing changed, not even the question asked with it.
    detail = await read(hugo.client, prono)
    assert detail["question"] == "Nice ou Monaco samedi ?" and edits(detail) == []
    assert [o["label"] for o in detail["options"]] == ["Nice", "Nul", "Monaco"]


async def test_after_bets_an_open_ended_date_stays_open_ended(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await published(
        hugo.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    tomorrow = (clock.now() + timedelta(days=1)).date().isoformat()
    await place(cami.client, str(org.id), prono["id"], date_value=tomorrow, stake=1)
    refused = await edit(hugo.client, prono, open_ended=False, closes_at=at(3))
    assert refused.json()["error"]["fields"]["open_ended"] == "locked_after_bets"
    assert (await edit(hugo.client, prono, question="Quand pleuvra-t-il ?")).status_code == 200


async def test_after_bets_the_closing_is_only_postponed(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await published(hugo.client, str(org.id), closes_at=at(3))
    await place(cami.client, str(org.id), prono["id"], option_id=prono["options"][0]["id"], stake=1)
    for closing in (at(2), at(-1)):
        refused = await edit(hugo.client, prono, closes_at=closing)
        assert refused.status_code == 422
        assert refused.json()["error"]["fields"] == {"closes_at": "not_later"}
    # A result expected before the new closing is refused, as at the publication.
    early = await edit(hugo.client, prono, closes_at=at(5), result_expected_at=at(4))
    assert early.json()["error"]["fields"] == {"result_expected_at": "before_closing"}
    assert (await edit(hugo.client, prono, closes_at=at(5))).status_code == 200


async def test_a_closed_prono_is_reworded_until_its_result(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await published(hugo.client, str(org.id), closes_at=at(1))
    nice = prono["options"][0]["id"]
    await place(cami.client, str(org.id), prono["id"], option_id=nice, stake=10)
    fake_clock.advance(timedelta(days=2))
    await advance_pronos()
    closed = await read(hugo.client, prono)
    assert closed["state"] == "closed"
    assert (closed["can_edit"], closed["locked_fields"]) == (True, [*LOCKED, "closes_at"])

    # Its closing is past and stays: a relaunch reopens the bets, not an edit.
    reworded = await edit(
        hugo.client, prono, question="Nice ou Monaco, samedi ?", result_expected_at=at(1)
    )
    assert reworded.status_code == 200, reworded.text
    assert reworded.json()["state"] == "closed"
    refused = await edit(hugo.client, prono, closes_at=at(3), result_expected_at=at(4))
    assert refused.json()["error"]["fields"] == {"closes_at": "locked_after_bets"}

    resolved = await hugo.client.post(
        f"{prono['url']}/resolve", json={"correct_option_ids": [nice]}
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["can_edit"] is False
    after = await edit(hugo.client, prono, question="Nice ou Monaco, enfin ?")
    assert after.status_code == 409 and after.json()["error"]["code"] == "invalid_state"


async def test_a_cancelled_prono_is_not_edited(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    ines = await person(org, "editor")
    cami = await person(org, "reader")
    prono = await published(hugo.client, str(org.id))
    await place(
        cami.client, str(org.id), prono["id"], option_id=prono["options"][0]["id"], stake=10
    )
    cancelled = await ines.client.post(f"{prono['url']}/cancel", json={"reason": "Match annulé"})
    assert cancelled.status_code == 200, cancelled.text
    for client in (hugo.client, ines.client):
        refused = await edit(client, prono, question="Nice ou Monaco, un jour ?")
        assert refused.status_code == 409 and refused.json()["error"]["code"] == "invalid_state"


async def test_an_edit_that_changes_nothing_leaves_no_trace(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await published(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=prono["options"][0]["id"], stake=1)
    # The whole prono sent back as it is, locked fields included.
    same = await edit(
        hugo.client,
        prono,
        kind="choice",
        question="  Nice ou Monaco samedi ? ",
        options=["Nice", "Nul", "Monaco"],
        base_gain=20,
        closes_at=prono["closes_at"],
        open_ended=False,
    )
    assert same.status_code == 200, same.text
    assert edits(same.json()) == []


async def test_an_edit_keeps_what_a_prono_needs(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    ines = await person(org, "editor")
    prono = await published(hugo.client, str(org.id))
    for field in ("question", "section_id", "kind", "base_gain", "open_ended"):
        refused = await edit(hugo.client, prono, **{field: None})
        assert refused.status_code == 422
        assert refused.json()["error"]["fields"] == {field: "missing"}

    # Its section archived since stays, as long as the edit leaves it.
    other = await ines.client.post(f"/api/orgs/{org.id}/sections", json={"name": "Foot"})
    general = prono["section"]["id"]
    deleted = await ines.client.delete(f"/api/orgs/{org.id}/sections/{general}")
    assert deleted.status_code == 204
    assert (await edit(hugo.client, prono, question="Nice ou Monaco dimanche ?")).status_code == 200
    back = await edit(hugo.client, prono, section_id=general)
    assert back.status_code == 200
    moved = await edit(hugo.client, prono, section_id=other.json()["id"])
    assert moved.status_code == 200
    gone = await edit(hugo.client, prono, section_id=general)
    assert gone.json()["error"]["fields"] == {"section_id": "unknown"}

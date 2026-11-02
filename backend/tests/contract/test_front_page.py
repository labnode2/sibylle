from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import assert_no_private_data
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url

from sybille import clock
from sybille.db.models import Organisation
from sybille.db.session import transaction
from sybille.worker.jobs import advance_pronos

pytestmark = pytest.mark.contract


async def front(client: httpx.AsyncClient, org_id: object) -> dict[str, Any]:
    response = await client.get(f"/api/orgs/{org_id}/front-page")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert_no_private_data(body)
    return body


def questions(pronos: list[dict[str, Any]]) -> list[str]:
    return [p["question"] for p in pronos]


def in_hours(hours: float) -> str:
    return (clock.now() + timedelta(hours=hours)).isoformat()


async def test_the_front_page_in_order(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await person(org, "reader", "Manon")
    await person(org, "reader", "Zoé")

    await publish(hugo.client, org_id, question="Qui gagne le baby-foot ?", closes_at=in_hours(72))
    await publish(hugo.client, org_id, question="Combien de cafés jeudi ?", closes_at=in_hours(26))
    await publish(
        hugo.client,
        org_id,
        kind="date",
        options=[],
        question="Quand la machine sera-t-elle réparée ?",
        open_ended=True,
        closes_at=None,
    )
    await publish(
        hugo.client,
        org_id,
        question="Le séminaire aura-t-il lieu ?",
        opens_at=in_hours(48),
        closes_at=in_hours(120),
    )
    soon = await publish(
        hugo.client, org_id, question="Le bouclage avant 20 h ?", closes_at=in_hours(2)
    )
    await place(cami.client, org_id, soon["id"], option_id=option(soon, "Nice"), stake=0)
    await publish(hugo.client, org_id, question="Le pot aura-t-il lieu ?", closes_at=in_hours(1))
    done = await publish(hugo.client, org_id, question="Nice ou Monaco ?", closes_at=in_hours(1))
    await place(cami.client, org_id, done["id"], option_id=option(done, "Nice"), stake=10)
    await place(leo.client, org_id, done["id"], option_id=option(done, "Monaco"), stake=10)
    await publish(cami.client, org_id, question="Une proposition de Cami ?")
    async with transaction() as session:
        await session.execute(
            update(Organisation)
            .where(Organisation.id == org.id)
            .values(editor_note="Pot de départ vendredi à 18 h.")
        )

    fake_clock.advance(timedelta(hours=3))
    await advance_pronos()
    resolved = await hugo.client.post(
        url(org.id, done["id"], "resolve"), json={"correct_option_ids": [option(done, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text

    page = await front(cami.client, org.id)
    # The headline closes first; open-ended and scheduled pronos come after or not at all.
    assert page["headline"]["question"] == "Combien de cafés jeudi ?"
    assert questions(page["open"]) == [
        "Qui gagne le baby-foot ?",
        "Quand la machine sera-t-elle réparée ?",
    ]
    assert page["to_designate"] is None
    [result] = page["latest_results"]
    assert (result["prono"]["question"], result["result"]) == ("Nice ou Monaco ?", "Nice")
    assert (result["my_outcome"], result["my_payout"]) == ("won", 40)
    assert [
        (r["rank"], r["member"]["pseudo"], r["value"], r["is_me"]) for r in page["leaderboard_top"]
    ] == [
        (1, "Cami", 30, True),
        (2, "Hugo", 0, False),
        (2, "Manon", 0, False),
    ]
    assert page["games"] == []
    assert page["editor_note"] == "Pot de départ vendredi à 18 h."
    assert list(page) == [
        "headline",
        "open",
        "to_designate",
        "latest_results",
        "leaderboard_top",
        "games",
        "editor_note",
    ]

    # Journalists also see what waits for a result, the oldest closing first.
    newsroom = await front(hugo.client, org.id)
    assert questions(newsroom["to_designate"]) == [
        "Le pot aura-t-il lieu ?",
        "Le bouclage avant 20 h ?",
    ]
    assert newsroom["latest_results"][0]["my_outcome"] is None

    # Léo lost and is fifth: the top three, then his own line.
    seen_by_leo = await front(leo.client, org.id)
    assert (
        seen_by_leo["latest_results"][0]["my_outcome"],
        seen_by_leo["latest_results"][0]["my_payout"],
    ) == ("lost", 0)
    assert [
        (r["rank"], r["member"]["pseudo"], r["is_me"]) for r in seen_by_leo["leaderboard_top"]
    ] == [
        (1, "Cami", False),
        (2, "Hugo", False),
        (2, "Manon", False),
        (5, "Léo", True),
    ]


async def test_an_empty_newsroom(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    page = await front(cami.client, org.id)
    assert (page["headline"], page["open"], page["latest_results"], page["editor_note"]) == (
        None,
        [],
        [],
        None,
    )


async def test_outsiders_get_404(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    await person(org)
    outsider = await person(await make_org("Autre rédaction"))
    assert (await outsider.client.get(f"/api/orgs/{org.id}/front-page")).status_code == 404

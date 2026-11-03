"""The ball's race over HTTP (US9): five runs a week, scores checked, the week paid once."""

from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from tests.conftest import MakeOrg, MakePerson, Person

from sibylle import clock
from sibylle.db.models import LedgerEntry, Membership
from sibylle.db.session import transaction
from sibylle.domain.seasons import PARIS
from sibylle.services.ledger import check_caches
from sibylle.worker.jobs import pay_runner_week

pytestmark = pytest.mark.contract


def games(org_id: object) -> str:
    return f"/api/orgs/{org_id}/games"


async def start(person: Person, org_id: object) -> httpx.Response:
    return await person.client.post(f"{games(org_id)}/runner/runs")


async def finish(
    person: Person, org_id: object, run_id: str, score: int, duration_ms: int = 20_000
) -> httpx.Response:
    return await person.client.post(
        f"{games(org_id)}/runner/runs/{run_id}/finish",
        json={"score": score, "duration_ms": duration_ms},
    )


async def play(
    person: Person, org_id: object, score: int, fake_clock: clock.FakeClock
) -> dict[str, Any]:
    started = await start(person, org_id)
    assert started.status_code == 201, started.text
    fake_clock.advance(timedelta(seconds=30))
    finished = await finish(person, org_id, started.json()["run_id"], score)
    assert finished.status_code == 200, finished.text
    data: dict[str, Any] = finished.json()
    return data


async def runner(person: Person, org_id: object) -> dict[str, Any]:
    response = await person.client.get(games(org_id))
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    assert data["pixel"] is None
    return data["runner"]  # type: ignore[no-any-return]


async def test_five_runs_a_week_and_the_best_one_counts(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    assert await runner(cami, org.id) == {
        "week_start": "2026-11-02",
        "attempts_left": 5,
        "my_best": None,
        "top": [],
    }

    started = await start(cami, org.id)
    assert started.status_code == 201
    assert isinstance(started.json()["seed"], int)
    fake_clock.advance(timedelta(seconds=30))
    first = await finish(cami, org.id, started.json()["run_id"], 400)
    assert first.json() == {"score": 400, "my_best": 400, "rank": 1}
    # A run is finished once.
    again = await finish(cami, org.id, started.json()["run_id"], 900)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "run_finished"
    # Nobody else finishes it.
    assert (await finish(leo, org.id, started.json()["run_id"], 10)).status_code == 404

    assert (await play(cami, org.id, 250, fake_clock))["my_best"] == 400
    assert (await play(leo, org.id, 600, fake_clock))["rank"] == 1
    for _ in range(3):
        assert (await start(cami, org.id)).status_code == 201  # abandoned runs count too
    exhausted = await start(cami, org.id)
    assert exhausted.status_code == 409
    assert exhausted.json()["error"]["code"] == "attempts_exhausted"

    mine = await runner(cami, org.id)
    assert (mine["attempts_left"], mine["my_best"]) == (0, 400)
    assert [(row["member"]["pseudo"], row["score"], row["rank"]) for row in mine["top"]] == [
        ("Léo", 600, 1),
        ("Cami", 400, 2),
    ]

    # A new week, five new attempts.
    fake_clock.set(datetime(2026, 11, 9, 0, 0, tzinfo=PARIS))
    fresh = await runner(cami, org.id)
    assert (fresh["week_start"], fresh["attempts_left"]) == ("2026-11-09", 5)
    assert fresh["my_best"] is None


async def test_an_impossible_score_is_refused(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    run_id = (await start(cami, org.id)).json()["run_id"]
    fake_clock.advance(timedelta(seconds=30))
    # 20 seconds cannot give 10 000 points.
    too_high = await finish(cami, org.id, run_id, 10_000)
    assert too_high.status_code == 422
    assert "score" in too_high.json()["error"]["fields"]
    # Nor can a run last longer than the time since it started.
    too_long = await finish(cami, org.id, run_id, 100, duration_ms=60_000)
    assert too_long.status_code == 422
    assert "duration_ms" in too_long.json()["error"]["fields"]

    # Past 30 minutes, the run can no longer be finished.
    late = (await start(cami, org.id)).json()["run_id"]
    fake_clock.advance(timedelta(minutes=31))
    expired = await finish(cami, org.id, late, 100)
    assert expired.status_code == 422
    assert "duration_ms" in expired.json()["error"]["fields"]


async def balances(*people: Person) -> list[tuple[int, int]]:
    async with transaction() as session:
        members = [await session.get(Membership, p.member.id) for p in people]
        return [(m.balance, m.season_score) for m in members if m is not None]


async def test_monday_pays_the_week_once_to_the_balance_only(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    cami, leo, manon, hugo, zoe = [
        await person(org, "reader", name) for name in ("Cami", "Léo", "Manon", "Hugo", "Zoé")
    ]
    for player, score in ((cami, 800), (leo, 500), (manon, 300), (hugo, 120), (cami, 200)):
        await play(player, org.id, score, fake_clock)
    await start(zoe, org.id)  # never finished: not a player
    other = await make_org("Autre Rédac")
    stranger = await person(other, "reader", "Inconnu")
    await play(stranger, other.id, 50, fake_clock)

    # Sunday evening: nothing yet.
    fake_clock.set(datetime(2026, 11, 8, 23, 0, tzinfo=PARIS))
    assert await pay_runner_week() == 0
    # Monday, once the week's last runs are over.
    fake_clock.set(datetime(2026, 11, 9, 0, 30, tzinfo=PARIS))
    assert await pay_runner_week() == 5
    assert await pay_runner_week() == 0
    assert await balances(cami, leo, manon, hugo, zoe, stranger) == [
        (110, 0),
        (107, 0),
        (105, 0),
        (102, 0),
        (100, 0),
        (110, 0),
    ]
    async with transaction() as session:
        kinds = (
            await session.scalars(
                select(LedgerEntry.reason).where(
                    LedgerEntry.membership_id == cami.member.id, LedgerEntry.kind == "minigame"
                )
            )
        ).all()
        assert kinds == ["runner:2026-11-02"]
        assert await check_caches(session, org.id) == []


async def test_the_race_needs_a_member(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    other = await make_org("Autre Rédac")
    stranger = await person(other, "reader")
    assert (await stranger.client.get(games(org.id))).status_code == 404
    assert (await start(stranger, org.id)).status_code == 404

"""The games of each week over HTTP (US12, research.md J7): the editor plans this week and the
three after it, an ordinary week covers the rest, members see and play only the week's games,
and a game taken out of the current week cancels its week."""

import base64
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import MakeOrg, MakePerson, Person

from sibylle import clock
from sibylle.db.models import Membership
from sibylle.db.session import transaction
from sibylle.domain.seasons import PARIS
from sibylle.realtime import bus
from sibylle.worker.jobs import pay_runner_week, reveal_pixel_puzzles

pytestmark = pytest.mark.contract

THIS_WEEK = "2026-11-02"
PIXELS = bytes([0] * 112 + [13] * 32 + [0] * 112)
DRAWING = {"size": 16, "palette": "base-v1", "pixels": base64.b64encode(PIXELS).decode()}


def url(org_id: object, path: str = "") -> str:
    return f"/api/orgs/{org_id}/games/schedule{path}"


async def plan(person: Person, org_id: object, week: str, games: list[str]) -> httpx.Response:
    return await person.client.put(url(org_id, f"/weeks/{week}"), json={"games": games})


async def ordinary(person: Person, org_id: object, games: list[str]) -> httpx.Response:
    return await person.client.put(url(org_id, "/default"), json={"games": games})


async def schedule(person: Person, org_id: object) -> dict[str, Any]:
    response = await person.client.get(url(org_id))
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def games(person: Person, org_id: object) -> dict[str, Any]:
    response = await person.client.get(f"/api/orgs/{org_id}/games")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


def week(start: str, games: list[str], planned: bool = False) -> dict[str, Any]:
    return {"week_start": start, "games": games, "planned": planned}


async def start(person: Person, org_id: object) -> httpx.Response:
    return await person.client.post(f"/api/orgs/{org_id}/games/runner/runs")


async def finish(person: Person, org_id: object, run_id: str, score: int) -> httpx.Response:
    return await person.client.post(
        f"/api/orgs/{org_id}/games/runner/runs/{run_id}/finish",
        json={"score": score, "duration_ms": 20_000},
    )


async def play(person: Person, org_id: object, score: int, fake_clock: clock.FakeClock) -> None:
    started = await start(person, org_id)
    assert started.status_code == 201, started.text
    fake_clock.advance(timedelta(seconds=30))
    finished = await finish(person, org_id, started.json()["run_id"], score)
    assert finished.status_code == 200, finished.text


async def post(person: Person, org_id: object, word: str) -> httpx.Response:
    return await person.client.post(
        f"/api/orgs/{org_id}/games/pixel/puzzles", json={"drawing": DRAWING, "word": word}
    )


async def guess(person: Person, org_id: object, word: str) -> httpx.Response:
    return await person.client.post(f"/api/orgs/{org_id}/games/pixel/guesses", json={"word": word})


async def pixel(person: Person, org_id: object) -> dict[str, Any] | None:
    response = await person.client.get(f"/api/orgs/{org_id}/games/pixel")
    assert response.status_code == 200, response.text
    data: dict[str, Any] | None = response.json()
    return data


async def balance(person: Person) -> int:
    async with transaction() as session:
        member = await session.get(Membership, person.member.id)
        assert member is not None
        return member.balance


def refused(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


async def test_only_the_editor_sees_and_plans_the_games(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    stranger = await person(await make_org("Autre Rédac"), "editor", "Inconnue")

    assert await schedule(ines, org.id) == {
        "default": ["runner", "pixel"],
        "weeks": [
            week("2026-11-02", ["runner", "pixel"]),
            week("2026-11-09", ["runner", "pixel"]),
            week("2026-11-16", ["runner", "pixel"]),
            week("2026-11-23", ["runner", "pixel"]),
        ],
    }
    for someone in (hugo, cami):
        refused(await someone.client.get(url(org.id)), 403, "forbidden")
        refused(await ordinary(someone, org.id, []), 403, "forbidden")
        refused(await plan(someone, org.id, THIS_WEEK, []), 403, "forbidden")
        refused(await someone.client.delete(url(org.id, "/weeks/2026-11-09")), 403, "forbidden")
    refused(await stranger.client.get(url(org.id)), 404, "not_found")
    refused(await plan(stranger, org.id, THIS_WEEK, []), 404, "not_found")
    # Nobody changed anything.
    assert (await games(cami, org.id))["scheduled"] == ["runner", "pixel"]


async def test_an_ordinary_week_changes_from_the_next_week_on(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    await play(cami, org.id, 300, fake_clock)

    changed = await ordinary(ines, org.id, ["pixel", "pixel"])
    assert changed.status_code == 200, changed.text
    assert changed.json() == {
        "default": ["pixel"],
        "weeks": [
            week("2026-11-02", ["runner", "pixel"]),
            week("2026-11-09", ["pixel"]),
            week("2026-11-16", ["pixel"]),
            week("2026-11-23", ["pixel"]),
        ],
    }
    # This week keeps its games.
    assert (await games(cami, org.id))["scheduled"] == ["runner", "pixel"]
    refused(await ordinary(ines, org.id, ["chess"]), 422, "validation_error")

    # Monday: the race is gone, and the week before still pays.
    fake_clock.set(datetime(2026, 11, 9, 0, 30, tzinfo=PARIS))
    now = await games(cami, org.id)
    assert (now["scheduled"], now["runner"]) == (["pixel"], None)
    assert await pay_runner_week(org.id) == 1
    assert await balance(cami) == 110
    # Changed again on that Monday, it waits for the Monday after.
    again = await ordinary(ines, org.id, [])
    assert [w["games"] for w in again.json()["weeks"]] == [["pixel"], [], [], []]


async def test_the_editor_plans_each_of_the_four_weeks(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")

    assert (await plan(ines, org.id, "2026-11-09", ["runner"])).status_code == 200
    none = await plan(ines, org.id, "2026-11-16", [])
    assert none.status_code == 200, none.text
    assert none.json()["weeks"] == [
        week("2026-11-02", ["runner", "pixel"]),
        week("2026-11-09", ["runner"], planned=True),
        week("2026-11-16", [], planned=True),
        week("2026-11-23", ["runner", "pixel"]),
    ]
    # A planned week keeps its games whatever an ordinary week becomes.
    after = await ordinary(ines, org.id, ["pixel"])
    assert [w["games"] for w in after.json()["weeks"]] == [
        ["runner", "pixel"],
        ["runner"],
        [],
        ["pixel"],
    ]
    # Back to an ordinary week.
    back = await ines.client.delete(url(org.id, "/weeks/2026-11-16"))
    assert back.status_code == 200, back.text
    assert back.json()["weeks"][2] == week("2026-11-16", ["pixel"])

    # Only this week and the three after it, by their Monday; the current week stays planned.
    for start_day, code in (
        ("2026-10-26", "out_of_range"),
        ("2026-11-30", "out_of_range"),
        ("2026-11-03", "not_monday"),
    ):
        answer = await plan(ines, org.id, start_day, ["runner"])
        assert answer.status_code == 422, start_day
        assert answer.json()["error"]["fields"] == {"week_start": code}
        answer = await ines.client.delete(url(org.id, f"/weeks/{start_day}"))
        assert answer.json()["error"]["fields"] == {"week_start": code}
    refused(await ines.client.delete(url(org.id, f"/weeks/{THIS_WEEK}")), 409, "invalid_state")
    refused(await plan(ines, org.id, THIS_WEEK, ["chess"]), 422, "validation_error")

    # A week without a game: nothing to show, nothing to play.
    assert (await plan(ines, org.id, THIS_WEEK, [])).status_code == 200
    assert await games(cami, org.id) == {"scheduled": [], "runner": None, "pixel": None}
    refused(await start(cami, org.id), 409, "game_not_scheduled")
    refused(await guess(cami, org.id, "café"), 409, "game_not_scheduled")


async def test_a_race_taken_out_of_the_week_pays_nothing(
    make_org: MakeOrg,
    person: MakePerson,
    fake_clock: clock.FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await play(cami, org.id, 500, fake_clock)
    running = (await start(leo, org.id)).json()["run_id"]
    events = record_events(monkeypatch)

    removed = await plan(ines, org.id, THIS_WEEK, ["pixel"])
    assert removed.status_code == 200, removed.text
    assert ("games.schedule.changed", {"week_start": THIS_WEEK, "games": ["pixel"]}) in events
    now = await games(cami, org.id)
    assert (now["scheduled"], now["runner"]) == (["pixel"], None)
    refused(await start(cami, org.id), 409, "game_not_scheduled")
    fake_clock.advance(timedelta(seconds=30))
    refused(await finish(leo, org.id, running, 200), 409, "game_not_scheduled")
    # Planning the same games again says nothing more.
    events.clear()
    assert (await plan(ines, org.id, THIS_WEEK, ["pixel"])).status_code == 200
    assert events == []

    # Monday pays nothing for the cancelled week; the week after is ordinary again.
    fake_clock.set(datetime(2026, 11, 9, 0, 30, tzinfo=PARIS))
    assert await pay_runner_week(org.id) == 0
    assert (await balance(cami), await balance(leo)) == (100, 100)
    back = await games(cami, org.id)
    assert (back["scheduled"], back["runner"]["attempts_left"]) == (["runner", "pixel"], 5)


async def test_a_race_put_back_in_the_week_counts_again(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    await play(cami, org.id, 500, fake_clock)
    assert (await plan(ines, org.id, THIS_WEEK, [])).status_code == 200
    assert (await plan(ines, org.id, THIS_WEEK, ["runner"])).status_code == 200

    now = await games(cami, org.id)
    assert (now["scheduled"], now["pixel"]) == (["runner"], None)
    assert (now["runner"]["attempts_left"], now["runner"]["my_best"]) == (4, 500)
    fake_clock.set(datetime(2026, 11, 9, 0, 30, tzinfo=PARIS))
    assert await pay_runner_week(org.id) == 1
    assert await balance(cami) == 110


async def test_pixel_taken_out_of_the_week_gives_the_word(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    assert (await post(hugo, org.id, "Café")).status_code == 201
    assert (await guess(cami, org.id, "café")).json()["rank"] == 1

    assert (await plan(ines, org.id, THIS_WEEK, ["runner"])).status_code == 200
    stopped = await pixel(leo, org.id)
    assert stopped is not None
    assert (stopped["state"], stopped["word"]) == ("finished", "Café")
    assert base64.b64decode(stopped["revealed"]) == PIXELS
    now = await games(leo, org.id)
    assert (now["scheduled"], now["pixel"]) == (["runner"], stopped)
    refused(await guess(leo, org.id, "café"), 409, "game_not_scheduled")
    # The laurels won stay.
    assert await balance(cami) == 110

    # A drawing posted meanwhile waits for Pixel mystère to come back.
    waiting = await post(hugo, org.id, "Boule")
    assert (waiting.status_code, waiting.json()["state"]) == (201, "queued")
    fake_clock.set(datetime(2026, 11, 3, 8, 0, tzinfo=PARIS))
    assert await reveal_pixel_puzzles(org.id) == 0
    # Back the next day: the next drawing starts at once.
    fake_clock.set(datetime(2026, 11, 3, 9, 0, tzinfo=PARIS))
    assert (await plan(ines, org.id, THIS_WEEK, ["runner", "pixel"])).status_code == 200
    following = await pixel(leo, org.id)
    assert following is not None
    assert (following["state"], following["letters"], following["word"]) == ("active", 5, None)


async def test_a_week_without_pixel_stops_the_drawing_on_monday(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    assert (await plan(ines, org.id, "2026-11-09", ["runner"])).status_code == 200
    fake_clock.set(datetime(2026, 11, 5, 10, 0, tzinfo=PARIS))
    assert (await post(hugo, org.id, "Café")).status_code == 201
    assert (await post(hugo, org.id, "Boule")).json()["state"] == "queued"

    fake_clock.set(datetime(2026, 11, 8, 23, 59, tzinfo=PARIS))
    await reveal_pixel_puzzles(org.id)
    sunday = await pixel(cami, org.id)
    assert sunday is not None
    assert (sunday["state"], sunday["revealed_count"]) == ("active", 148)

    # Monday 00:00: no more guesses, and the worker's next minute ends the drawing.
    fake_clock.set(datetime(2026, 11, 9, 0, 0, tzinfo=PARIS))
    refused(await guess(cami, org.id, "café"), 409, "game_not_scheduled")
    assert await pixel(cami, org.id) is None
    assert await reveal_pixel_puzzles(org.id) == 1
    ended = await pixel(cami, org.id)
    assert ended is not None
    assert (ended["state"], ended["word"]) == ("finished", "Café")

    # The waiting drawing skips the week without Pixel mystère, then starts with the next one.
    fake_clock.set(datetime(2026, 11, 10, 8, 0, tzinfo=PARIS))
    assert await reveal_pixel_puzzles(org.id) == 0
    fake_clock.set(datetime(2026, 11, 16, 0, 0, tzinfo=PARIS))
    assert await reveal_pixel_puzzles(org.id) == 1
    started = await pixel(cami, org.id)
    assert started is not None
    assert (started["state"], started["letters"]) == ("active", 5)


def record_events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """The events published from now on, by name and data, still sent as usual."""
    events: list[tuple[str, dict[str, Any]]] = []
    original = bus.publish

    async def publish(session: Any, event: str, data: dict[str, Any], **kwargs: Any) -> None:
        events.append((event, data))
        await original(session, event, data, **kwargs)

    monkeypatch.setattr(bus, "publish", publish)
    return events

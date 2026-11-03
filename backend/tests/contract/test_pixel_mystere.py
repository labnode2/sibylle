"""Pixel mystère over HTTP (US10): a drawing shows itself day by day, the first to find the
word win laurels, and the game ends when everyone found or when every pixel is shown."""

import base64
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import MakeOrg, MakePerson, Person

from sibylle import clock
from sibylle.db.models import Membership
from sibylle.db.session import transaction
from sibylle.domain.minigames import HIDDEN
from sibylle.domain.seasons import PARIS
from sibylle.worker.jobs import reveal_pixel_puzzles

pytestmark = pytest.mark.contract

# A 16 × 16 drawing: a band of colour 13 on a transparent background.
PIXELS = bytes([0] * 112 + [13] * 32 + [0] * 112)
DRAWING = {"size": 16, "palette": "base-v1", "pixels": base64.b64encode(PIXELS).decode()}


def pixel(org_id: object, path: str = "") -> str:
    return f"/api/orgs/{org_id}/games/pixel{path}"


async def post(person: Person, org_id: object, word: str = "Café") -> httpx.Response:
    return await person.client.post(
        pixel(org_id, "/puzzles"), json={"drawing": DRAWING, "word": word}
    )


async def status(person: Person, org_id: object) -> dict[str, Any]:
    response = await person.client.get(pixel(org_id))
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def guess(person: Person, org_id: object, word: str) -> httpx.Response:
    return await person.client.post(pixel(org_id, "/guesses"), json={"word": word})


def shown(state: dict[str, Any]) -> int:
    return sum(1 for value in base64.b64decode(state["revealed"]) if value != HIDDEN)


async def balance(person: Person) -> int:
    async with transaction() as session:
        member = await session.get(Membership, person.member.id)
        assert member is not None
        return member.balance


async def test_a_journalist_posts_a_drawing_and_it_starts(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    assert (await cami.client.get(pixel(org.id))).json() is None
    assert (await post(cami, org.id)).status_code == 403
    for word in ("x", "café2", "un mot bien trop long pour ce petit jeu"):
        refused = await post(hugo, org.id, word)
        assert refused.status_code == 422, word
        assert "word" in refused.json()["error"]["fields"]
    bad = await hugo.client.post(
        pixel(org.id, "/puzzles"), json={"drawing": {**DRAWING, "size": 8}, "word": "Café"}
    )
    assert bad.status_code == 422

    assert (await post(hugo, org.id)).status_code == 201
    state = await status(cami, org.id)
    assert (state["state"], state["size"], state["letters"]) == ("active", 16, 4)
    assert (state["guesses_left_today"], state["found_by_me"], state["mine"]) == (3, False, False)
    assert state["word"] is None and state["finds"] == []
    assert shown(state) == 37 == state["revealed_count"]
    assert (await cami.client.get(f"/api/orgs/{org.id}/games")).json()["pixel"] == state

    # Its author sees the whole drawing and the word, and does not play.
    mine = await status(hugo, org.id)
    assert (mine["mine"], mine["word"], mine["guesses_left_today"]) == (True, "Café", 0)
    assert base64.b64decode(mine["revealed"]) == PIXELS
    refused = await guess(hugo, org.id, "café")
    assert refused.status_code == 403


async def test_three_guesses_a_day_and_the_first_finders_win(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")
    await post(hugo, org.id)

    wrong = await guess(cami, org.id, "thé")
    assert wrong.json() == {
        "correct": False,
        "rank": None,
        "laurels": None,
        "guesses_left_today": 2,
    }
    right = await guess(cami, org.id, "cafe")
    assert right.json() == {"correct": True, "rank": 1, "laurels": 10, "guesses_left_today": 1}
    again = await guess(cami, org.id, "cafe")
    assert again.status_code == 409
    second = await guess(leo, org.id, "  CAFÉ ")
    assert (second.json()["rank"], second.json()["laurels"]) == (2, 7)
    assert (await balance(cami), await balance(leo)) == (110, 107)

    found = await status(cami, org.id)
    assert (found["found_by_me"], found["word"]) == (True, "Café")
    assert base64.b64decode(found["revealed"]) == PIXELS
    assert [(f["member"]["pseudo"], f["rank"]) for f in found["finds"]] == [("Cami", 1), ("Léo", 2)]
    still = await status(manon, org.id)
    assert still["word"] is None and shown(still) == 37

    for word in ("thé", "lait", "sucre"):
        assert (await guess(manon, org.id, word)).json()["correct"] is False
    fourth = await guess(manon, org.id, "café")
    assert fourth.status_code == 409
    assert fourth.json()["error"]["code"] == "attempts_exhausted"
    # Tomorrow, three new guesses.
    fake_clock.set(datetime(2026, 11, 3, 8, 0, tzinfo=PARIS))
    third = await guess(manon, org.id, "café")
    assert (third.json()["rank"], third.json()["guesses_left_today"]) == (3, 2)


async def test_the_game_ends_when_everyone_else_found(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await post(hugo, org.id)
    await guess(cami, org.id, "café")
    assert (await status(cami, org.id))["state"] == "active"
    await guess(leo, org.id, "café")
    ended = await status(hugo, org.id)
    assert (ended["state"], ended["word"]) == ("finished", "Café")
    assert (await guess(leo, org.id, "café")).status_code == 409

    # The next drawing waits for tomorrow 08:00.
    assert (await post(hugo, org.id, "Boule")).status_code == 201
    assert (await status(cami, org.id))["state"] == "finished"
    fake_clock.set(datetime(2026, 11, 3, 7, 59, tzinfo=PARIS))
    assert await reveal_pixel_puzzles() == 0
    fake_clock.set(datetime(2026, 11, 3, 8, 0, tzinfo=PARIS))
    assert await reveal_pixel_puzzles() == 1
    following = await status(cami, org.id)
    assert (following["state"], following["letters"], following["word"]) == ("active", 5, None)


async def test_the_game_ends_when_every_pixel_shows(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await post(hugo, org.id)
    await guess(cami, org.id, "café")

    counts = []
    for day in range(3, 9):
        fake_clock.set(datetime(2026, 11, day, 8, 0, tzinfo=PARIS))
        await reveal_pixel_puzzles()
        await reveal_pixel_puzzles()  # twice changes nothing
        counts.append((await status(leo, org.id))["revealed_count"])
    assert counts == [74, 111, 148, 185, 222, 256]
    ended = await status(leo, org.id)
    assert (ended["state"], ended["word"], ended["found_by_me"]) == ("finished", "Café", False)
    assert base64.b64decode(ended["revealed"]) == PIXELS
    assert (await guess(leo, org.id, "café")).status_code == 409


async def test_the_queue_is_for_journalists(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    await post(hugo, org.id, "Café")
    await post(hugo, org.id, "Boule")
    await post(ines, org.id, "Laurier")

    assert (await cami.client.get(pixel(org.id, "/puzzles"))).status_code == 403
    queue = (await hugo.client.get(pixel(org.id, "/puzzles"))).json()
    assert [(p["state"], p["mine"], p["word"]) for p in queue] == [
        ("active", True, "Café"),
        ("queued", True, "Boule"),
        ("queued", False, None),
    ]
    assert queue[2]["drawing"] is None and queue[1]["drawing"] == DRAWING
    assert all("author" not in p for p in queue)


async def test_a_newsroom_sees_only_its_own_game(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    other = await make_org("Autre Rédac")
    hugo = await person(org, "journalist", "Hugo")
    stranger = await person(other, "reader", "Inconnu")
    await post(hugo, org.id)
    assert (await stranger.client.get(pixel(org.id))).status_code == 404
    assert (await stranger.client.get(pixel(other.id))).json() is None


async def test_reveals_are_spaced_by_mornings(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await post(hugo, org.id)
    fake_clock.advance(timedelta(hours=12))  # Monday 22:00
    assert await reveal_pixel_puzzles() == 0
    assert (await status(cami, org.id))["revealed_count"] == 37

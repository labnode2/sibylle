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


async def post(
    person: Person, org_id: object, word: str = "Café", others: list[str] | None = None
) -> httpx.Response:
    return await person.client.post(
        pixel(org_id, "/puzzles"),
        json={"drawing": DRAWING, "word": word, "other_words": others or []},
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
    assert shown(state) == state["revealed_count"] <= 1
    assert state["gain_now"] == 50
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
    assert right.json() == {"correct": True, "rank": 1, "laurels": 50, "guesses_left_today": 1}
    again = await guess(cami, org.id, "cafe")
    assert again.status_code == 409
    second = await guess(leo, org.id, "  CAFÉ ")
    assert (second.json()["rank"], second.json()["laurels"]) == (2, 50)
    assert (await balance(cami), await balance(leo)) == (150, 150)

    found = await status(cami, org.id)
    assert (found["found_by_me"], found["word"]) == (True, "Café")
    assert base64.b64decode(found["revealed"]) == PIXELS
    assert [(f["member"]["pseudo"], f["rank"]) for f in found["finds"]] == [("Cami", 1), ("Léo", 2)]
    still = await status(manon, org.id)
    assert still["word"] is None and shown(still) <= 1

    for word in ("thé", "lait", "sucre"):
        assert (await guess(manon, org.id, word)).json()["correct"] is False
    fourth = await guess(manon, org.id, "café")
    assert fourth.status_code == 409
    assert fourth.json()["error"]["code"] == "attempts_exhausted"
    # Tomorrow, three new guesses.
    fake_clock.set(datetime(2026, 11, 3, 8, 0, tzinfo=PARIS))
    third = await guess(manon, org.id, "café")
    assert (third.json()["rank"], third.json()["guesses_left_today"]) == (3, 2)
    # A day later the gain is lower, the same for whoever finds then: 50 - 47 × 22/168 = 43.8.
    assert third.json()["laurels"] == 44
    assert await balance(manon) == 144


async def test_la_une_never_gives_the_drawing_nor_the_word_before_the_end(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await person(org, "reader", "Léo")
    await post(hugo, org.id)
    assert (await guess(cami, org.id, "café")).json()["correct"] is True

    for who, flag in ((hugo, "mine"), (cami, "found_by_me")):
        response = await who.client.get(f"/api/orgs/{org.id}/games")
        home = response.json()["pixel"]
        assert home[flag] is True and home["state"] == "active"
        assert home["word"] is None
        assert "Café" not in response.text
        assert shown(home) == home["revealed_count"] <= 1
        assert base64.b64decode(home["revealed"]) != PIXELS
        # The game's own page still shows them the whole drawing and the word.
        page = await status(who, org.id)
        assert page["word"] == "Café" and base64.b64decode(page["revealed"]) == PIXELS


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
    # The countdown runs to a week after the opening, when the last pixels show.
    opening = clock.now()
    ends_at = (await status(leo, org.id))["ends_at"]
    assert abs(datetime.fromisoformat(ends_at) - (opening + timedelta(days=7))) < timedelta(
        seconds=5
    )

    counts = []
    for day in (1, 2, 4, 6):
        fake_clock.set(opening + timedelta(days=day))
        await reveal_pixel_puzzles()
        await reveal_pixel_puzzles()  # twice changes nothing
        counts.append((await status(leo, org.id))["revealed_count"])
    assert counts == [37, 74, 147, 220]
    fake_clock.set(opening + timedelta(days=7, minutes=1))
    await reveal_pixel_puzzles()
    ended = await status(leo, org.id)
    assert (ended["state"], ended["word"], ended["found_by_me"]) == ("finished", "Café", False)
    assert ended["ends_at"] is None
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


async def test_pixels_and_gain_follow_the_time_gone(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    await post(hugo, org.id)
    opening = clock.now()
    fake_clock.set(opening + timedelta(hours=84))  # half of the week
    state = await status(cami, org.id)
    assert 128 <= state["revealed_count"] <= 130 and shown(state) == state["revealed_count"]
    assert state["gain_now"] == 26
    # What the home card shows is the same, and a finder is told the gain paid.
    assert (await cami.client.get(f"/api/orgs/{org.id}/games")).json()["pixel"] == state
    right = await guess(cami, org.id, "café")
    assert right.json()["laurels"] == 26 == state["gain_now"]
    assert await balance(cami) == 126
    # The rank is kept but the gain does not depend on it.
    again = await guess(leo, org.id, "café")
    assert (again.json()["rank"], again.json()["laurels"]) == (2, 26)
    assert (await status(hugo, org.id))["gain_now"] is None


async def test_the_author_is_paid_25_at_the_start_then_5_a_find(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    before = await balance(hugo)
    await post(hugo, org.id)
    assert await balance(hugo) == before + 25
    assert (await status(hugo, org.id))["author_earned"] == 25
    assert (await status(cami, org.id))["author_earned"] is None

    # A wrong word and the author's own answer pay nothing.
    await guess(cami, org.id, "thé")
    assert (await guess(hugo, org.id, "café")).status_code == 403
    assert await balance(hugo) == before + 25

    assert (await guess(cami, org.id, "café")).json()["correct"] is True
    assert await balance(hugo) == before + 30
    # A replayed answer is refused and pays nothing more.
    assert (await guess(cami, org.id, "café")).status_code == 409
    assert await balance(hugo) == before + 30
    await guess(leo, org.id, "café")
    assert await balance(hugo) == before + 35
    assert (await status(hugo, org.id))["author_earned"] == 35

    # Ending the game and the morning job pay no second bonus.
    fake_clock.set(clock.now() + timedelta(days=8))
    await reveal_pixel_puzzles()
    assert await balance(hugo) == before + 35


async def test_a_drawing_with_several_words_accepts_each_of_them(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")

    # Refused: a bad other word, a duplicate once normalized, more than five words in all.
    for others in (
        ["x"],
        ["CAFE"],
        ["thé", "the"],
        ["a1"],
        ["un", "deux", "trois", "quatre", "cinq"],
    ):
        refused = await post(hugo, org.id, "Café", others)
        assert refused.status_code == 422, others
        assert "other_words" in refused.json()["error"]["fields"]
    created = await post(hugo, org.id, "Café", ["Expresso", " petit  noir ", "Jus", "Thé"])
    assert created.status_code == 201
    assert created.json()["words"] == ["Café", "Expresso", "petit noir", "Jus", "Thé"]

    # The others never see the list before they find the word.
    state = await status(cami, org.id)
    assert state["word"] is None and state["words"] is None
    assert (await status(hugo, org.id))["words"] == created.json()["words"]

    assert (await guess(cami, org.id, "tasse")).json()["correct"] is False
    first = await guess(cami, org.id, "expresso")
    assert (first.json()["correct"], first.json()["rank"]) == (True, 1)
    second = await guess(leo, org.id, "Petit Noir")
    assert (second.json()["correct"], second.json()["rank"]) == (True, 2)
    assert (await guess(cami, org.id, "café")).status_code == 409  # one find per member

    found = await status(cami, org.id)
    assert found["words"] == created.json()["words"] and found["word"] == "Café"
    assert (await status(manon, org.id))["words"] is None


async def museum(person: Person, org_id: object) -> list[dict[str, Any]]:
    response = await person.client.get(pixel(org_id, "/museum"))
    assert response.status_code == 200, response.text
    data: list[dict[str, Any]] = response.json()
    return data


def near(text: str, instant: datetime) -> bool:
    return abs(datetime.fromisoformat(text) - instant) < timedelta(seconds=5)


async def test_the_museum_shows_the_finished_drawings_latest_first(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    assert await museum(cami, org.id) == []

    # Neither the drawing in play nor the one waiting: their words are still to find.
    await post(hugo, org.id, "Café", ["Expresso"])
    await post(ines, org.id, "Boule")
    await guess(cami, org.id, "café")
    await guess(leo, org.id, "café")
    response = await cami.client.get(pixel(org.id, "/museum"))
    assert response.json() == []
    assert "Café" not in response.text and "Boule" not in response.text

    # « Café » ends with its last pixels, found by two; « Boule » starts the next morning.
    opening = clock.now()
    fake_clock.set(opening + timedelta(days=7, minutes=1))
    await reveal_pixel_puzzles()
    cafe_end = clock.now()
    assert [item["word"] for item in await museum(cami, org.id)] == ["Café"]
    fake_clock.set(datetime(2026, 11, 10, 8, 0, tzinfo=PARIS))
    assert await reveal_pixel_puzzles() == 1
    assert [item["word"] for item in await museum(cami, org.id)] == ["Café"]

    # Everyone but Inès finds « Boule », which ends at once; the next drawing waits.
    for who in (hugo, cami, leo):
        assert (await guess(who, org.id, "boule")).json()["correct"] is True
    boule_end = clock.now()
    assert (await post(hugo, org.id, "Laurier")).json()["state"] == "queued"
    fake_clock.set(datetime(2026, 11, 11, 8, 0, tzinfo=PARIS))
    assert await reveal_pixel_puzzles() == 1

    response = await cami.client.get(pixel(org.id, "/museum"))
    assert response.status_code == 200
    assert "Laurier" not in response.text
    boule, cafe = response.json()
    assert (boule["word"], boule["author"]["pseudo"], boule["found_count"]) == ("Boule", "Inès", 3)
    assert (cafe["word"], cafe["author"]["pseudo"], cafe["found_count"]) == ("Café", "Hugo", 2)
    for item in (boule, cafe):
        assert (item["size"], item["drawing"]) == (16, DRAWING)
        assert set(item["author"]) >= {"id", "pseudo", "avatar", "role"}
        assert not {"first_name", "last_name", "email"} & set(item["author"])
    assert near(boule["finished_at"], boule_end) and near(cafe["finished_at"], cafe_end)
    assert cafe["puzzle_id"] != boule["puzzle_id"]


async def test_the_museum_is_its_newsroom_s_own_and_open_to_all_its_members(
    make_org: MakeOrg, person: MakePerson, client: httpx.AsyncClient
) -> None:
    org = await make_org()
    other = await make_org("Autre Rédac")
    hugo = await person(org, "journalist", "Hugo")
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    zoe = await person(other, "journalist", "Zoé")
    stranger = await person(other, "reader", "Inconnu")
    await post(hugo, org.id, "Café")
    for who in (ines, cami):
        await guess(who, org.id, "café")
    await post(zoe, other.id, "Boule")
    await guess(stranger, other.id, "boule")

    assert [item["word"] for item in await museum(cami, org.id)] == ["Café"]
    assert [item["word"] for item in await museum(stranger, other.id)] == ["Boule"]
    # Not a member: the newsroom stays out of sight, as everywhere else.
    refused = await stranger.client.get(pixel(org.id, "/museum"))
    assert refused.status_code == 404
    assert "Café" not in refused.text
    assert (await client.get(pixel(org.id, "/museum"))).status_code == 401

    # A week without Pixel mystère, the museum stays open, to the readers too.
    planned = await ines.client.put(
        f"/api/orgs/{org.id}/games/schedule/weeks/2026-11-02", json={"games": ["runner"]}
    )
    assert planned.status_code == 200, planned.text
    assert (await ines.client.get(f"/api/orgs/{org.id}/games")).json()["scheduled"] == ["runner"]
    assert [item["word"] for item in await museum(cami, org.id)] == ["Café"]

"""Wordle over HTTP: one game a day per member, the word kept secret until the game is over,
the gain paid once."""

from datetime import date, datetime
from typing import Any

import httpx
import pytest
from tests.conftest import MakeOrg, MakePerson, Person

from sibylle import clock
from sibylle.db.models import Membership
from sibylle.db.session import transaction
from sibylle.domain.minigames import wordle_answer
from sibylle.domain.seasons import PARIS
from sibylle.domain.wordle_words import ANSWERS

pytestmark = pytest.mark.contract

DAY = date(2026, 11, 16)


def url(org_id: object, path: str = "") -> str:
    return f"/api/orgs/{org_id}/games/wordle{path}"


async def guess(person: Person, org_id: object, word: str) -> httpx.Response:
    return await person.client.post(url(org_id, "/guesses"), json={"word": word})


async def status(person: Person, org_id: object) -> dict[str, Any]:
    response = await person.client.get(url(org_id))
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def balance(person: Person) -> int:
    async with transaction() as session:
        member = await session.get(Membership, person.member.id)
        assert member is not None
        return member.balance


def wrong_words(count: int) -> list[str]:
    answer = wordle_answer(DAY)
    return [w for w in ANSWERS if w != answer][:count]


async def test_a_new_day_gives_six_tries_and_hides_the_solution(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 9, 0, tzinfo=PARIS))
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    state = await status(cami, org.id)
    assert state["day"] == "2026-11-16"
    assert (state["state"], state["tries"], state["tries_left"]) == ("playing", [], 6)
    assert state["solution"] is None and state["laurels"] is None
    assert (await cami.client.get(f"/api/orgs/{org.id}/games")).json()["wordle"] == state

    r = await guess(cami, org.id, wrong_words(1)[0])
    assert r.status_code == 200, r.text
    first = r.json()
    assert first["tries_left"] == 5 and first["solution"] is None
    assert wordle_answer(DAY) not in str(first)
    # The state is kept by the server: a reload shows the same.
    assert await status(cami, org.id) == first


async def test_a_word_found_pays_once_and_gives_the_solution(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 9, 0, tzinfo=PARIS))
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    before = await balance(cami)
    await guess(cami, org.id, wrong_words(1)[0])
    won = (await guess(cami, org.id, wordle_answer(DAY).upper())).json()
    assert (won["state"], won["laurels"], won["solution"]) == ("won", 5, wordle_answer(DAY))
    assert won["tries"][-1]["marks"] == ["correct"] * 5
    assert await balance(cami) == before + 5

    # One game a day: nothing more to try, nothing more paid.
    again = await guess(cami, org.id, wordle_answer(DAY))
    assert again.status_code == 409
    assert await balance(cami) == before + 5
    # The others have their own game, and the same word.
    assert (await status(leo, org.id))["state"] == "playing"
    assert (await guess(leo, org.id, wordle_answer(DAY))).json()["laurels"] == 6

    # The next day, a new game.
    fake_clock.set(datetime(2026, 11, 17, 0, 5, tzinfo=PARIS))
    fresh = await status(cami, org.id)
    assert (fresh["state"], fresh["tries_left"], fresh["solution"]) == ("playing", 6, None)


async def test_the_sixth_miss_ends_the_game_and_shows_the_solution(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 9, 0, tzinfo=PARIS))
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    before = await balance(cami)
    words = wrong_words(6)
    for word in words[:5]:
        assert (await guess(cami, org.id, word)).json()["state"] == "playing"
    lost = (await guess(cami, org.id, words[5])).json()
    assert (lost["state"], lost["tries_left"], lost["laurels"]) == ("lost", 0, None)
    assert lost["solution"] == wordle_answer(DAY)
    assert (await guess(cami, org.id, wordle_answer(DAY))).status_code == 409
    assert await balance(cami) == before


async def test_an_unknown_word_is_refused_and_costs_no_try(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 9, 0, tzinfo=PARIS))
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    for word in ("zzzzz", "abc", "trop long"):
        refused = await guess(cami, org.id, word)
        assert refused.status_code == 422, word
        assert "word" in refused.json()["error"]["fields"]
    assert (await status(cami, org.id))["tries_left"] == 6


async def test_accents_are_normalized(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    # A day whose word has no accent to type: « école » tried is the accepted « ecole ».
    fake_clock.set(datetime(2026, 11, 16, 9, 0, tzinfo=PARIS))
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    state = (await guess(cami, org.id, "École")).json()
    assert state["tries"][0]["word"] == "ecole"

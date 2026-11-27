"""Wordle over HTTP and in the worker: one game a day per member on the newsroom's own word, kept
secret until the game is over, the gain paid once, a last chance for the rarer words; the word
file synced each night, each newsroom's word drawn at midnight and kept, its level set by whoever
plans the games."""

import hashlib
import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from tests.conftest import MakeOrg, MakePerson, Person
from tests.wordle_sample import FakeWordleFile, encoded, sample, tier_words, word, words_of

from sibylle import clock
from sibylle.db.models import (
    LedgerEntry,
    Membership,
    Organisation,
    WordleDay,
    WordleGame,
    WordleList,
)
from sibylle.db.session import transaction
from sibylle.domain.minigames import wordle_answer, wordle_marks
from sibylle.domain.seasons import PARIS
from sibylle.domain.wordle_words import ACCEPTED, ANSWERS
from sibylle.services import minigames, wordle_lists
from sibylle.worker.jobs import prepare_wordle_day

pytestmark = pytest.mark.contract

DAY = date(2026, 11, 16)
MORNING = datetime(2026, 11, 16, 9, 0, tzinfo=PARIS)


def url(org_id: object, path: str = "") -> str:
    return f"/api/orgs/{org_id}/games/wordle{path}"


async def guess(person: Person, org_id: object, word: str) -> httpx.Response:
    return await person.client.post(url(org_id, "/guesses"), json={"word": word})


async def status(person: Person, org_id: object) -> dict[str, Any]:
    response = await person.client.get(url(org_id))
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def set_level(person: Person, org_id: object, level: object) -> httpx.Response:
    return await person.client.put(url(org_id, "/level"), json={"level": level})


def refused(response: httpx.Response, status_code: int, code: str) -> None:
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code


async def balance(person: Person) -> int:
    async with transaction() as session:
        member = await session.get(Membership, person.member.id)
        assert member is not None
        return member.balance


async def word_of(org_id: object, day: date | None = None) -> WordleDay | None:
    """The newsroom's word of `day` (today by default), if it was drawn."""
    day = day or clock.now().astimezone(PARIS).date()
    async with transaction() as session:
        return await session.get(WordleDay, (org_id, day))


async def the_word(person: Person, org_id: object) -> str:
    """The newsroom's word of today, which the member's first look draws if need be."""
    await status(person, org_id)
    today = await word_of(org_id)
    assert today is not None
    return today.word


def wrong_words(count: int, answer: str) -> list[str]:
    return [w for w in ANSWERS if w != answer][:count]


async def versions() -> list[WordleList]:
    async with transaction() as session:
        return list((await session.scalars(select(WordleList).order_by(WordleList.id))).all())


async def synced(wordle_file: FakeWordleFile, data: dict[str, Any]) -> None:
    """Today's sync, on that file: a new version."""
    wordle_file.serve(data)
    assert await wordle_lists.sync() == "stored"


def reversed_file() -> dict[str, Any]:
    """Another version: the same words, the tiers the other way round."""
    data = sample()
    data["answers"].reverse()
    return data


def without(data: dict[str, Any], gone: str) -> dict[str, Any]:
    """The file without a word, neither an answer nor a guess; another guess takes its place."""
    for tier in data["answers"]:
        tier["words"] = [entry for entry in tier["words"] if entry["word"] != gone]
        tier["count"] = len(tier["words"])
    data["guesses"] = sorted({*data["guesses"], "yyyyy"} - {gone})
    return data


def warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.name == "sibylle.services.wordle_lists" and r.levelno >= logging.WARNING
    ]


def draw_last(words: Sequence[str]) -> str:
    return words[-1]


# The game


async def test_a_new_day_gives_six_tries_and_hides_the_solution(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    state = await status(cami, org.id)
    assert state["day"] == "2026-11-16"
    assert (state["state"], state["tries"], state["tries_left"]) == ("playing", [], 6)
    assert state["solution"] is None and state["laurels"] is None and state["hint"] is None
    assert (await cami.client.get(f"/api/orgs/{org.id}/games")).json()["wordle"] == state

    answer = await the_word(cami, org.id)
    r = await guess(cami, org.id, wrong_words(1, answer)[0])
    assert r.status_code == 200, r.text
    first = r.json()
    assert first["tries_left"] == 5 and first["solution"] is None
    assert answer not in str(first)
    # The state is kept by the server: a reload shows the same.
    assert await status(cami, org.id) == first


async def test_a_word_found_pays_once_and_gives_the_solution(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    before = await balance(cami)
    answer = await the_word(cami, org.id)
    await guess(cami, org.id, wrong_words(1, answer)[0])
    won = (await guess(cami, org.id, answer.upper())).json()
    assert (won["state"], won["laurels"], won["solution"]) == ("won", 5, answer)
    assert won["tries"][-1]["marks"] == ["correct"] * 5
    assert await balance(cami) == before + 5

    # One game a day: nothing more to try, nothing more paid.
    again = await guess(cami, org.id, answer)
    assert again.status_code == 409
    assert await balance(cami) == before + 5
    # The others have their own game, and the newsroom's word.
    assert (await status(leo, org.id))["state"] == "playing"
    assert (await guess(leo, org.id, answer)).json()["laurels"] == 6

    # The next day, a new game.
    fake_clock.set(datetime(2026, 11, 17, 0, 5, tzinfo=PARIS))
    fresh = await status(cami, org.id)
    assert (fresh["state"], fresh["tries_left"], fresh["solution"]) == ("playing", 6, None)


async def test_the_sixth_miss_ends_the_game_and_shows_the_solution(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    before = await balance(cami)
    answer = await the_word(cami, org.id)
    words = wrong_words(6, answer)
    for each in words[:5]:
        assert (await guess(cami, org.id, each)).json()["state"] == "playing"
    lost = (await guess(cami, org.id, words[5])).json()
    assert (lost["state"], lost["tries_left"], lost["laurels"]) == ("lost", 0, None)
    assert lost["solution"] == answer
    assert (await guess(cami, org.id, answer)).status_code == 409
    assert await balance(cami) == before


async def test_an_unknown_word_is_refused_and_costs_no_try(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    for each in ("zzzzz", "abc", "trop long"):
        answer = await guess(cami, org.id, each)
        assert answer.status_code == 422, each
        assert "word" in answer.json()["error"]["fields"]
    assert (await status(cami, org.id))["tries_left"] == 6


async def test_accents_are_normalized(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    # « école » tried is the accepted « ecole ».
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    state = (await guess(cami, org.id, "École")).json()
    assert state["tries"][0]["word"] == "ecole"


# The last chance


async def drawn(org: Organisation, answer: str, level: int | None) -> None:
    """The newsroom's word of today, as the draw kept it, with its level."""
    async with transaction() as session:
        session.add(WordleDay(org_id=org.id, day=DAY, word=answer, level=level))


async def ledger_of(person: Person) -> list[tuple[str, str | None]]:
    """The member's lines in the ledger, in order: their kind and reason."""
    async with transaction() as session:
        rows = await session.execute(
            select(LedgerEntry.kind, LedgerEntry.reason)
            .where(LedgerEntry.membership_id == person.member.id)
            .order_by(LedgerEntry.id)
        )
        return [(kind, reason) for kind, reason in rows]


@pytest.mark.parametrize("level", [4, 5, 6])
async def test_a_word_of_level_4_to_6_gives_a_last_chance_after_the_sixth_miss(
    level: int, make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    await drawn(org, "matin", level)
    misses = wrong_words(7, "matin")
    for count, each in enumerate(misses[:5], start=1):
        state = (await guess(cami, org.id, each)).json()
        assert (state["state"], state["tries_left"], state["hint"]) == ("playing", 6 - count, None)

    # The sixth missed: the game goes on, with the word's letters in alphabetical order.
    last = (await guess(cami, org.id, misses[5])).json()
    assert (last["state"], last["tries_left"], last["hint"]) == ("playing", 1, "A I M N T")
    assert (last["level"], last["laurels"], last["solution"]) == (level, None, None)
    assert await status(cami, org.id) == last
    assert (await cami.client.get(f"/api/orgs/{org.id}/games")).json()["wordle"] == last

    # The seventh try is one like the others: a word unknown is refused and costs nothing, a
    # word known shows its colours. Missed, it ends the game.
    refused(await guess(cami, org.id, "zzzzz"), 422, "validation_error")
    assert await status(cami, org.id) == last
    lost = (await guess(cami, org.id, misses[6])).json()
    assert (lost["state"], lost["tries_left"], lost["hint"]) == ("lost", 0, None)
    assert (lost["laurels"], lost["solution"]) == (None, "matin")
    assert len(lost["tries"]) == 7
    assert lost["tries"][-1] == {"word": misses[6], "marks": wordle_marks(misses[6], "matin")}
    # Never an eighth try.
    refused(await guess(cami, org.id, "matin"), 409, "wordle_over")
    assert await status(cami, org.id) == lost


@pytest.mark.parametrize("level", [1, 2, 3, None])
async def test_a_word_of_level_1_to_3_or_without_a_level_ends_at_the_sixth_miss(
    level: int | None, make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    await drawn(org, "matin", level)
    misses = wrong_words(6, "matin")
    for each in misses[:5]:
        assert (await guess(cami, org.id, each)).json()["hint"] is None
    lost = (await guess(cami, org.id, misses[5])).json()
    assert (lost["state"], lost["tries_left"], lost["hint"]) == ("lost", 0, None)
    assert (lost["level"], lost["solution"]) == (level, "matin")
    refused(await guess(cami, org.id, "matin"), 409, "wordle_over")


async def test_the_word_found_at_the_last_chance_is_a_win_without_laurels(
    make_org: MakeOrg,
    person: MakePerson,
    fake_clock: clock.FakeClock,
    wordle_file: FakeWordleFile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Drawn from the file at Normal: the last word of the fourth tier, so level 4.
    monkeypatch.setattr(minigames, "wordle_choice", draw_last)
    fake_clock.set(MORNING)
    await synced(wordle_file, sample())
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    answer = await the_word(cami, org.id)
    assert (answer, (await status(cami, org.id))["level"]) == (word(4, 19), 4)
    before = (await balance(cami), await ledger_of(cami))
    misses = tier_words(1)[:6]
    for each in misses[:5]:
        await guess(cami, org.id, each)
    last = (await guess(cami, org.id, misses[5])).json()
    assert (last["state"], last["hint"]) == ("playing", "A A A D T")

    won = (await guess(cami, org.id, answer.upper())).json()
    assert (won["state"], won["laurels"], won["solution"]) == ("won", 0, answer)
    assert (won["tries_left"], won["hint"]) == (0, None)
    assert len(won["tries"]) == 7 and won["tries"][-1]["marks"] == ["correct"] * 5
    # Nothing paid, not a line in the ledger; but a win, kept as one.
    assert (await balance(cami), await ledger_of(cami)) == before
    async with transaction() as session:
        game = await session.scalar(
            select(WordleGame).where(WordleGame.membership_id == cami.member.id)
        )
        assert game is not None
        assert (game.state, game.laurels, len(game.guesses)) == ("won", 0, 7)
    # Never an eighth try.
    refused(await guess(cami, org.id, answer), 409, "wordle_over")
    assert (await balance(cami), await ledger_of(cami)) == before


# The word file


async def test_the_sync_keeps_a_new_version_only_when_the_file_changed(
    db: None, wordle_file: FakeWordleFile, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 0, 1, tzinfo=PARIS))
    await synced(wordle_file, sample())
    [first] = await versions()
    assert first.content == sample()
    assert first.sha256 == hashlib.sha256(encoded(sample())).hexdigest()
    assert first.fetched_at == first.checked_at
    # Once a day: not again the same day.
    assert await wordle_lists.sync() == "not_due"
    assert wordle_file.downloads == 1

    # The next night, the same file: the version is only marked checked.
    fake_clock.set(datetime(2026, 11, 17, 0, 1, tzinfo=PARIS))
    assert await wordle_lists.sync() == "unchanged"
    [same] = await versions()
    assert (same.id, same.fetched_at) == (first.id, first.fetched_at)
    assert same.checked_at > first.checked_at
    async with transaction() as session:
        assert (await wordle_lists.current(session)).tiers[0] == tuple(tier_words(1))

    # The night after, a changed file: a new version, which the game takes.
    fake_clock.set(datetime(2026, 11, 18, 0, 1, tzinfo=PARIS))
    await synced(wordle_file, reversed_file())
    assert [version.content for version in await versions()] == [sample(), reversed_file()]
    async with transaction() as session:
        assert (await wordle_lists.current(session)).tiers[0] == tuple(tier_words(6))


async def test_a_failed_sync_keeps_the_last_good_version_and_tries_again(
    db: None,
    wordle_file: FakeWordleFile,
    fake_clock: clock.FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 0, 1, tzinfo=PARIS))
    await synced(wordle_file, sample())

    # The next night the network fails: a warning, and the version stays.
    fake_clock.set(datetime(2026, 11, 17, 0, 1, tzinfo=PARIS))
    wordle_file.serve(None)
    with caplog.at_level(logging.WARNING, logger="sibylle.services.wordle_lists"):
        assert await wordle_lists.sync() == "failed"
    assert [r.getMessage() for r in warnings(caplog)] == ["wordle lists not synced"]
    # Not again within a quarter of an hour.
    fake_clock.advance(timedelta(minutes=14))
    assert await wordle_lists.sync() == "not_due"
    assert wordle_file.downloads == 2

    # Then files that do not hold, each a quarter of an hour after the one before: broken JSON,
    # a word of six letters, an answer missing from the guesses.
    six = sample()
    six["answers"][0]["words"][0]["word"] = "abcdef"
    missing = sample()
    missing["guesses"].remove(word(2))
    for wrong, why in (
        (b'{"answers": [', "not JSON"),
        (encoded(six), "'abcdef' is not five letters"),
        (encoded(missing), f"'{word(2)}' is not among the guesses"),
    ):
        fake_clock.advance(timedelta(minutes=15, seconds=5))
        wordle_file.serve(wrong)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="sibylle.services.wordle_lists"):
            assert await wordle_lists.sync() == "failed"
        [warning] = warnings(caplog)
        assert why in warning.__dict__["error"]
    assert wordle_file.downloads == 5
    assert len(await versions()) == 1
    async with transaction() as session:
        assert (await wordle_lists.current(session)).tiers[0] == tuple(tier_words(1))

    # Until a good one comes, a quarter of an hour later again.
    fake_clock.advance(timedelta(minutes=10))
    wordle_file.serve(reversed_file())
    assert await wordle_lists.sync() == "not_due"
    fake_clock.advance(timedelta(minutes=5, seconds=5))
    await synced(wordle_file, reversed_file())
    assert len(await versions()) == 2


async def test_a_new_day_syncs_at_once_even_just_after_a_failure(
    db: None, wordle_file: FakeWordleFile, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 23, 55, tzinfo=PARIS))
    assert await wordle_lists.sync() == "failed"
    # Midnight: the day's sync comes before its words, whatever failed a few minutes ago.
    fake_clock.set(datetime(2026, 11, 17, 0, 0, 10, tzinfo=PARIS))
    wordle_file.serve(sample())
    assert await prepare_wordle_day() == 0
    assert wordle_file.downloads == 2
    assert len(await versions()) == 1


async def test_without_a_version_the_game_plays_on_the_old_lists(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(MORNING)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    # The worker could not fetch the file: the job still draws the newsroom's word.
    assert await prepare_wordle_day() == 1
    assert await versions() == []
    state = await status(cami, org.id)
    today = await word_of(org.id)
    assert today is not None and today.word in ANSWERS
    assert today.level is None and state["level"] is None
    # A word the old lists accept as a try only.
    other = sorted(ACCEPTED - set(ANSWERS))[0]
    assert (await guess(cami, org.id, other)).status_code == 200
    assert (await guess(cami, org.id, today.word)).json()["state"] == "won"


# Each newsroom's word


async def test_two_newsrooms_draw_their_own_words(
    make_org: MakeOrg,
    person: MakePerson,
    fake_clock: clock.FakeClock,
    wordle_file: FakeWordleFile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_clock.set(MORNING)
    await synced(wordle_file, sample())
    # Each draw takes the next word of those left: two draws, two words.
    draws = iter(range(100))
    monkeypatch.setattr(minigames, "wordle_choice", lambda words: words[next(draws)])
    gazette, monde = await make_org("Gazette"), await make_org("Le Monde")
    cami = await person(gazette, "reader", "Cami")
    leo = await person(monde, "reader", "Léo")
    one, two = await the_word(cami, gazette.id), await the_word(leo, monde.id)
    assert (one, two) == (word(1, 0), word(1, 1))
    # Each newsroom plays on its own: Léo's word is not Cami's.
    assert (await guess(cami, gazette.id, two)).json()["state"] == "playing"
    assert (await guess(leo, monde.id, two)).json()["state"] == "won"


async def test_a_newsroom_keeps_its_word_whatever_its_level_or_the_file(
    make_org: MakeOrg,
    person: MakePerson,
    fake_clock: clock.FakeClock,
    wordle_file: FakeWordleFile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(minigames, "wordle_choice", draw_last)
    fake_clock.set(datetime(2026, 11, 15, 23, 0, tzinfo=PARIS))
    await synced(wordle_file, sample())
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")

    # Midnight, and the network is down: the word comes from the version of the day before, at
    # the newsroom's level, Normal (the first four tiers).
    fake_clock.set(datetime(2026, 11, 16, 0, 0, 20, tzinfo=PARIS))
    wordle_file.serve(None)
    assert await prepare_wordle_day() == 1
    kept = word(4, 19)
    assert (await the_word(cami, org.id), (await status(cami, org.id))["level"]) == (kept, 4)

    # The same day: the editor makes it easy, and a quarter of an hour later the sync works, on
    # a file whose tiers are the other way round and which no longer has the word.
    assert (await set_level(ines, org.id, 1)).status_code == 200
    fake_clock.set(datetime(2026, 11, 16, 0, 16, tzinfo=PARIS))
    await synced(wordle_file, without(reversed_file(), kept))
    for _ in range(2):
        fake_clock.advance(timedelta(hours=4))
        assert await prepare_wordle_day() == 0
        assert (await the_word(cami, org.id), (await status(cami, org.id))["level"]) == (kept, 4)
    # Still the word to find, though no longer a guess.
    won = (await guess(cami, org.id, kept)).json()
    assert (won["state"], won["solution"], won["level"]) == ("won", kept, 4)

    # The next day, the new level and the new file: the first two tiers of the reversed file.
    fake_clock.set(datetime(2026, 11, 17, 0, 0, 20, tzinfo=PARIS))
    assert await prepare_wordle_day() == 1
    tomorrow = await word_of(org.id)
    assert tomorrow is not None
    assert (tomorrow.word, tomorrow.level) == (word(5, 19), 2)


async def test_a_new_level_counts_from_tomorrows_word(
    make_org: MakeOrg,
    person: MakePerson,
    fake_clock: clock.FakeClock,
    wordle_file: FakeWordleFile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(minigames, "wordle_choice", draw_last)
    fake_clock.set(MORNING)
    await synced(wordle_file, sample())
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    # Nobody looked at today's game yet: the change draws its word first, at Normal.
    assert await word_of(org.id) is None
    assert (await set_level(ines, org.id, 3)).json()["wordle_level"] == 3
    today = await word_of(org.id)
    assert today is not None and (today.word, today.level) == (word(4, 19), 4)
    assert (await status(cami, org.id))["level"] == 4
    # Tomorrow, Difficile: any tier.
    fake_clock.set(datetime(2026, 11, 17, 8, 0, tzinfo=PARIS))
    assert (await status(cami, org.id))["level"] == 6


async def test_no_word_comes_back_while_some_never_came(
    make_org: MakeOrg, fake_clock: clock.FakeClock, wordle_file: FakeWordleFile
) -> None:
    wordle_file.serve(sample())
    org = await make_org(wordle_level=1)
    drawn = []
    for day in range(40):
        fake_clock.set(datetime(2026, 11, 16, 0, 0, 30, tzinfo=PARIS) + timedelta(days=day))
        assert await prepare_wordle_day() == 1
        today = await word_of(org.id)
        assert today is not None
        drawn.append(today.word)
    # Facile allows 40 words: each came once.
    assert sorted(drawn) == sorted(words_of(1, 2))


async def test_the_job_draws_one_word_per_newsroom_then_nothing(
    make_org: MakeOrg, fake_clock: clock.FakeClock, wordle_file: FakeWordleFile
) -> None:
    fake_clock.set(datetime(2026, 11, 16, 0, 0, 30, tzinfo=PARIS))
    wordle_file.serve(sample())
    gazette, monde = await make_org("Gazette"), await make_org("Le Monde", wordle_level=3)
    closed = await make_org("Fermée", deleted_at=clock.now())
    assert await prepare_wordle_day() == 2
    # The day's sync came first: the words come from the file.
    assert wordle_file.downloads == 1
    for org in (gazette, monde):
        today = await word_of(org.id)
        assert today is not None and today.level is not None
    assert await word_of(closed.id) is None
    first = [await word_of(org.id) for org in (gazette, monde)]

    fake_clock.advance(timedelta(minutes=1))
    assert await prepare_wordle_day() == 0
    assert wordle_file.downloads == 1
    again = [await word_of(org.id) for org in (gazette, monde)]
    assert [(w.word, w.level) for w in again if w] == [(w.word, w.level) for w in first if w]


async def test_the_day_the_draw_came_in_games_begun_keep_the_shared_word(
    make_org: MakeOrg,
    person: MakePerson,
    fake_clock: clock.FakeClock,
    wordle_file: FakeWordleFile,
) -> None:
    fake_clock.set(MORNING)
    await synced(wordle_file, sample())
    begun, fresh = await make_org("Gazette"), await make_org("Le Monde")
    cami = await person(begun, "reader", "Cami")
    leo = await person(fresh, "reader", "Léo")
    shared = wordle_answer(DAY)
    tried = wrong_words(1, shared)[0]
    # Cami began the day's game before the update, on the word every newsroom shared.
    async with transaction() as session:
        session.add(
            WordleGame(
                org_id=begun.id,
                membership_id=cami.member.id,
                day=DAY,
                guesses=[tried],
                state="playing",
            )
        )

    assert await prepare_wordle_day() == 2
    state = await status(cami, begun.id)
    assert state["level"] is None
    assert state["tries"] == [{"word": tried, "marks": wordle_marks(tried, shared)}]
    kept = await word_of(begun.id)
    assert kept is not None and (kept.word, kept.level) == (shared, None)
    # The other newsroom draws from the file.
    assert (await status(leo, fresh.id))["level"] is not None

    # The shared word is not among the file's guesses, yet Cami may try it, and wins.
    assert shared not in sample()["guesses"]
    won = (await guess(cami, begun.id, shared)).json()
    assert (won["state"], won["solution"], won["laurels"]) == ("won", shared, 5)
    # The guesses are the file's now: the old lists no longer make a try.
    refused(await guess(leo, fresh.id, tried), 422, "validation_error")


# The level


async def test_only_who_plans_the_games_sets_the_wordle_level(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    stranger = await person(await make_org("Autre Rédac"), "editor", "Inconnue")
    planning = await ines.client.get(f"/api/orgs/{org.id}/games/schedule")
    assert planning.json()["wordle_level"] == 2

    changed = await set_level(ines, org.id, 3)
    assert changed.status_code == 200, changed.text
    assert changed.json() == planning.json() | {"wordle_level": 3}
    for someone in (hugo, cami):
        refused(await set_level(someone, org.id, 1), 403, "forbidden")
    refused(await set_level(stranger, org.id, 1), 404, "not_found")
    for wrong in (0, 4, 2.5, "facile", None):
        refused(await set_level(ines, org.id, wrong), 422, "validation_error")
    refused(await ines.client.put(url(org.id, "/level"), json={}), 422, "validation_error")

    async with transaction() as session:
        newsroom = await session.get(Organisation, org.id)
        assert newsroom is not None and newsroom.wordle_level == 3
    assert (await ines.client.get(f"/api/orgs/{org.id}/games/schedule")).json()["wordle_level"] == 3

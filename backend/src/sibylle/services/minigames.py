"""The mini-games of the week: the ball's race (US9, research.md J3 and R19) and Pixel mystère
(US10, J4).

The race: the server opens each run (seed, start) and counts the week's attempts; the game runs
in the browser and sends its score and duration, which the server checks before keeping them. On
Monday, the past week's ranking is paid to the balance, once per newsroom.

Pixel mystère: a journalist posts a drawing and its word; one drawing is active per newsroom, the
others wait. Its pixels show in proportion to the time gone over a week; whoever finds the word is
paid at once, 50 laurels at the opening falling to 3 at the end, whatever the rank. The game ends
when every other member found or the week is gone, and the next drawing starts the following
morning. Once over, a drawing goes to the newsroom's museum, whole and with its word.

Both follow the week's games (US12, research.md J7). Out of them, the race opens and finishes no
run, and Monday does not pay its week; Pixel mystère takes no guess and starts no drawing, and
the drawing in play ends with its word given.
"""

import base64
import secrets
import uuid
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import exists, func, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import (
    LedgerEntry,
    Membership,
    MinigamePayout,
    Organisation,
    PixelFind,
    PixelGuess,
    PixelPuzzle,
    RunnerRun,
    WordleDay,
    WordleGame,
)
from sibylle.domain.game_schedule import Game
from sibylle.domain.ledger import minigame, pixel_author_bonus, pixel_author_find
from sibylle.domain.minigames import (
    PIXEL_AUTHOR_BONUS,
    PIXEL_AUTHOR_PER_FIND,
    PIXEL_GUESSES_PER_DAY,
    RUN_MAX,
    RUNNER_ATTEMPTS,
    WORDLE_TRIES,
    WORDS_MAX,
    RunResult,
    letter_count,
    masked,
    next_start,
    normalize_word,
    pixel_gain,
    plausible,
    rank_runner,
    reveal_end,
    reveal_order,
    revealed_count,
    runner_gains,
    valid_word,
    week_to_pay,
    wordle_allowed,
    wordle_answer,
    wordle_gain,
    wordle_hint,
    wordle_level,
    wordle_marks,
    wordle_pick,
    wordle_tries,
    wordle_word,
)
from sibylle.domain.permissions import Action, can
from sibylle.domain.pixels import decode
from sibylle.domain.seasons import PARIS, week_start
from sibylle.realtime import bus
from sibylle.services import ledger, seasons, wordle_lists
from sibylle.services.game_schedule import games_of
from sibylle.services.orgs import checked_drawing, public_member, unlocked_colors

TOP = 10
# The browser's clock and the server's may differ a little.
CLOCK_SLACK_MS = 2_000


async def _on(
    session: AsyncSession, org_id: uuid.UUID, game: Game, week: date | None = None
) -> bool:
    """Whether the game is among the newsroom's games of that week (this week by default)."""
    return game in await games_of(session, org_id, week or week_start(clock.now()))


async def games(session: AsyncSession, member: Membership) -> dict[str, Any]:
    """What a member sees of the games: those of the current week, and the state of each. As on
    la une, Pixel mystère shows only what the newsroom sees so far, even to whoever found it or
    drew it: the whole drawing and its word stay on the game's own page."""
    scheduled = await games_of(session, member.org_id, week_start(clock.now()))
    return {
        "scheduled": scheduled,
        "runner": await runner_status(session, member) if "runner" in scheduled else None,
        "pixel": await pixel_status(session, member, on="pixel" in scheduled, home=True),
        "wordle": await wordle_status(session, member),
    }


async def _ranking(session: AsyncSession, org_id: uuid.UUID, week: date) -> list[RunResult]:
    """The week's finished runs of the newsroom's active members, best run each, best first."""
    rows = await session.execute(
        select(RunnerRun.membership_id, RunnerRun.score, RunnerRun.finished_at)
        .join(Membership, Membership.id == RunnerRun.membership_id)
        .where(
            RunnerRun.org_id == org_id,
            RunnerRun.week_start == week,
            RunnerRun.finished_at.is_not(None),
            RunnerRun.score > 0,
            Membership.status == "active",
        )
    )
    return rank_runner(
        RunResult(member_id, score, finished_at)
        for member_id, score, finished_at in rows
        if score is not None and finished_at is not None
    )


async def _top(session: AsyncSession, ranked: list[RunResult]) -> list[dict[str, Any]]:
    shown = ranked[:TOP]
    members = {
        member.id: member
        for member in await session.scalars(
            select(Membership).where(Membership.id.in_([run.member_id for run in shown]))
        )
    }
    return [
        {"member": members[run.member_id], "score": run.score, "rank": rank}
        for rank, run in enumerate(shown, start=1)
    ]


async def _attempts(session: AsyncSession, member: Membership, week: date) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(RunnerRun)
        .where(RunnerRun.membership_id == member.id, RunnerRun.week_start == week)
    )
    return int(count or 0)


async def runner_status(session: AsyncSession, member: Membership) -> dict[str, Any]:
    week = week_start(clock.now())
    ranked = await _ranking(session, member.org_id, week)
    mine = next((run for run in ranked if run.member_id == member.id), None)
    return {
        "week_start": week,
        "attempts_left": max(0, RUNNER_ATTEMPTS - await _attempts(session, member, week)),
        "my_best": mine.score if mine else None,
        "top": await _top(session, ranked),
    }


async def start_run(session: AsyncSession, member: Membership) -> RunnerRun:
    """Opens a run; it counts as an attempt even if it is never finished."""
    # One attempt at a time per member, so two taps cannot open a sixth run.
    await session.execute(select(Membership.id).where(Membership.id == member.id).with_for_update())
    week = week_start(clock.now())
    if not await _on(session, member.org_id, "runner", week):
        raise AppError("game_not_scheduled")
    if await _attempts(session, member, week) >= RUNNER_ATTEMPTS:
        raise AppError("attempts_exhausted")
    run = RunnerRun(
        org_id=member.org_id,
        membership_id=member.id,
        week_start=week,
        seed=secrets.randbits(31),
    )
    session.add(run)
    await session.flush()
    return run


async def finish_run(
    session: AsyncSession, member: Membership, run_id: uuid.UUID, score: int, duration_ms: int
) -> dict[str, Any]:
    run = await session.scalar(
        select(RunnerRun)
        .where(RunnerRun.id == run_id, RunnerRun.membership_id == member.id)
        .with_for_update()
    )
    if run is None:
        raise AppError("not_found")
    if run.finished_at is not None:
        raise AppError("run_finished")
    # A run counts for the week it started in, even when it ends on the Monday after.
    if not await _on(session, member.org_id, "runner", run.week_start):
        raise AppError("game_not_scheduled")
    now = clock.now()
    elapsed_ms = int((now - run.started_at).total_seconds() * 1000)
    if elapsed_ms > RUN_MAX.total_seconds() * 1000 + CLOCK_SLACK_MS:
        raise AppError("validation_error", {"duration_ms": "run_expired"})
    if duration_ms > elapsed_ms + CLOCK_SLACK_MS:
        raise AppError("validation_error", {"duration_ms": "longer_than_run"})
    if not plausible(score, duration_ms):
        raise AppError("validation_error", {"score": "implausible"})
    run.finished_at = now
    run.score = score
    run.duration_ms = duration_ms
    await session.flush()

    ranked = await _ranking(session, member.org_id, run.week_start)
    top = await _top(session, ranked)
    await bus.publish(
        session,
        "games.runner.updated",
        {
            "week_start": run.week_start.isoformat(),
            "top": [
                {"member": public_member(row["member"]), "score": row["score"], "rank": row["rank"]}
                for row in top
            ],
        },
        topics=[f"org:{member.org_id}"],
    )
    rank, best = next(
        ((i, r.score) for i, r in enumerate(ranked, start=1) if r.member_id == member.id),
        (None, score),
    )
    return {"score": score, "my_best": best, "rank": rank}


async def pay_runner_week(session: AsyncSession, *, org_id: uuid.UUID | None = None) -> int:
    """Pays the last finished week to each newsroom's players, once; returns how many were paid.

    A newsroom whose season closure is due waits for it, so that the season's reset never wipes
    the gains out. A week whose games no longer had the race when it ended is not paid. `org_id`
    keeps one newsroom only (tests on a shared database).
    """
    week = week_to_pay(clock.now())
    period = week.isoformat()
    newsroom = RunnerRun.org_id == org_id if org_id is not None else true()
    org_ids = (
        await session.scalars(
            select(RunnerRun.org_id)
            .join(Organisation, Organisation.id == RunnerRun.org_id)
            .where(
                newsroom,
                RunnerRun.week_start == week,
                RunnerRun.finished_at.is_not(None),
                Organisation.deleted_at.is_(None),
            )
            .distinct()
            .order_by(RunnerRun.org_id)
        )
    ).all()
    paid = 0
    for org in org_ids:
        if await seasons.due(session, org) or not await _on(session, org, "runner", week):
            continue
        claimed = await session.scalar(
            insert(MinigamePayout)
            .values(org_id=org, game="runner", period_key=period, paid_at=clock.now())
            .on_conflict_do_nothing()
            .returning(MinigamePayout.org_id)
        )
        if claimed is None:
            continue
        gains = runner_gains(await _ranking(session, org, week))
        # Locked in id order, like the settlements, so that both cannot deadlock.
        await session.execute(
            select(Membership.id)
            .where(Membership.id.in_([member_id for member_id, _ in gains]))
            .order_by(Membership.id)
            .with_for_update()
        )
        for member_id, gain in gains:
            await ledger.append(session, member_id, minigame(gain), reason=f"runner:{period}")
        paid += len(gains)
    return paid


# Pixel mystère


def _today() -> date:
    return clock.now().astimezone(PARIS).date()


async def _current(
    session: AsyncSession, org_id: uuid.UUID, *, lock: bool = False
) -> PixelPuzzle | None:
    """The active drawing, or else the last finished one (its word stays up until the next)."""
    query = (
        select(PixelPuzzle)
        .where(PixelPuzzle.org_id == org_id, PixelPuzzle.state.in_(("active", "finished")))
        .order_by((PixelPuzzle.state == "active").desc(), PixelPuzzle.finished_at.desc())
        .limit(1)
    )
    if lock:
        query = query.with_for_update()
    puzzle: PixelPuzzle | None = await session.scalar(query)
    return puzzle


async def _finds(session: AsyncSession, puzzle: PixelPuzzle) -> list[tuple[PixelFind, Membership]]:
    rows = await session.execute(
        select(PixelFind, Membership)
        .join(Membership, Membership.id == PixelFind.membership_id)
        .where(PixelFind.puzzle_id == puzzle.id)
        .order_by(PixelFind.rank)
    )
    return [(found, member) for found, member in rows]


async def _guesses_today(session: AsyncSession, puzzle: PixelPuzzle, member: Membership) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(PixelGuess)
        .where(
            PixelGuess.puzzle_id == puzzle.id,
            PixelGuess.membership_id == member.id,
            PixelGuess.day == _today(),
        )
    )
    return int(count or 0)


def _total(puzzle: PixelPuzzle) -> int:
    return int(puzzle.drawing["size"]) ** 2


def _shown(puzzle: PixelPuzzle) -> int:
    """The pixels showing now: worked out from the clock, not read from the last reveal."""
    if puzzle.state != "active" or puzzle.started_at is None:
        return _total(puzzle) if puzzle.state == "finished" else puzzle.revealed_count
    return revealed_count(int(puzzle.drawing["size"]), puzzle.started_at, clock.now())


def _gain_now(puzzle: PixelPuzzle) -> int:
    """The laurels whoever finds the word now would win."""
    assert puzzle.started_at is not None
    return pixel_gain(clock.now() - puzzle.started_at)


async def _ends_at(session: AsyncSession, puzzle: PixelPuzzle) -> datetime:
    """When an active drawing ends unless everyone finds it first: the morning its last pixels
    show, or before that the Monday of a week without Pixel mystère."""
    assert puzzle.started_at is not None
    end = reveal_end(puzzle.started_at)
    week = week_start(clock.now())
    while True:
        week += timedelta(days=7)
        monday = datetime(week.year, week.month, week.day, tzinfo=PARIS)
        if monday >= end:
            return end
        if not await _on(session, puzzle.org_id, "pixel", week):
            return monday


async def _author_earned(session: AsyncSession, puzzle: PixelPuzzle) -> int:
    """What a drawing has paid its author so far: the bonus and the finds."""
    total = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
            LedgerEntry.membership_id == puzzle.author_membership_id,
            LedgerEntry.kind.in_(("pixel_author_bonus", "pixel_author_find")),
            LedgerEntry.reason.like(f"pixel-%:{puzzle.id}%"),
        )
    )
    return int(total or 0)


async def pixel_status(
    session: AsyncSession, member: Membership, *, on: bool | None = None, home: bool = False
) -> dict[str, Any] | None:
    """What a member sees: the pixels shown so far, or the whole drawing and its word once they
    found it, drew it, or the game ended. In a week without Pixel mystère (`on` false), only the
    last drawing once finished, so that the word of a drawing stopped by the planning is given.
    For la une (`home`), the whole drawing and the word only once the game ended: whoever found
    or drew it sees it masked like everyone else."""
    if on is None:
        on = await _on(session, member.org_id, "pixel")
    puzzle = await _current(session, member.org_id)
    if puzzle is None or (not on and puzzle.state != "finished"):
        return None
    finds = await _finds(session, puzzle)
    found = any(m.id == member.id for _, m in finds)
    mine = puzzle.author_membership_id == member.id
    open_book = puzzle.state == "finished" or (not home and (found or mine))
    pixels = decode(puzzle.drawing)
    shown = _shown(puzzle)
    left = 0
    if puzzle.state == "active" and not found and not mine:
        left = max(0, PIXEL_GUESSES_PER_DAY - await _guesses_today(session, puzzle, member))
    return {
        "puzzle_id": puzzle.id,
        "size": puzzle.drawing["size"],
        "revealed": base64.b64encode(
            pixels if open_book else masked(pixels, puzzle.reveal_order, shown)
        ).decode(),
        # What the newsroom sees so far, even for whoever sees the whole drawing.
        "revealed_count": shown,
        "letters": letter_count(puzzle.words[0]),
        "guesses_left_today": left,
        "finds": [{"member": m, "rank": f.rank} for f, m in finds],
        "found_by_me": found,
        "mine": mine,
        "state": puzzle.state,
        "word": puzzle.words[0] if open_book else None,
        "words": puzzle.words if open_book else None,
        "ends_at": await _ends_at(session, puzzle) if puzzle.state == "active" else None,
        "started_at": puzzle.started_at if puzzle.state == "active" else None,
        "gain_ends_at": reveal_end(puzzle.started_at)
        if puzzle.state == "active" and puzzle.started_at
        else None,
        "author_earned": await _author_earned(session, puzzle) if mine else None,
        "gain_now": _gain_now(puzzle)
        if puzzle.state == "active" and not found and not mine
        else None,
    }


async def _activate(session: AsyncSession, puzzle: PixelPuzzle, now: datetime) -> None:
    puzzle.state = "active"
    puzzle.started_at = now
    puzzle.revealed_count = revealed_count(int(puzzle.drawing["size"]), now, now)
    await session.flush()
    # Only a queued drawing is activated, under the newsroom's lock: the bonus is paid once.
    await ledger.append(
        session,
        puzzle.author_membership_id,
        pixel_author_bonus(PIXEL_AUTHOR_BONUS),
        reason=f"pixel-bonus:{puzzle.id}",
    )
    await bus.publish(
        session,
        "games.pixel.revealed",
        {"puzzle_id": str(puzzle.id), "revealed_count": puzzle.revealed_count},
        topics=[f"org:{puzzle.org_id}"],
    )


async def _activate_next(session: AsyncSession, org_id: uuid.UUID) -> bool:
    """Starts the oldest waiting drawing when Pixel mystère is among the week's games, none is
    active and the last one ended before this morning's 08:00. Returns whether one started."""
    # One activation at a time per newsroom: two posts at once cannot both start theirs.
    await session.execute(
        select(Organisation.id).where(Organisation.id == org_id).with_for_update(key_share=True)
    )
    if not await _on(session, org_id, "pixel"):
        return False
    states = dict(
        (
            await session.execute(
                select(PixelPuzzle.state, func.max(PixelPuzzle.finished_at))
                .where(PixelPuzzle.org_id == org_id)
                .group_by(PixelPuzzle.state)
            )
        ).all()
    )
    if "active" in states or "queued" not in states:
        return False
    now = clock.now()
    last_finished = states.get("finished")
    if last_finished is not None and now < next_start(last_finished):
        return False
    waiting = await session.scalar(
        select(PixelPuzzle)
        .where(PixelPuzzle.org_id == org_id, PixelPuzzle.state == "queued")
        .order_by(PixelPuzzle.created_at, PixelPuzzle.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if waiting is None:
        return False
    await _activate(session, waiting, now)
    return True


async def _finish(session: AsyncSession, puzzle: PixelPuzzle) -> None:
    puzzle.state = "finished"
    puzzle.finished_at = clock.now()
    puzzle.revealed_count = _total(puzzle)
    await session.flush()
    await bus.publish(
        session,
        "games.pixel.finished",
        {"puzzle_id": str(puzzle.id), "word": puzzle.words[0]},
        topics=[f"org:{puzzle.org_id}"],
    )


async def _everyone_found(session: AsyncSession, puzzle: PixelPuzzle) -> bool:
    """Every active member but the author has found the word."""
    missing = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.org_id == puzzle.org_id,
            Membership.status == "active",
            Membership.id != puzzle.author_membership_id,
            Membership.id.notin_(
                select(PixelFind.membership_id).where(PixelFind.puzzle_id == puzzle.id)
            ),
        )
    )
    return not missing


async def post_puzzle(
    session: AsyncSession,
    member: Membership,
    drawing: dict[str, Any],
    word: str,
    other_words: Sequence[str] = (),
) -> PixelPuzzle:
    if not can(member.role, Action.CREATE_PUZZLE):
        raise AppError("forbidden")
    checked = checked_drawing("drawing", drawing, await unlocked_colors(session, member))
    word = " ".join(word.split())
    if not valid_word(word):
        raise AppError("validation_error", {"word": "invalid"})
    words = [word]
    for other in other_words:
        other = " ".join(other.split())
        if not valid_word(other):
            raise AppError("validation_error", {"other_words": "invalid"})
        words.append(other)
    if len(words) > WORDS_MAX:
        raise AppError("validation_error", {"other_words": "too_many"})
    normalized = [normalize_word(w) for w in words]
    if len(set(normalized)) != len(normalized):
        raise AppError("validation_error", {"other_words": "duplicate"})
    puzzle = PixelPuzzle(
        org_id=member.org_id,
        author_membership_id=member.id,
        drawing=checked,
        words=words,
        words_normalized=normalized,
        reveal_order=reveal_order(int(checked["size"])),
    )
    session.add(puzzle)
    await session.flush()
    await _activate_next(session, member.org_id)
    return puzzle


async def queue(session: AsyncSession, member: Membership) -> list[dict[str, Any]]:
    """The drawings to come, and the one in play: each journalist sees the word and drawing of
    their own only, so that they can still play the others'."""
    if not can(member.role, Action.CREATE_PUZZLE):
        raise AppError("forbidden")
    puzzles = (
        await session.scalars(
            select(PixelPuzzle)
            .where(PixelPuzzle.org_id == member.org_id, PixelPuzzle.state.in_(("active", "queued")))
            .order_by((PixelPuzzle.state == "active").desc(), PixelPuzzle.created_at)
        )
    ).all()
    return [
        {
            "puzzle_id": puzzle.id,
            "state": puzzle.state,
            "size": puzzle.drawing["size"],
            "letters": letter_count(puzzle.words[0]),
            "mine": puzzle.author_membership_id == member.id,
            "word": puzzle.words[0] if puzzle.author_membership_id == member.id else None,
            "words": puzzle.words if puzzle.author_membership_id == member.id else None,
            "drawing": puzzle.drawing if puzzle.author_membership_id == member.id else None,
            "created_at": puzzle.created_at,
        }
        for puzzle in puzzles
    ]


async def museum(session: AsyncSession, member: Membership) -> list[dict[str, Any]]:
    """The newsroom's drawings whose game is over, the latest first: whole, with their main word,
    their author and how many found them. Never one waiting or in play, whose word is still to
    find. Open to every member, whatever the week's games."""
    found = (
        select(func.count())
        .select_from(PixelFind)
        .where(PixelFind.puzzle_id == PixelPuzzle.id)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(
            PixelPuzzle.id,
            PixelPuzzle.drawing,
            PixelPuzzle.words,
            PixelPuzzle.finished_at,
            Membership,
            found,
        )
        .join(Membership, Membership.id == PixelPuzzle.author_membership_id)
        .where(PixelPuzzle.org_id == member.org_id, PixelPuzzle.state == "finished")
        .order_by(PixelPuzzle.finished_at.desc(), PixelPuzzle.id)
    )
    return [
        {
            "puzzle_id": puzzle_id,
            "size": drawing["size"],
            "drawing": drawing,
            "word": words[0],
            "author": author,
            "finished_at": finished_at,
            "found_count": count,
        }
        for puzzle_id, drawing, words, finished_at, author, count in rows
    ]


async def guess(session: AsyncSession, member: Membership, word: str) -> dict[str, Any]:
    if not await _on(session, member.org_id, "pixel"):
        raise AppError("game_not_scheduled")
    puzzle = await _current(session, member.org_id, lock=True)
    if puzzle is None or puzzle.state != "active":
        raise AppError("invalid_state")
    if puzzle.author_membership_id == member.id:
        raise AppError("forbidden")
    if any(m.id == member.id for _, m in await _finds(session, puzzle)):
        raise AppError("invalid_state")
    if await _guesses_today(session, puzzle, member) >= PIXEL_GUESSES_PER_DAY:
        raise AppError("attempts_exhausted")
    normalized = normalize_word(word)
    correct = normalized in puzzle.words_normalized
    session.add(
        PixelGuess(
            puzzle_id=puzzle.id,
            membership_id=member.id,
            guess_normalized=normalized,
            correct=correct,
            day=_today(),
        )
    )
    await session.flush()
    left = PIXEL_GUESSES_PER_DAY - await _guesses_today(session, puzzle, member)
    if not correct:
        return {"correct": False, "rank": None, "laurels": None, "guesses_left_today": left}

    # The puzzle is locked: ranks are handed out one at a time.
    rank = len(await _finds(session, puzzle)) + 1
    assert puzzle.started_at is not None
    laurels = _gain_now(puzzle)
    session.add(PixelFind(puzzle_id=puzzle.id, membership_id=member.id, rank=rank, laurels=laurels))
    await ledger.append(session, member.id, minigame(laurels), reason=f"pixel:{puzzle.words[0]}")
    # One find per member (checked above, puzzle locked): the author is paid once for each.
    await ledger.append(
        session,
        puzzle.author_membership_id,
        pixel_author_find(PIXEL_AUTHOR_PER_FIND),
        reason=f"pixel-find:{puzzle.id}:{rank}",
    )
    await bus.publish(
        session,
        "games.pixel.found",
        {"puzzle_id": str(puzzle.id), "member": public_member(member), "rank": rank},
        topics=[f"org:{member.org_id}"],
    )
    if await _everyone_found(session, puzzle):
        await _finish(session, puzzle)
    return {"correct": True, "rank": rank, "laurels": laurels, "guesses_left_today": left}


async def reveal_pixel_puzzles(session: AsyncSession, *, org_id: uuid.UUID | None = None) -> int:
    """Shows the morning's pixels, ends the drawings fully shown or found by everyone, or whose
    newsroom has no Pixel mystère this week, and starts the waiting ones whose morning has come.
    Returns how many drawings changed."""
    now = clock.now()
    newsroom = PixelPuzzle.org_id == org_id if org_id is not None else true()
    changed = 0
    active = (
        await session.scalars(
            select(PixelPuzzle)
            .where(newsroom, PixelPuzzle.state == "active")
            .with_for_update(skip_locked=True)
        )
    ).all()
    for puzzle in active:
        assert puzzle.started_at is not None
        if not await _on(session, puzzle.org_id, "pixel"):
            await _finish(session, puzzle)
            changed += 1
            continue
        target = revealed_count(int(puzzle.drawing["size"]), puzzle.started_at, now)
        if now >= reveal_end(puzzle.started_at) or await _everyone_found(session, puzzle):
            await _finish(session, puzzle)
            changed += 1
        elif target > puzzle.revealed_count:
            puzzle.revealed_count = target
            await bus.publish(
                session,
                "games.pixel.revealed",
                {"puzzle_id": str(puzzle.id), "revealed_count": target},
                topics=[f"org:{puzzle.org_id}"],
            )
            changed += 1
    waiting = (
        await session.scalars(
            select(PixelPuzzle.org_id).where(newsroom, PixelPuzzle.state == "queued").distinct()
        )
    ).all()
    for org in waiting:
        changed += await _activate_next(session, org)
    return changed


async def follow_schedule(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Makes Pixel mystère follow a change of the current week's games: taken out, the drawing
    in play ends and gives its word, the laurels won staying; put back, the next one may start."""
    if await _on(session, org_id, "pixel"):
        await _activate_next(session, org_id)
        return
    playing = await session.scalar(
        select(PixelPuzzle)
        .where(PixelPuzzle.org_id == org_id, PixelPuzzle.state == "active")
        .with_for_update()
    )
    if playing is not None:
        await _finish(session, playing)


# Wordle: a word a day for each newsroom, six tries for each member; always on, whatever the
# week's games. The worker draws the word at midnight (`prepare_wordle_day`), or the first look at
# the game does if it has not yet; then it is kept. It stays on the server until the member's
# game is over. A word of level 4 or more gives whoever missed it six times a last chance: its
# letters in alphabetical order, and a seventh try, a win without laurels.

# The draw among the words left; the tests put a known one in its place.
wordle_choice: Callable[[Sequence[str]], str] = secrets.choice


async def _draw(session: AsyncSession, org_id: uuid.UUID, day: date) -> tuple[str, int | None]:
    """A word for the newsroom's `day`, and its level. The day the draw came in, a newsroom
    whose members had begun the game keeps the word every newsroom then shared, without a level,
    so that the tries already made keep their colours."""
    begun = await session.scalar(
        select(exists().where(WordleGame.org_id == org_id, WordleGame.day == day))
    )
    if begun:
        return wordle_answer(day), None
    lists = await wordle_lists.current(session)
    newsroom_level = await session.scalar(
        select(Organisation.wordle_level).where(Organisation.id == org_id)
    )
    assert newsroom_level is not None
    history = await session.execute(
        select(WordleDay.day, WordleDay.word).where(WordleDay.org_id == org_id)
    )
    word = wordle_pick(wordle_allowed(lists, newsroom_level), history.all(), day, wordle_choice)
    return word, wordle_level(lists, word)


async def _word_of_day(session: AsyncSession, org_id: uuid.UUID, day: date) -> WordleDay:
    """The newsroom's word of `day`, drawn now if it has none yet; several first looks at once
    still make a single draw. Once kept, neither the word nor its level change."""
    query = select(WordleDay).where(WordleDay.org_id == org_id, WordleDay.day == day)
    kept: WordleDay | None = await session.scalar(query)
    if kept is not None:
        return kept
    word, level = await _draw(session, org_id, day)
    await session.execute(
        insert(WordleDay)
        .values(org_id=org_id, day=day, word=word, level=level, created_at=clock.now())
        .on_conflict_do_nothing()
    )
    drawn: WordleDay | None = await session.scalar(query.execution_options(populate_existing=True))
    assert drawn is not None
    return drawn


async def prepare_wordle_day(session: AsyncSession) -> int:
    """Draws today's word (Paris) of each newsroom that has none yet; returns how many."""
    day = _today()
    missing = (
        await session.scalars(
            select(Organisation.id)
            .where(
                Organisation.deleted_at.is_(None),
                ~exists().where(WordleDay.org_id == Organisation.id, WordleDay.day == day),
            )
            .order_by(Organisation.id)
        )
    ).all()
    for org_id in missing:
        await _word_of_day(session, org_id, day)
    return len(missing)


async def set_wordle_level(session: AsyncSession, org_id: uuid.UUID, level: int) -> None:
    """Sets the newsroom's Wordle level, which counts from tomorrow's word: today's is drawn
    first, on the level it had, if nobody has looked at the game yet today."""
    await _word_of_day(session, org_id, _today())
    await session.execute(
        update(Organisation).where(Organisation.id == org_id).values(wordle_level=level)
    )


async def _wordle_game(
    session: AsyncSession, member: Membership, day: date, *, lock: bool = False
) -> WordleGame | None:
    query = select(WordleGame).where(WordleGame.membership_id == member.id, WordleGame.day == day)
    if lock:
        query = query.with_for_update()
    game: WordleGame | None = await session.scalar(query)
    return game


def _wordle_view(game: WordleGame | None, today: WordleDay) -> dict[str, Any]:
    guesses = list(game.guesses) if game else []
    state = game.state if game else "playing"
    # Six tries missed and the game still on: the last chance, which only a word of level 4 or
    # more gives.
    last_chance = state == "playing" and len(guesses) == WORDLE_TRIES
    return {
        "day": today.day,
        "state": state,
        "level": today.level,
        "tries": [{"word": word, "marks": wordle_marks(word, today.word)} for word in guesses],
        "tries_left": 1 if last_chance else max(WORDLE_TRIES - len(guesses), 0),
        "hint": wordle_hint(today.word) if last_chance else None,
        "laurels": game.laurels if game else None,
        "solution": today.word if state != "playing" else None,
    }


async def wordle_status(session: AsyncSession, member: Membership) -> dict[str, Any]:
    day = _today()
    today = await _word_of_day(session, member.org_id, day)
    return _wordle_view(await _wordle_game(session, member, day), today)


async def wordle_guess(session: AsyncSession, member: Membership, text: str) -> dict[str, Any]:
    """One try at the newsroom's word of the day: validated, marked, kept. A try is one of the
    word file's guesses, or the word of the day itself. The game of the day is created by the
    first try; the win is paid at once, once, as no try is taken after the game is over. The
    sixth try missed ends it, unless the word gives a last chance (`wordle_tries`): then the
    seventh does, and finding the word there is a win that pays nothing."""
    # One try at a time per member, so two taps cannot take a try too many or pay twice.
    await session.execute(select(Membership.id).where(Membership.id == member.id).with_for_update())
    day = _today()
    today = await _word_of_day(session, member.org_id, day)
    lists = await wordle_lists.current(session)
    word = wordle_word(text, lists.guesses, today.word)
    if word is None:
        raise AppError("validation_error", {"word": "unknown_word"})
    game = await _wordle_game(session, member, day, lock=True)
    if game is None:
        game = WordleGame(
            org_id=member.org_id, membership_id=member.id, day=day, guesses=[], state="playing"
        )
        session.add(game)
    if game.state != "playing":
        raise AppError("wordle_over")
    game.guesses = [*game.guesses, word]
    if word == today.word:
        game.state = "won"
        game.laurels = wordle_gain(len(game.guesses))
        # Found at the last chance: a win all the same, but nothing for the ledger, which takes
        # no gain of 0.
        if game.laurels > 0:
            await ledger.append(
                session, member.id, minigame(game.laurels), reason=f"wordle:{day.isoformat()}"
            )
    elif len(game.guesses) >= wordle_tries(today.level):
        game.state = "lost"
    await session.flush()
    return _wordle_view(game, today)

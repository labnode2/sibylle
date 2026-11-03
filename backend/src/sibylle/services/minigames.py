"""The mini-games of the week: the ball's race (US9, research.md J3 and R19) and Pixel mystère
(US10, J4).

The race: the server opens each run (seed, start) and counts the week's attempts; the game runs
in the browser and sends its score and duration, which the server checks before keeping them. On
Monday, the past week's ranking is paid to the balance, once per newsroom.

Pixel mystère: a journalist posts a drawing and its word; one drawing is active per newsroom, the
others wait. A seventh of its pixels shows at the opening and each morning; the first members to
find the word are paid at once. The game ends when every other member found or every pixel shows,
and the next drawing starts the following morning.
"""

import base64
import secrets
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import (
    Membership,
    MinigamePayout,
    Organisation,
    PixelFind,
    PixelGuess,
    PixelPuzzle,
    RunnerRun,
)
from sibylle.domain.ledger import minigame
from sibylle.domain.minigames import (
    PIXEL_GUESSES_PER_DAY,
    RUN_MAX,
    RUNNER_ATTEMPTS,
    RunResult,
    letter_count,
    masked,
    next_start,
    normalize_word,
    pixel_gain,
    plausible,
    rank_runner,
    reveal_order,
    revealed_count,
    runner_gains,
    valid_word,
    week_to_pay,
)
from sibylle.domain.permissions import Action, can
from sibylle.domain.pixels import decode
from sibylle.domain.seasons import PARIS, week_start
from sibylle.realtime import bus
from sibylle.services import ledger, seasons
from sibylle.services.orgs import checked_drawing, public_member, unlocked_colors

TOP = 10
# The browser's clock and the server's may differ a little.
CLOCK_SLACK_MS = 2_000


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
    the gains out. `org_id` keeps one newsroom only (tests on a shared database).
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
        if await seasons.due(session, org):
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


async def pixel_status(session: AsyncSession, member: Membership) -> dict[str, Any] | None:
    """What a member sees: the pixels shown so far, or the whole drawing and its word once they
    found it, drew it, or the game ended."""
    puzzle = await _current(session, member.org_id)
    if puzzle is None:
        return None
    finds = await _finds(session, puzzle)
    found = any(m.id == member.id for _, m in finds)
    mine = puzzle.author_membership_id == member.id
    open_book = found or mine or puzzle.state == "finished"
    pixels = decode(puzzle.drawing)
    left = 0
    if puzzle.state == "active" and not found and not mine:
        left = max(0, PIXEL_GUESSES_PER_DAY - await _guesses_today(session, puzzle, member))
    return {
        "puzzle_id": puzzle.id,
        "size": puzzle.drawing["size"],
        "revealed": base64.b64encode(
            pixels if open_book else masked(pixels, puzzle.reveal_order, puzzle.revealed_count)
        ).decode(),
        # What the newsroom sees so far, even for whoever sees the whole drawing.
        "revealed_count": puzzle.revealed_count,
        "letters": letter_count(puzzle.word),
        "guesses_left_today": left,
        "finds": [{"member": m, "rank": f.rank} for f, m in finds],
        "found_by_me": found,
        "mine": mine,
        "state": puzzle.state,
        "word": puzzle.word if open_book else None,
    }


async def _activate(session: AsyncSession, puzzle: PixelPuzzle, now: datetime) -> None:
    puzzle.state = "active"
    puzzle.started_at = now
    puzzle.revealed_count = revealed_count(int(puzzle.drawing["size"]), now, now)
    await session.flush()
    await bus.publish(
        session,
        "games.pixel.revealed",
        {"puzzle_id": str(puzzle.id), "revealed_count": puzzle.revealed_count},
        topics=[f"org:{puzzle.org_id}"],
    )


async def _activate_next(session: AsyncSession, org_id: uuid.UUID) -> bool:
    """Starts the oldest waiting drawing when none is active and the last one ended before this
    morning's 08:00. Returns whether one started."""
    # One activation at a time per newsroom: two posts at once cannot both start theirs.
    await session.execute(
        select(Organisation.id).where(Organisation.id == org_id).with_for_update(key_share=True)
    )
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
        {"puzzle_id": str(puzzle.id), "word": puzzle.word},
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
    session: AsyncSession, member: Membership, drawing: dict[str, Any], word: str
) -> PixelPuzzle:
    if not can(member.role, Action.CREATE_PUZZLE):
        raise AppError("forbidden")
    checked = checked_drawing("drawing", drawing, await unlocked_colors(session, member))
    word = " ".join(word.split())
    if not valid_word(word):
        raise AppError("validation_error", {"word": "invalid"})
    puzzle = PixelPuzzle(
        org_id=member.org_id,
        author_membership_id=member.id,
        drawing=checked,
        word=word,
        word_normalized=normalize_word(word),
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
            "letters": letter_count(puzzle.word),
            "mine": puzzle.author_membership_id == member.id,
            "word": puzzle.word if puzzle.author_membership_id == member.id else None,
            "drawing": puzzle.drawing if puzzle.author_membership_id == member.id else None,
            "created_at": puzzle.created_at,
        }
        for puzzle in puzzles
    ]


async def guess(session: AsyncSession, member: Membership, word: str) -> dict[str, Any]:
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
    correct = normalized == puzzle.word_normalized
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
    laurels = pixel_gain(rank)
    session.add(PixelFind(puzzle_id=puzzle.id, membership_id=member.id, rank=rank, laurels=laurels))
    await ledger.append(session, member.id, minigame(laurels), reason=f"pixel:{puzzle.word}")
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
    """Shows the morning's pixels, ends the drawings fully shown or found by everyone, and starts
    the waiting ones whose morning has come. Returns how many drawings changed."""
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
        target = revealed_count(int(puzzle.drawing["size"]), puzzle.started_at, now)
        if target >= _total(puzzle) or await _everyone_found(session, puzzle):
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

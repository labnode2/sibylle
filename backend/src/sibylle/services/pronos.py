"""Pronos: publishing, editing, listing, the detail screen and state changes."""

import base64
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, delete, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import (
    Bet,
    LedgerEntry,
    Membership,
    Organisation,
    Prono,
    PronoEvent,
    PronoOption,
    Reaction,
    Report,
    Section,
    Settlement,
    Upload,
)
from sibylle.domain.betting import Kind, PronoDraft, ValidationFailed, distribution, validate_prono
from sibylle.domain.content import REACTION_KINDS
from sibylle.domain.ledger import LedgerKind
from sibylle.domain.lifecycle import Event, InvalidTransition, State, can_edit, transition
from sibylle.domain.permissions import Action, can
from sibylle.domain.seasons import PARIS
from sibylle.realtime import bus
from sibylle.services import notifications
from sibylle.services.orgs import public_member

HIDDEN_STATES = (State.PROPOSED.value, State.REJECTED.value)
PAYOUT_KINDS = (LedgerKind.BASE_GAIN, LedgerKind.EARLY_BIRD, LedgerKind.POT_SHARE)
EDITABLE_FIELDS = (
    "kind",
    "question",
    "section_id",
    "base_gain",
    "link_url",
    "image_id",
    "opens_at",
    "closes_at",
    "open_ended",
    "result_expected_at",
    "number_unit",
)


def _is_newsroom(member: Membership) -> bool:
    return can(member.role, Action.PUBLISH_PRONO)


def visible_to(member: Membership) -> Any:
    """Proposals stay between their author and the journalists (US5)."""
    if _is_newsroom(member):
        return Prono.org_id == member.org_id
    return and_(
        Prono.org_id == member.org_id,
        or_(Prono.state.notin_(HIDDEN_STATES), Prono.created_by == member.id),
    )


async def get_prono(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, *, lock: bool = False
) -> Prono:
    query: Select[Prono] = select(Prono).where(Prono.id == prono_id, visible_to(member))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    prono = await session.scalar(query)
    if prono is None:
        raise AppError("not_found")
    return prono


async def record_event(
    session: AsyncSession,
    prono: Prono,
    kind: str,
    actor: Membership | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    session.add(
        PronoEvent(
            prono_id=prono.id,
            kind=kind,
            actor_membership_id=actor.id if actor else None,
            data=data or {},
        )
    )


async def announce(
    session: AsyncSession, prono: Prono, event: str, data: dict[str, Any], topics: list[str]
) -> None:
    """Tells the screens about a prono; a proposal reaches only the journalists and its author."""
    if prono.state in HIDDEN_STATES:
        await bus.publish(session, event, data, topics=topics, audience="journalists")
        await bus.publish(session, event, data, topics=topics, audience=[prono.created_by])
    else:
        await bus.publish(session, event, data, topics=topics)


async def set_state(
    session: AsyncSession,
    prono: Prono,
    state: State,
    event: str,
    actor: Membership | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Moves a prono to a new state, keeps its history and tells the screens; a prono that
    opens (scheduled or proposed until now) is news for the newsroom."""
    opening = state is State.OPEN and prono.state in (State.SCHEDULED, State.PROPOSED)
    prono.state = state.value
    await record_event(session, prono, event, actor, data)
    await session.flush()
    if opening:
        await notifications.prono_opened(session, prono, actor)
    await announce(
        session,
        prono,
        "prono.state_changed",
        {
            "prono_id": str(prono.id),
            "state": prono.state,
            "closes_at": prono.closes_at.isoformat() if prono.closes_at else None,
            "relaunch_count": prono.relaunch_count,
        },
        [f"org:{prono.org_id}", f"prono:{prono.id}"],
    )


async def _check_links(
    session: AsyncSession, org_id: uuid.UUID, section_id: uuid.UUID, image_id: uuid.UUID | None
) -> None:
    section = await session.get(Section, section_id)
    if section is None or section.org_id != org_id or section.archived_at is not None:
        raise AppError("validation_error", {"section_id": "unknown"})
    if image_id is not None:
        upload = await session.get(Upload, image_id)
        if upload is None or upload.org_id != org_id:
            raise AppError("validation_error", {"image_id": "unknown"})


def _validated(fields: dict[str, Any], options: list[str], org: Organisation) -> list[str]:
    draft = PronoDraft(
        kind=Kind(fields["kind"]),
        question=fields["question"],
        base_gain=fields["base_gain"],
        options=options,
        link_url=fields.get("link_url"),
        opens_at=fields.get("opens_at"),
        closes_at=fields.get("closes_at"),
        open_ended=bool(fields.get("open_ended")),
        result_expected_at=fields.get("result_expected_at"),
    )
    try:
        return validate_prono(draft, max_base_gain=org.max_base_gain, now=clock.now())
    except ValidationFailed as error:
        raise AppError("validation_error", error.fields) from error


async def _replace_options(session: AsyncSession, prono: Prono, labels: list[str]) -> None:
    for option in (
        await session.scalars(select(PronoOption).where(PronoOption.prono_id == prono.id))
    ).all():
        await session.delete(option)
    await session.flush()
    for position, label in enumerate(labels):
        session.add(PronoOption(prono_id=prono.id, label=label, position=position))


async def create_prono(session: AsyncSession, member: Membership, fields: dict[str, Any]) -> Prono:
    """A journalist publishes; a reader proposes, and the prono waits for a journalist."""
    publishing = can(member.role, Action.PUBLISH_PRONO)
    if not publishing and not can(member.role, Action.PROPOSE_PRONO):
        raise AppError("forbidden")
    org = await session.get(Organisation, member.org_id)
    assert org is not None
    await _check_links(session, org.id, fields["section_id"], fields.get("image_id"))
    labels = _validated(fields, fields.get("options") or [], org)
    now = clock.now()
    opens_at = fields.get("opens_at")
    # The newsroom's row stays locked until the commit: two pronos never share a number.
    number = await session.scalar(
        update(Organisation)
        .where(Organisation.id == org.id)
        .values(last_prono_number=Organisation.last_prono_number + 1)
        .returning(Organisation.last_prono_number)
    )
    prono = Prono(
        org_id=org.id,
        number=number,
        **{name: fields.get(name) for name in EDITABLE_FIELDS},
        state=(
            State.PROPOSED
            if not publishing
            else State.SCHEDULED
            if opens_at and opens_at > now
            else State.OPEN
        ).value,
        created_by=member.id,
    )
    prono.question = prono.question.strip()
    prono.open_ended = bool(prono.open_ended)
    session.add(prono)
    await session.flush()
    await _replace_options(session, prono, labels)
    await record_event(session, prono, "created" if publishing else "proposed", member)
    await session.flush()
    if prono.state == State.OPEN:
        await notifications.prono_opened(session, prono, member)
    await announce(
        session,
        prono,
        "prono.created",
        {"prono": {"id": str(prono.id), "question": prono.question, "state": prono.state}},
        [f"org:{org.id}"],
    )
    return prono


async def _option_labels(session: AsyncSession, prono: Prono) -> list[str]:
    return list(
        (
            await session.scalars(
                select(PronoOption.label)
                .where(PronoOption.prono_id == prono.id)
                .order_by(PronoOption.position)
            )
        ).all()
    )


def _after(prono: Prono, event: Event) -> State:
    try:
        return transition(
            State(prono.state),
            event,
            opens_in_future=bool(prono.opens_at and prono.opens_at > clock.now()),
        )
    except InvalidTransition as error:
        raise AppError("invalid_state") from error


async def validate_proposal(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, base_gain: int | None
) -> Prono:
    """Publishes a reader's proposal, with the gain the journalist chooses."""
    if not can(member.role, Action.VALIDATE_PROPOSAL):
        raise AppError("forbidden")
    prono = await get_prono(session, member, prono_id, lock=True)
    state = _after(prono, Event.VALIDATE)
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    fields = {name: getattr(prono, name) for name in EDITABLE_FIELDS}
    if base_gain is not None:
        fields["base_gain"] = base_gain
    # The ceiling and the dates are checked again: the proposal may have waited.
    _validated(fields, await _option_labels(session, prono), org)
    prono.base_gain = fields["base_gain"]
    prono.validated_by = member.id
    await set_state(session, prono, state, "validated", member, {"base_gain": prono.base_gain})
    return prono


async def reject_proposal(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, reason: str | None
) -> Prono:
    """Turns a proposal down; its author sees the reason."""
    if not can(member.role, Action.VALIDATE_PROPOSAL):
        raise AppError("forbidden")
    prono = await get_prono(session, member, prono_id, lock=True)
    state = _after(prono, Event.REJECT)
    prono.rejected_reason = reason
    await set_state(session, prono, state, "rejected", member, {"reason": reason} if reason else {})
    return prono


async def reaction_counts(session: AsyncSession, prono_id: uuid.UUID) -> dict[str, int]:
    rows = await session.execute(
        select(Reaction.kind, func.count())
        .where(Reaction.prono_id == prono_id)
        .group_by(Reaction.kind)
    )
    counts = {kind: int(count) for kind, count in rows}
    return {kind: counts[kind] for kind in REACTION_KINDS if kind in counts}


async def react(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, kind: str, *, on: bool
) -> None:
    """Adds (`on`) or takes back a quick reaction; doing it twice changes nothing."""
    prono = await get_prono(session, member, prono_id)
    if prono.state in HIDDEN_STATES:
        raise AppError("invalid_state")
    if on:
        await session.execute(
            insert(Reaction)
            .values(prono_id=prono.id, membership_id=member.id, kind=kind, created_at=clock.now())
            .on_conflict_do_nothing()
        )
    else:
        await session.execute(
            delete(Reaction).where(
                Reaction.prono_id == prono.id,
                Reaction.membership_id == member.id,
                Reaction.kind == kind,
            )
        )
    await bus.publish(
        session,
        "reaction.changed",
        {"prono_id": str(prono.id), "reactions": await reaction_counts(session, prono.id)},
        topics=[f"prono:{prono.id}"],
    )


def may_edit(member: Membership, prono: Prono) -> bool:
    author = prono.created_by == member.id and _is_newsroom(member)
    return (author or member.role == "editor") and can_edit(prono.state, prono.bet_count)


async def edit_prono(
    session: AsyncSession, member: Membership, prono: Prono, changes: dict[str, Any]
) -> Prono:
    author = prono.created_by == member.id and _is_newsroom(member)
    if not (author or member.role == "editor"):
        raise AppError("forbidden")
    if not can_edit(prono.state, prono.bet_count):
        raise AppError("invalid_state")
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    fields = {name: getattr(prono, name) for name in EDITABLE_FIELDS} | {
        k: v for k, v in changes.items() if k in EDITABLE_FIELDS
    }
    if fields.get("open_ended"):
        fields["closes_at"] = None
    current = (
        await session.scalars(
            select(PronoOption.label)
            .where(PronoOption.prono_id == prono.id)
            .order_by(PronoOption.position)
        )
    ).all()
    options = changes["options"] if changes.get("options") is not None else list(current)
    if Kind(fields["kind"]) in (Kind.NUMBER, Kind.DATE):
        options = []
    await _check_links(session, org.id, fields["section_id"], fields.get("image_id"))
    labels = _validated(fields, options, org)
    for name, value in fields.items():
        setattr(prono, name, value)
    prono.question = prono.question.strip()
    if prono.state == State.SCHEDULED and not (prono.opens_at and prono.opens_at > clock.now()):
        prono.state = State.OPEN.value
    await _replace_options(session, prono, labels)
    await record_event(session, prono, "edited", member)
    await session.flush()
    await announce(
        session,
        prono,
        "prono.edited",
        {"prono": {"id": str(prono.id), "question": prono.question, "state": prono.state}},
        [f"org:{prono.org_id}", f"prono:{prono.id}"],
    )
    return prono


def _encode_cursor(prono: Prono) -> str:
    raw = f"{prono.created_at.isoformat()}|{prono.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_at, prono_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(created_at), uuid.UUID(prono_id)
    except (ValueError, UnicodeDecodeError) as error:
        raise AppError("validation_error", {"cursor": "invalid"}) from error


async def list_pronos(
    session: AsyncSession,
    member: Membership,
    *,
    states: list[str],
    section_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[Prono], str | None]:
    query = select(Prono).where(visible_to(member))
    if states:
        query = query.where(Prono.state.in_(states))
    if section_id:
        query = query.where(Prono.section_id == section_id)
    if cursor:
        created_at, prono_id = _decode_cursor(cursor)
        query = query.where(tuple_(Prono.created_at, Prono.id) < (created_at, prono_id))
    rows = (
        await session.scalars(
            query.order_by(Prono.created_at.desc(), Prono.id.desc()).limit(limit + 1)
        )
    ).all()
    page = list(rows[:limit])
    return page, _encode_cursor(page[-1]) if len(rows) > limit else None


# Read models


def format_number(value: Decimal, unit: str | None) -> str:
    text = format(value.normalize(), "f").replace(".", ",")
    return f"{text} {unit}" if unit else text


def answer_of(bet: Bet, prono: Prono, labels: dict[uuid.UUID, str]) -> str:
    if bet.option_id is not None:
        return labels.get(bet.option_id, "")
    if bet.number_value is not None:
        return format_number(bet.number_value, prono.number_unit)
    return bet.date_value.isoformat() if bet.date_value else ""


def bet_view(
    bet: Bet, prono: Prono, member: Membership, labels: dict[uuid.UUID, str]
) -> dict[str, Any]:
    return {
        "id": bet.id,
        "member": public_member(member),
        "option_id": bet.option_id,
        "number_value": bet.number_value,
        "date_value": bet.date_value,
        "answer": answer_of(bet, prono, labels),
        "stake": bet.stake,
        "rank": bet.rank,
        "placed_at": bet.placed_at,
        "superseded": bet.superseded_at is not None,
        "outcome": bet.outcome,
        "payout": bet.payout,
    }


async def summaries(session: AsyncSession, pronos: list[Prono]) -> list[dict[str, Any]]:
    """The list view of several pronos, with their section and author."""
    if not pronos:
        return []
    sections = {
        s.id: s
        for s in (
            await session.scalars(
                select(Section).where(Section.id.in_({p.section_id for p in pronos}))
            )
        ).all()
    }
    authors = {
        m.id: m
        for m in (
            await session.scalars(
                select(Membership).where(Membership.id.in_({p.created_by for p in pronos}))
            )
        ).all()
    }
    return [
        {
            "id": p.id,
            "number": p.number,
            "kind": p.kind,
            "question": p.question,
            "section": sections[p.section_id],
            "state": p.state,
            "base_gain": p.base_gain,
            "opens_at": p.opens_at,
            "closes_at": p.closes_at,
            "open_ended": p.open_ended,
            "result_expected_at": p.result_expected_at,
            "number_unit": p.number_unit,
            "link_url": p.link_url,
            "image_url": f"/api/orgs/{p.org_id}/uploads/{p.image_id}" if p.image_id else None,
            "bet_count": p.bet_count,
            "pot": p.pot,
            "relaunch_count": p.relaunch_count,
            "created_by": public_member(authors[p.created_by]),
        }
        for p in pronos
    ]


async def live_settlement(session: AsyncSession, prono_id: uuid.UUID) -> Settlement | None:
    """The settlement in force: the latest one, unless a later one reversed it."""
    return await session.scalar(
        select(Settlement)
        .where(Settlement.prono_id == prono_id, Settlement.reversed_by_id.is_(None))
        .order_by(Settlement.seq.desc())
        .limit(1)
    )


def result_label(prono: Prono, options: list[PronoOption]) -> str | None:
    """The designated result as the front page writes it."""
    if prono.result_number is not None:
        return format_number(prono.result_number, prono.number_unit)
    if prono.result_date is not None:
        return prono.result_date.isoformat()
    correct = [o.label for o in options if o.is_correct]
    return ", ".join(correct) or None


async def special_edition(
    session: AsyncSession,
    prono: Prono,
    options: list[PronoOption],
    members: dict[uuid.UUID, dict[str, Any]],
) -> dict[str, Any] | None:
    """The result as published: winners with what they got, and whether the pot was lost."""
    if prono.state not in (State.RESOLVED, State.CANCELLED):
        return None
    settlement = await live_settlement(session, prono.id)
    if settlement is None:
        return None
    rows = (
        await session.execute(
            select(LedgerEntry.bet_id, LedgerEntry.kind, func.sum(LedgerEntry.amount))
            .where(
                LedgerEntry.settlement_id == settlement.id,
                LedgerEntry.kind.in_([k.value for k in PAYOUT_KINDS]),
            )
            .group_by(LedgerEntry.bet_id, LedgerEntry.kind)
        )
    ).all()
    paid: dict[uuid.UUID | None, dict[str, int]] = {}
    for bet_id, kind, amount in rows:
        paid.setdefault(bet_id, {})[kind] = int(amount)
    winners = (
        await session.scalars(
            select(Bet).where(Bet.prono_id == prono.id, Bet.outcome == "won").order_by(Bet.rank)
        )
    ).all()
    settler = await session.get(Membership, settlement.created_by)
    assert settler is not None
    cancelled = settlement.kind == "cancellation"
    shared = any(LedgerKind.POT_SHARE.value in amounts for amounts in paid.values())
    return {
        "settlement_seq": settlement.seq,
        "kind": settlement.kind,
        "result": None if cancelled else result_label(prono, options),
        "settled_at": settlement.created_at,
        "settled_by": public_member(settler),
        "pot": prono.pot,
        "pot_lost": not cancelled and prono.pot > 0 and not shared,
        "winners": [
            {
                "member": members[bet.membership_id],
                "bet_id": bet.id,
                "stake": bet.stake,
                "payout": bet.payout,
                "base_gain": paid.get(bet.id, {}).get(LedgerKind.BASE_GAIN.value, 0),
                "early_bird": paid.get(bet.id, {}).get(LedgerKind.EARLY_BIRD.value, 0),
                "pot_share": paid.get(bet.id, {}).get(LedgerKind.POT_SHARE.value, 0),
            }
            for bet in winners
        ],
    }


def _pct(part: int, total: int) -> int:
    return round(part * 100 / total) if total else 0


def _shares(
    options: Sequence[PronoOption], active: Sequence[Bet]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Each answer with its share of the bets in force, and the split of the numbers or dates."""
    counts: dict[uuid.UUID, list[int]] = defaultdict(lambda: [0, 0])
    for bet in active:
        if bet.option_id is not None:
            counts[bet.option_id][0] += 1
            counts[bet.option_id][1] += bet.stake
    total = len(active)
    values = [
        (bet.number_value if bet.number_value is not None else bet.date_value, bet.stake)
        for bet in active
        if bet.number_value is not None or bet.date_value is not None
    ]
    buckets = [
        {**asdict(b), "share_pct": _pct(b.count, total)}
        for b in distribution(values)  # type: ignore[arg-type]
    ]
    option_rows = [
        {
            "id": o.id,
            "label": o.label,
            "is_correct": o.is_correct,
            "count": counts[o.id][0],
            "stake_total": counts[o.id][1],
            "share_pct": _pct(counts[o.id][0], total),
        }
        for o in options
    ]
    return option_rows, buckets


async def with_shares(session: AsyncSession, pronos: list[Prono]) -> list[dict[str, Any]]:
    """The list view of several pronos, each with the split of its answers (la une's gauges)."""
    ids = [p.id for p in pronos]
    options: dict[uuid.UUID, list[PronoOption]] = defaultdict(list)
    for option in (
        await session.scalars(
            select(PronoOption)
            .where(PronoOption.prono_id.in_(ids))
            .order_by(PronoOption.prono_id, PronoOption.position)
        )
    ).all():
        options[option.prono_id].append(option)
    active: dict[uuid.UUID, list[Bet]] = defaultdict(list)
    for bet in (
        await session.scalars(select(Bet).where(Bet.prono_id.in_(ids), Bet.superseded_at.is_(None)))
    ).all():
        active[bet.prono_id].append(bet)
    views = []
    for prono, summary in zip(pronos, await summaries(session, pronos), strict=True):
        option_rows, buckets = _shares(options[prono.id], active[prono.id])
        views.append({**summary, "options": option_rows, "distribution": buckets})
    return views


async def detail(session: AsyncSession, member: Membership, prono: Prono) -> dict[str, Any]:
    [summary] = await summaries(session, [prono])
    options = (
        await session.scalars(
            select(PronoOption)
            .where(PronoOption.prono_id == prono.id)
            .order_by(PronoOption.position)
        )
    ).all()
    labels = {o.id: o.label for o in options}
    rows = (
        await session.execute(
            select(Bet, Membership)
            .join(Membership, Membership.id == Bet.membership_id)
            .where(Bet.prono_id == prono.id)
            .order_by(Bet.rank)
        )
    ).all()
    active = [bet for bet, _ in rows if bet.superseded_at is None]
    option_rows, buckets = _shares(options, active)
    mine = next((bet for bet, m in rows if m.id == member.id and bet.superseded_at is None), None)
    members = {m.id: public_member(m) for _, m in rows}
    today = clock.now().astimezone(PARIS).date()
    mine_reacted = set(
        (
            await session.scalars(
                select(Reaction.kind).where(
                    Reaction.prono_id == prono.id, Reaction.membership_id == member.id
                )
            )
        ).all()
    )
    events = (
        await session.scalars(
            select(PronoEvent)
            .where(PronoEvent.prono_id == prono.id)
            .order_by(PronoEvent.created_at)
        )
    ).all()
    return {
        **summary,
        "options": option_rows,
        "distribution": buckets,
        "bets": [bet_view(bet, prono, m, labels) for bet, m in rows],
        "my_bet": bet_view(mine, prono, member, labels) if mine else None,
        "can_rebet": bool(
            prono.open_ended
            and prono.state == State.OPEN
            and mine is not None
            and mine.date_value is not None
            and mine.date_value < today
        ),
        "can_edit": may_edit(member, prono),
        "reactions": await reaction_counts(session, prono.id),
        "my_reactions": [kind for kind in REACTION_KINDS if kind in mine_reacted],
        "rejected_reason": prono.rejected_reason,
        # The member's own reports on this prono, and what became of them.
        "my_reports": (
            await session.scalars(
                select(Report)
                .where(Report.prono_id == prono.id, Report.reporter_membership_id == member.id)
                .order_by(Report.created_at)
            )
        ).all(),
        "events": [{"kind": e.kind, "at": e.created_at, "data": e.data} for e in events],
        "special_edition": await special_edition(session, prono, list(options), members),
    }

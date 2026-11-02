"""Pronos: publishing, editing, listing, the detail screen and state changes."""

import base64
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from sybille import clock
from sybille.api.errors import AppError
from sybille.db.models import (
    Bet,
    LedgerEntry,
    Membership,
    Organisation,
    Prono,
    PronoEvent,
    PronoOption,
    Section,
    Settlement,
    Upload,
)
from sybille.domain.betting import Kind, PronoDraft, ValidationFailed, distribution, validate_prono
from sybille.domain.ledger import LedgerKind
from sybille.domain.lifecycle import State, can_edit
from sybille.domain.permissions import Action, can
from sybille.domain.seasons import PARIS
from sybille.realtime import bus
from sybille.services.orgs import public_member

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


async def set_state(
    session: AsyncSession,
    prono: Prono,
    state: State,
    event: str,
    actor: Membership | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Moves a prono to a new state, keeps its history and tells the screens."""
    prono.state = state.value
    await record_event(session, prono, event, actor, data)
    await session.flush()
    await bus.publish(
        session,
        "prono.state_changed",
        {
            "prono_id": str(prono.id),
            "state": prono.state,
            "closes_at": prono.closes_at.isoformat() if prono.closes_at else None,
            "relaunch_count": prono.relaunch_count,
        },
        topics=[f"org:{prono.org_id}", f"prono:{prono.id}"],
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
    if not can(member.role, Action.PUBLISH_PRONO):
        # Readers' proposals arrive with US5.
        raise AppError("forbidden")
    org = await session.get(Organisation, member.org_id)
    assert org is not None
    await _check_links(session, org.id, fields["section_id"], fields.get("image_id"))
    labels = _validated(fields, fields.get("options") or [], org)
    now = clock.now()
    opens_at = fields.get("opens_at")
    prono = Prono(
        org_id=org.id,
        **{name: fields.get(name) for name in EDITABLE_FIELDS},
        state=(State.SCHEDULED if opens_at and opens_at > now else State.OPEN).value,
        created_by=member.id,
    )
    prono.question = prono.question.strip()
    prono.open_ended = bool(prono.open_ended)
    session.add(prono)
    await session.flush()
    await _replace_options(session, prono, labels)
    await record_event(session, prono, "created", member)
    await session.flush()
    await bus.publish(
        session,
        "prono.created",
        {"prono": {"id": str(prono.id), "question": prono.question, "state": prono.state}},
        topics=[f"org:{org.id}"],
    )
    return prono


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
    await bus.publish(
        session,
        "prono.edited",
        {"prono": {"id": str(prono.id), "question": prono.question, "state": prono.state}},
        topics=[f"org:{prono.org_id}", f"prono:{prono.id}"],
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
    cancelled = settlement.kind == "cancellation"
    shared = any(LedgerKind.POT_SHARE.value in amounts for amounts in paid.values())
    return {
        "settlement_seq": settlement.seq,
        "kind": settlement.kind,
        "result": None if cancelled else result_label(prono, options),
        "settled_at": settlement.created_at,
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
    mine = next((bet for bet, m in rows if m.id == member.id and bet.superseded_at is None), None)
    members = {m.id: public_member(m) for _, m in rows}
    today = clock.now().astimezone(PARIS).date()
    events = (
        await session.scalars(
            select(PronoEvent)
            .where(PronoEvent.prono_id == prono.id)
            .order_by(PronoEvent.created_at)
        )
    ).all()
    return {
        **summary,
        "options": [
            {
                "id": o.id,
                "label": o.label,
                "is_correct": o.is_correct,
                "count": counts[o.id][0],
                "stake_total": counts[o.id][1],
                "share_pct": _pct(counts[o.id][0], total),
            }
            for o in options
        ],
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
        "reactions": {},
        "my_reactions": [],
        "events": [{"kind": e.kind, "at": e.created_at, "data": e.data} for e in events],
        "special_edition": await special_edition(session, prono, list(options), members),
    }

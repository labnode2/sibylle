"""Everything Sibylle keeps about an account, as one file (US11, principle I): the account, then
each newsroom with its membership, bets, laurels, coins, collection, trophies and reports."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.db.models import (
    Account,
    Bet,
    CatalogItem,
    CoinEntry,
    LedgerEntry,
    Membership,
    Organisation,
    OwnedItem,
    Prono,
    PronoOption,
    Report,
    Season,
    Trophy,
)
from sibylle.services import notifications
from sibylle.services.pronos import answer_of


async def export(session: AsyncSession, account: Account) -> dict[str, Any]:
    rows = await session.execute(
        select(Organisation, Membership)
        .join(Membership, Membership.org_id == Organisation.id)
        .where(Membership.account_id == account.id)
        .order_by(Membership.joined_at)
    )
    return {
        "exported_at": clock.now(),
        "account": {
            "email": account.email,
            "first_name": account.first_name,
            "last_name": account.last_name,
            "email_verified_at": account.email_verified_at,
            "locale": account.locale,
            "theme": account.theme,
            "reduce_motion": account.reduce_motion,
            "created_at": account.created_at,
        },
        "newsrooms": [await _newsroom(session, org, member) for org, member in rows.all()],
        "notification_prefs": [
            {"type": type, "channel": channel, "enabled": enabled}
            for type, channel, enabled in await notifications.prefs(session, account.id)
        ],
        # The endpoint stays out: it is the device's address at its push service.
        "push_devices": [
            {
                "user_agent": device.user_agent,
                "created_at": device.created_at,
                "last_success_at": device.last_success_at,
            }
            for device in await notifications.devices(session, account.id)
        ],
    }


async def _newsroom(session: AsyncSession, org: Organisation, member: Membership) -> dict[str, Any]:
    return {
        "newsroom": {"id": org.id, "title": org.title},
        "membership": {
            "pseudo": member.pseudo,
            "role": member.role,
            "status": member.status,
            "avatar": member.avatar,
            "joined_at": member.joined_at,
            "left_at": member.left_at,
            "balance": member.balance,
            "season_score": member.season_score,
            "coins": member.coins,
        },
        "bets": await _bets(session, member.id),
        "laurels": await _laurels(session, member.id),
        "coins": [
            {
                "kind": entry.kind,
                "amount": entry.amount,
                "week_start": entry.week_start,
                "gold": entry.gold,
                "item_key": entry.item_key,
                "created_at": entry.created_at,
            }
            for entry in await session.scalars(
                select(CoinEntry).where(CoinEntry.membership_id == member.id).order_by(CoinEntry.id)
            )
        ],
        "collection": [
            {"key": item.key, "kind": item.kind, "source": owned.source, "at": owned.acquired_at}
            for owned, item in await session.execute(
                select(OwnedItem, CatalogItem)
                .join(CatalogItem, CatalogItem.id == OwnedItem.item_id)
                .where(OwnedItem.membership_id == member.id)
                .order_by(OwnedItem.acquired_at)
            )
        ],
        "trophies": [
            {
                "season": f"{season.name} {season.year}",
                "score": trophy.score,
                "rank": trophy.rank,
                "podium": trophy.podium,
            }
            for trophy, season in await session.execute(
                select(Trophy, Season)
                .join(Season, Season.id == Trophy.season_id)
                .where(Trophy.membership_id == member.id)
                .order_by(Season.starts_at)
            )
        ],
        "reports": [
            {
                "prono_id": report.prono_id,
                "kind": report.kind,
                "message": report.message,
                "state": report.state,
                "resolution_note": report.resolution_note,
                "created_at": report.created_at,
            }
            for report in await session.scalars(
                select(Report)
                .where(Report.reporter_membership_id == member.id)
                .order_by(Report.created_at)
            )
        ],
    }


async def _bets(session: AsyncSession, member_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Bet, Prono)
            .join(Prono, Prono.id == Bet.prono_id)
            .where(Bet.membership_id == member_id)
            .order_by(Bet.placed_at)
        )
    ).all()
    labels = {
        option_id: label
        for option_id, label in await session.execute(
            select(PronoOption.id, PronoOption.label).where(
                PronoOption.prono_id.in_({prono.id for _, prono in rows})
            )
        )
    }
    return [
        {
            "prono_id": prono.id,
            "question": prono.question,
            "answer": answer_of(bet, prono, labels),
            "stake": bet.stake,
            "placed_at": bet.placed_at,
            "replaced_at": bet.superseded_at,
            "outcome": bet.outcome,
            "payout": bet.payout,
        }
        for bet, prono in rows
    ]


async def _laurels(session: AsyncSession, member_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(LedgerEntry, Prono.question)
        .outerjoin(Prono, Prono.id == LedgerEntry.prono_id)
        .where(LedgerEntry.membership_id == member_id)
        .order_by(LedgerEntry.id)
    )
    return [
        {
            "kind": entry.kind,
            "amount": entry.amount,
            "score_delta": entry.score_delta,
            "reason": entry.reason,
            "question": question,
            "created_at": entry.created_at,
        }
        for entry, question in rows
    ]

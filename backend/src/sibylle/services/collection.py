"""The collection: buying colours, frames and balls with coins, secret codes, and the press card
that shows a member's statistics, trophies and collection."""

import uuid
from typing import Any

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle.api.errors import AppError
from sibylle.db.models import (
    Bet,
    CatalogItem,
    Membership,
    OwnedItem,
    Season,
    SecretCode,
    SecretCodeRedemption,
    Trophy,
)
from sibylle.domain.coins import CoinKind
from sibylle.domain.leaderboard import Metric, Period
from sibylle.services import coins, deals, leaderboard, ledger, streaks
from sibylle.services.security import token_hash

_KIND_ORDER = {"color": 0, "frame": 1, "ball": 2}


def _order(item: CatalogItem) -> tuple[int, int, str]:
    return _KIND_ORDER[item.kind], int(item.data.get("index", 0)), item.key


async def _owned(session: AsyncSession, member: Membership) -> list[tuple[OwnedItem, CatalogItem]]:
    rows = await session.execute(
        select(OwnedItem, CatalogItem)
        .join(CatalogItem, CatalogItem.id == OwnedItem.item_id)
        .where(OwnedItem.membership_id == member.id)
        .order_by(OwnedItem.acquired_at, OwnedItem.id)
    )
    return [(owned, item) for owned, item in rows]


async def catalog(session: AsyncSession, member: Membership) -> list[tuple[CatalogItem, bool]]:
    """What is on sale, and what the member owns (a secret code's surprise shows once owned)."""
    owned_ids = select(OwnedItem.item_id).where(OwnedItem.membership_id == member.id)
    items = (
        await session.scalars(
            select(CatalogItem).where(
                CatalogItem.active,
                or_(CatalogItem.price.is_not(None), CatalogItem.id.in_(owned_ids)),
            )
        )
    ).all()
    mine = {item.id for _, item in await _owned(session, member)}
    return [(item, item.id in mine) for item in sorted(items, key=_order)]


async def unlocked_colors(session: AsyncSession, member: Membership) -> set[int]:
    """Palette indices beyond the base palette that the member owns."""
    data = await session.scalars(
        select(CatalogItem.data)
        .join(OwnedItem, OwnedItem.item_id == CatalogItem.id)
        .where(OwnedItem.membership_id == member.id, CatalogItem.kind == "color")
    )
    return {int(d["index"]) for d in data}


async def owned_frame(session: AsyncSession, member: Membership, item_id: uuid.UUID) -> CatalogItem:
    item = await session.scalar(
        select(CatalogItem)
        .join(OwnedItem, OwnedItem.item_id == CatalogItem.id)
        .where(
            OwnedItem.membership_id == member.id,
            CatalogItem.id == item_id,
            CatalogItem.kind == "frame",
        )
    )
    if item is None:
        raise AppError("validation_error", {"avatar_frame_item_id": "not_owned"})
    return item


async def buy(
    session: AsyncSession,
    member: Membership,
    item_id: uuid.UUID,
    *,
    shown_price: int | None = None,
) -> tuple[OwnedItem, CatalogItem, int]:
    """Pays this week's price in coins (laurels and score stay) and adds the item to the
    collection. `shown_price`, the price the screen showed, must still be this week's."""
    item = await session.scalar(
        select(CatalogItem).where(
            CatalogItem.id == item_id, CatalogItem.active, CatalogItem.price.is_not(None)
        )
    )
    if item is None:
        raise AppError("not_found")
    price = deals.price_of(item, await deals.this_week(session, member.org_id))
    if price is None:
        raise AppError("not_found")
    if shown_price is not None and shown_price != price:
        raise AppError("price_changed")
    member = await ledger.lock_member(session, member.id)
    already = await session.scalar(
        select(OwnedItem.id).where(
            OwnedItem.membership_id == member.id, OwnedItem.item_id == item.id
        )
    )
    if already is not None:
        raise AppError("invalid_state")
    if member.coins < price:
        raise AppError("insufficient_coins")
    await coins.append(session, member.id, CoinKind.PURCHASE, -price, item_key=item.key)
    owned = OwnedItem(membership_id=member.id, item_id=item.id, source="purchase")
    session.add(owned)
    await session.flush()
    return owned, item, member.coins


def _fingerprint(code: str) -> str:
    """Codes are typed loosely: spaces around and letter case do not count."""
    return token_hash(code.strip().upper())


async def add_secret_code(session: AsyncSession, code: str, item_key: str) -> SecretCode:
    item = await session.scalar(select(CatalogItem).where(CatalogItem.key == item_key))
    if item is None:
        raise LookupError(f"no catalog item {item_key!r}")
    secret = SecretCode(code_hash=_fingerprint(code), item_id=item.id)
    session.add(secret)
    await session.flush()
    return secret


async def redeem(session: AsyncSession, member: Membership, code: str) -> CatalogItem:
    """Unlocks a code's surprise, once per member."""
    secret = await session.scalar(
        select(SecretCode).where(SecretCode.code_hash == _fingerprint(code), SecretCode.active)
    )
    if secret is None:
        raise AppError("validation_error", {"code": "unknown"})
    item = await session.get(CatalogItem, secret.item_id)
    assert item is not None
    used = await session.execute(
        insert(SecretCodeRedemption)
        .values(id=uuid.uuid4(), secret_code_id=secret.id, membership_id=member.id)
        .on_conflict_do_nothing()
        .returning(SecretCodeRedemption.id)
    )
    if used.scalar() is None:
        raise AppError("invalid_state")
    owned = await session.execute(
        insert(OwnedItem)
        .values(id=uuid.uuid4(), membership_id=member.id, item_id=item.id, source="secret_code")
        .on_conflict_do_nothing()
        .returning(OwnedItem.id)
    )
    if owned.scalar() is None:
        raise AppError("invalid_state")
    return item


# The press card


async def _stats(session: AsyncSession, member: Membership) -> dict[str, Any]:
    active = Bet.superseded_at.is_(None)
    played, settled, wins = (
        await session.execute(
            select(
                func.count(func.distinct(Bet.prono_id)),
                func.count().filter(active, Bet.outcome.in_(("won", "lost"))),
                func.count().filter(active, Bet.outcome == "won"),
            ).where(Bet.membership_id == member.id)
        )
    ).one()
    laurels = await leaderboard.values(session, member.org_id, Metric.LAURELS, Period.ALL_TIME)
    chain = await streaks.of_member(session, member)
    return {
        "laurels": laurels.get(member.id, 0),
        "pronos_played": int(played),
        "settled": int(settled),
        "wins": int(wins),
        "success_rate": round(100 * wins / settled) if settled else None,
        "streak": chain.current,
        "best_streak": chain.best,
    }


async def _card_number(session: AsyncSession, member: Membership) -> str:
    """The member's rank of arrival in the newsroom, on four digits."""
    before = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.org_id == member.org_id,
            tuple_(Membership.joined_at, Membership.id) < (member.joined_at, member.id),
        )
    )
    return f"{int(before or 0) + 1:04d}"


# The press card shows at most three things the member chose: objects of the collection
# (bought or unlocked) and engraved trophies.
SHOWCASE_MAX = 3


def _trophy_view(trophy: Trophy, season: Season) -> dict[str, Any]:
    return {
        "id": trophy.id,
        "season": {"year": season.year, "name": season.name},
        "score": trophy.score,
        "rank": trophy.rank,
        "podium": trophy.podium,
    }


async def checked_showcase(
    session: AsyncSession, member: Membership, refs: list[tuple[str, uuid.UUID]]
) -> list[dict[str, str]]:
    """The member's choice, kept only if every object is theirs and every trophy theirs too."""
    if len(refs) > SHOWCASE_MAX:
        raise AppError("validation_error", {"showcase": "too_many"})
    if len(set(refs)) != len(refs):
        raise AppError("validation_error", {"showcase": "duplicate"})
    items = {ref for kind, ref in refs if kind == "item"}
    trophies = {ref for kind, ref in refs if kind == "trophy"}
    owned = set(
        (
            await session.scalars(
                select(OwnedItem.item_id).where(
                    OwnedItem.membership_id == member.id, OwnedItem.item_id.in_(items)
                )
            )
        ).all()
    )
    won = set(
        (
            await session.scalars(
                select(Trophy.id).where(Trophy.membership_id == member.id, Trophy.id.in_(trophies))
            )
        ).all()
    )
    if items - owned or trophies - won:
        raise AppError("validation_error", {"showcase": "not_owned"})
    return [{"kind": kind, "id": str(ref)} for kind, ref in refs]


async def _showcase(session: AsyncSession, member: Membership) -> list[dict[str, Any]]:
    """The chosen things, in their order; one that is no longer the member's is left out."""
    refs = [(entry["kind"], uuid.UUID(entry["id"])) for entry in member.showcase or []]
    items = {
        item.id: item
        for item in (
            await session.scalars(
                select(CatalogItem)
                .join(OwnedItem, OwnedItem.item_id == CatalogItem.id)
                .where(
                    OwnedItem.membership_id == member.id,
                    CatalogItem.id.in_([ref for kind, ref in refs if kind == "item"]),
                )
            )
        ).all()
    }
    trophies = {
        trophy.id: _trophy_view(trophy, season)
        for trophy, season in await session.execute(
            select(Trophy, Season)
            .join(Season, Season.id == Trophy.season_id)
            .where(
                Trophy.membership_id == member.id,
                Trophy.id.in_([ref for kind, ref in refs if kind == "trophy"]),
            )
        )
    }
    shown: list[dict[str, Any]] = []
    for kind, ref in refs:
        if kind == "item" and ref in items:
            shown.append({"kind": "item", "item": items[ref]})
        elif kind == "trophy" and ref in trophies:
            shown.append({"kind": "trophy", "trophy": trophies[ref]})
    return shown


async def press_card(session: AsyncSession, member: Membership) -> dict[str, Any]:
    trophies = await session.execute(
        select(Trophy, Season)
        .join(Season, Season.id == Trophy.season_id)
        .where(Trophy.membership_id == member.id)
        .order_by(Season.starts_at)
    )
    return {
        "member": member,
        "card_number": await _card_number(session, member),
        "stats": await _stats(session, member),
        "trophies": [_trophy_view(trophy, season) for trophy, season in trophies],
        "collection": await _owned(session, member),
        "showcase": await _showcase(session, member),
    }

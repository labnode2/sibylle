import asyncio
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update
from tests.conftest import MakeOrg, MakePerson, Person
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url

from sybille import clock
from sybille.db.models import LedgerEntry, Membership, Season, SeasonClosure, Trophy
from sybille.db.session import transaction
from sybille.services.ledger import check_caches
from sybille.worker.jobs import advance_pronos, close_finished_seasons

pytestmark = pytest.mark.integration

PARIS = ZoneInfo("Europe/Paris")
WINTER_2026 = datetime(2026, 12, 21, 0, 0, 30, tzinfo=PARIS)
SPRING_2027 = datetime(2027, 3, 21, 0, 0, 30, tzinfo=PARIS)


async def resolve(
    journalist: Person, org_id: uuid.UUID, prono: dict[str, object], answer: str
) -> None:
    response = await journalist.client.post(
        url(org_id, str(prono["id"]), "resolve"),
        json={"correct_option_ids": [option(prono, answer)]},  # type: ignore[arg-type]
    )
    assert response.status_code == 200, response.text


async def trophies(season: tuple[int, str]) -> dict[str, tuple[int, int, bool]]:
    """Pseudo → (score, rank, podium) for one season."""
    year, name = season
    async with transaction() as session:
        rows = await session.execute(
            select(Membership.pseudo, Trophy.score, Trophy.rank, Trophy.podium)
            .join(Membership, Membership.id == Trophy.membership_id)
            .join(Season, Season.id == Trophy.season_id)
            .where(Season.year == year, Season.name == name)
        )
        return {pseudo: (score, rank, podium) for pseudo, score, rank, podium in rows}


async def counters(org_id: uuid.UUID) -> dict[str, tuple[int, int]]:
    """Pseudo → (balance, season score)."""
    async with transaction() as session:
        rows = await session.execute(
            select(Membership.pseudo, Membership.balance, Membership.season_score).where(
                Membership.org_id == org_id
            )
        )
        return {pseudo: (balance, score) for pseudo, balance, score in rows}


async def count(model: type[LedgerEntry] | type[Trophy] | type[SeasonClosure]) -> int:
    async with transaction() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def test_the_end_of_the_season(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami, leo, manon, paul = [
        await person(org, "reader", n) for n in ("Cami", "Léo", "Manon", "Paul")
    ]
    await person(org, "reader", "Zoé")  # never bets: no trophy

    prono = await publish(hugo.client, str(org.id))
    org_id = str(org.id)
    await place(cami.client, org_id, prono["id"], option_id=option(prono, "Nice"), stake=10)
    await place(leo.client, org_id, prono["id"], option_id=option(prono, "Monaco"), stake=0)
    await place(manon.client, org_id, prono["id"], option_id=option(prono, "Monaco"), stake=10)
    await place(paul.client, org_id, prono["id"], option_id=option(prono, "Monaco"), stake=20)
    fake_clock.advance(timedelta(days=4))
    await advance_pronos()
    await resolve(hugo, org.id, prono, "Nice")
    # Paul leaves before the end of the season: his trophy and his reset still come.
    async with transaction() as session:
        await session.execute(
            update(Membership).where(Membership.id == paul.member.id).values(status="left")
        )

    assert await counters(org.id) == {
        "Hugo": (100, 0),
        "Cami": (150, 50),  # 100 − 10 + 20 base + the pot of 40
        "Léo": (100, 0),
        "Manon": (90, -10),
        "Paul": (80, -20),
        "Zoé": (100, 0),
    }

    # Nothing to close before the end of autumn.
    fake_clock.set(datetime(2026, 12, 20, 23, 59, tzinfo=PARIS))
    assert await close_finished_seasons() == 0

    fake_clock.set(WINTER_2026)
    assert await close_finished_seasons() == 1
    assert await trophies((2026, "autumn")) == {
        "Cami": (50, 1, True),
        "Léo": (0, 2, True),
        "Manon": (-10, 3, True),
        "Paul": (-20, 4, False),
    }
    assert await counters(org.id) == {
        name: (100, 0) for name in ("Hugo", "Cami", "Léo", "Manon", "Paul", "Zoé")
    }
    async with transaction() as session:
        assert await check_caches(session, org.id) == []
        resets = (
            await session.scalars(
                select(LedgerEntry.amount)
                .where(LedgerEntry.kind == "season_reset")
                .order_by(LedgerEntry.amount)
            )
        ).all()
    assert list(resets) == [-50, 10, 20]  # Cami, Manon, Paul; the others were already at 100

    # The newsroom was created in November: earlier seasons are not closed for it.
    async with transaction() as session:
        closed = (
            await session.execute(
                select(Season.year, Season.name)
                .join(SeasonClosure, SeasonClosure.season_id == Season.id)
                .where(SeasonClosure.org_id == org.id)
            )
        ).all()
    assert [tuple(row) for row in closed] == [(2026, "autumn")]

    # A second run, or two at once after a restart, pays nothing twice.
    entries, closures = await count(LedgerEntry), await count(SeasonClosure)
    assert await asyncio.gather(close_finished_seasons(), close_finished_seasons()) == [0, 0]
    assert (await count(LedgerEntry), await count(SeasonClosure)) == (entries, closures)
    assert await count(Trophy) == 4


async def test_two_runs_at_once_close_the_season_once(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)

    fake_clock.set(WINTER_2026)
    assert sorted(await asyncio.gather(close_finished_seasons(), close_finished_seasons())) == [
        0,
        1,
    ]
    assert await count(Trophy) == 1
    assert await count(SeasonClosure) == 1
    assert set((await counters(org.id)).values()) == {(100, 0)}


async def test_a_prono_staked_in_autumn_and_settled_in_winter_counts_in_winter(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(datetime(2026, 12, 19, 12, tzinfo=PARIS))
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(
        hugo.client,
        str(org.id),
        closes_at=datetime(2026, 12, 23, 12, tzinfo=PARIS).isoformat(),
    )
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await place(leo.client, str(org.id), prono["id"], option_id=option(prono, "Monaco"), stake=10)

    # Autumn ends with both stakes still in the pot: nothing scored, both on the podium at 0.
    fake_clock.set(WINTER_2026)
    assert await close_finished_seasons() == 1
    assert await trophies((2026, "autumn")) == {"Cami": (0, 1, True), "Léo": (0, 1, True)}

    fake_clock.set(datetime(2026, 12, 24, 12, tzinfo=PARIS))
    await advance_pronos()
    await resolve(hugo, org.id, prono, "Nice")
    assert (await counters(org.id))["Cami"] == (100 + 20 + 20, 30)

    # Nobody bets in winter, yet the winter scores are engraved.
    fake_clock.set(SPRING_2027)
    assert await close_finished_seasons() == 1
    assert await trophies((2026, "winter")) == {"Cami": (30, 1, True), "Léo": (-10, 2, True)}
    async with transaction() as session:
        assert await check_caches(session, org.id) == []


async def test_scores_moved_after_midnight_stay_in_the_new_season(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    """A prono settled between the end of the season and the closure belongs to the new season:
    the trophy engraves the old season only, and the new season keeps its score."""
    fake_clock.set(datetime(2026, 12, 15, 12, tzinfo=PARIS))
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    first = await publish(hugo.client, str(org.id))
    second = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), first["id"], option_id=option(first, "Nice"), stake=0)
    await place(cami.client, str(org.id), second["id"], option_id=option(second, "Nice"), stake=0)
    fake_clock.set(datetime(2026, 12, 19, 12, tzinfo=PARIS))
    await advance_pronos()
    await resolve(hugo, org.id, first, "Nice")

    # The worker was down at midnight; the second prono is settled before the closure runs.
    fake_clock.set(WINTER_2026)
    await resolve(hugo, org.id, second, "Nice")
    assert (await counters(org.id))["Cami"] == (140, 40)
    assert await close_finished_seasons() == 1
    assert await trophies((2026, "autumn")) == {"Cami": (20, 1, True)}
    assert (await counters(org.id))["Cami"] == (100, 20)
    async with transaction() as session:
        assert await check_caches(session, org.id) == []

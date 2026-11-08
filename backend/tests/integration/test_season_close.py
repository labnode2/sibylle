import asyncio
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update
from tests.conftest import MakeMember, MakeOrg, MakePerson, Person
from tests.contract.helpers import waiting_on_a_lock
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url

from sibylle import clock
from sibylle.db.models import LedgerEntry, Membership, Season, SeasonClosure, Trophy
from sibylle.db.session import transaction
from sibylle.domain.ledger import adjustment
from sibylle.services import ledger
from sibylle.services.ledger import check_caches
from sibylle.worker.jobs import advance_pronos, close_finished_seasons

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
    """Pseudo → (gold laurels engraved, rank, podium) for one season."""
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
    # The gold laurels, the starting balance included.
    assert await trophies((2026, "autumn")) == {
        "Cami": (150, 1, True),
        "Léo": (100, 2, True),
        "Manon": (90, 3, True),
        "Paul": (80, 4, False),
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
    fake_clock.advance(timedelta(days=4))
    await advance_pronos()
    await resolve(hugo, org.id, prono, "Nice")

    fake_clock.set(WINTER_2026)
    assert sorted(await asyncio.gather(close_finished_seasons(), close_finished_seasons())) == [
        0,
        1,
    ]
    assert await count(Trophy) == 1
    assert await count(SeasonClosure) == 1
    assert set((await counters(org.id)).values()) == {(100, 0)}


async def test_the_season_waits_for_the_results_of_its_bets(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    """A bet of the season still waiting for its result holds the closure back. Once settled, it
    counts in the season it was placed in; what is played in winter meanwhile stays out of the
    trophy and out of the reset."""
    fake_clock.set(datetime(2026, 12, 19, 12, tzinfo=PARIS))
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    autumn = await publish(
        hugo.client,
        str(org.id),
        closes_at=datetime(2026, 12, 23, 12, tzinfo=PARIS).isoformat(),
    )
    await place(cami.client, str(org.id), autumn["id"], option_id=option(autumn, "Nice"), stake=10)
    await place(leo.client, str(org.id), autumn["id"], option_id=option(autumn, "Monaco"), stake=10)

    fake_clock.set(WINTER_2026)
    assert await close_finished_seasons() == 0
    # Meanwhile, in winter, Cami stakes 5 on a new prono and receives 7 laurels.
    winter = await publish(
        hugo.client,
        str(org.id),
        closes_at=datetime(2027, 1, 10, 12, tzinfo=PARIS).isoformat(),
    )
    await place(cami.client, str(org.id), winter["id"], option_id=option(winter, "Nul"), stake=5)
    async with transaction() as session:
        await ledger.append(session, cami.member.id, adjustment(7), reason="Cadeau")

    fake_clock.set(datetime(2026, 12, 24, 12, tzinfo=PARIS))
    await advance_pronos()
    await resolve(hugo, org.id, autumn, "Nice")
    assert (await counters(org.id))["Cami"][0] == 100 - 10 + 20 + 20 - 5 + 7
    assert await close_finished_seasons() == 1
    assert await trophies((2026, "autumn")) == {"Cami": (130, 1, True), "Léo": (90, 2, True)}
    # Everyone back to 100 gold laurels, plus what winter brought: Cami's 5 are still in play.
    balances = {name: balance for name, (balance, _) in (await counters(org.id)).items()}
    assert balances == {"Hugo": 100, "Cami": 100 - 5 + 7, "Léo": 100}
    async with transaction() as session:
        assert await check_caches(session, org.id) == []


async def test_an_open_ended_prono_does_not_hold_the_season_back(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    """Its stake, still in play, is engraved with the gold laurels and stays in play; the
    result, when it comes, goes to the season then open."""
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(
        hugo.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    day = (clock.now() + timedelta(days=60)).date().isoformat()
    await place(cami.client, str(org.id), prono["id"], date_value=day, stake=10)

    fake_clock.set(WINTER_2026)
    assert await close_finished_seasons() == 1
    assert await trophies((2026, "autumn")) == {"Cami": (100, 1, True)}
    assert (await counters(org.id))["Cami"] == (90, 0)

    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"result_date": day}
    )
    assert resolved.status_code == 200, resolved.text
    assert (await counters(org.id))["Cami"] == (90 + 20 + 10, 20)
    async with transaction() as session:
        assert await check_caches(session, org.id) == []


async def test_a_season_held_back_holds_back_the_next_ones(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)

    # Spring: autumn still waits for its result, and winter waits behind it.
    fake_clock.set(SPRING_2027)
    assert await close_finished_seasons() == 0
    await advance_pronos()
    await resolve(hugo, org.id, prono, "Nice")
    assert await close_finished_seasons() == 2
    async with transaction() as session:
        closed = (
            await session.execute(
                select(Season.year, Season.name)
                .join(SeasonClosure, SeasonClosure.season_id == Season.id)
                .where(SeasonClosure.org_id == org.id)
                .order_by(Season.starts_at)
            )
        ).all()
        assert await check_caches(session, org.id) == []
    assert [tuple(row) for row in closed] == [(2026, "autumn"), (2026, "winter")]
    assert set((await counters(org.id)).values()) == {(100, 0)}


async def test_a_settlement_at_the_moment_of_closing_does_not_deadlock(
    make_org: MakeOrg, make_member: MakeMember, fake_clock: clock.FakeClock
) -> None:
    """A settlement locks its members in id order. The closure, which locks the whole newsroom,
    takes the same order, so it waits for the settlement instead of deadlocking with it."""
    org = await make_org()
    first, second, third = sorted([(await make_member(org)).id for _ in range(3)])
    # Names in the opposite order to the ids: the order the closure used to lock in.
    async with transaction() as session:
        for member_id, pseudo in ((first, "Zoé"), (second, "Manon"), (third, "Cami")):
            await session.execute(
                update(Membership).where(Membership.id == member_id).values(pseudo=pseudo)
            )

    fake_clock.set(WINTER_2026)
    async with transaction() as settling:
        await settling.execute(
            select(Membership.id).where(Membership.id == first).with_for_update()
        )
        closing = asyncio.create_task(close_finished_seasons(org.id))
        await waiting_on_a_lock(closing)
        await settling.execute(
            select(Membership.id)
            .where(Membership.id.in_([second, third]))
            .order_by(Membership.id)
            .with_for_update()
        )
    assert await closing == 1

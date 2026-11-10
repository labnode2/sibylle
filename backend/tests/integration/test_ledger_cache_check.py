"""The worker's nightly check that each member's caches match the ledger (T146): the balance
and the season score against the laurels ledger, the coins against the coin entries."""

import logging
from datetime import timedelta

import pytest
from sqlalchemy import text
from tests.conftest import MakeMember, MakeOrg

from sibylle import clock
from sibylle.db.session import transaction
from sibylle.domain import ledger as effects
from sibylle.services import coins, ledger
from sibylle.worker.jobs import REGISTRY, check_ledger_caches

pytestmark = pytest.mark.integration

LOGGER = "sibylle.worker.jobs"


def _drifts(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.ERROR]


def test_the_check_runs_every_night() -> None:
    assert REGISTRY["check_ledger_caches"].cron == {"hour": 3, "minute": 40}


async def test_consistent_caches_log_nothing(
    make_org: MakeOrg,
    make_member: MakeMember,
    fake_clock: clock.FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    org = await make_org()
    other = await make_org("Autre rédaction")
    member = await make_member(org)
    await make_member(other)
    async with transaction() as session:
        await ledger.append(session, member.id, effects.stake(10))
        await ledger.append(session, member.id, effects.pot_share(40, stake=10))
        await coins.append(session, member.id, coins.CoinKind.PURCHASE, 0)
    fake_clock.advance(timedelta(days=1))

    with caplog.at_level(logging.ERROR, logger=LOGGER):
        assert await check_ledger_caches() == 0
    assert _drifts(caplog) == []


@pytest.mark.parametrize(
    ("column", "message", "fields"),
    [
        (
            "balance",
            "laurels cache differs from the ledger",
            {"balance": 999, "ledger_balance": 100, "season_score": 0, "ledger_season_score": 0},
        ),
        (
            "season_score",
            "laurels cache differs from the ledger",
            {"balance": 100, "ledger_balance": 100, "season_score": 999, "ledger_season_score": 0},
        ),
        (
            "coins",
            "coins cache differs from the coin entries",
            {"coins": 999, "ledger_coins": 0},
        ),
    ],
)
async def test_each_kind_of_mismatch_is_logged(
    make_org: MakeOrg,
    make_member: MakeMember,
    caplog: pytest.LogCaptureFixture,
    column: str,
    message: str,
    fields: dict[str, int],
) -> None:
    org = await make_org()
    member = await make_member(org)
    await make_member(org)
    async with transaction() as session:
        await session.execute(
            text(f"UPDATE memberships SET {column} = 999 WHERE id = :id"), {"id": member.id}
        )

    with caplog.at_level(logging.ERROR, logger=LOGGER):
        assert await check_ledger_caches() == 1
    [record] = _drifts(caplog)
    assert record.getMessage() == message
    assert record.org_id == str(org.id)
    assert record.membership_id == str(member.id)
    for name, value in fields.items():
        assert getattr(record, name) == value


async def test_one_newsroom_only(
    make_org: MakeOrg, make_member: MakeMember, caplog: pytest.LogCaptureFixture
) -> None:
    org = await make_org()
    other = await make_org("Autre rédaction")
    await make_member(org)
    drifting = await make_member(other)
    async with transaction() as session:
        await session.execute(
            text("UPDATE memberships SET coins = 5 WHERE id = :id"), {"id": drifting.id}
        )

    assert await check_ledger_caches(org.id) == 0
    assert await check_ledger_caches(other.id) == 1

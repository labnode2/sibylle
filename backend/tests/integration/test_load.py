"""The load test of tests/load/run_load.py (T149), at a small scale, on a real server: its
scenario runs, every bet reaches the members who watch its prono, and its newsroom goes away."""

import pytest
from sqlalchemy import func, select
from tests.conftest import ORIGIN
from tests.load.run_load import discard, prepare, run

from sibylle.db.models import AuthSession, Bet, Organisation
from sibylle.db.session import transaction

pytestmark = pytest.mark.integration


async def test_the_load_scenario_runs_and_measures(live_server: str) -> None:
    newsroom = await prepare(members=8, open_pronos=3)
    report = await run(f"http://{live_server}", ORIGIN, newsroom)

    assert report.failures == []
    assert report.sockets == 8 and report.bets == 8 * 3
    async with transaction() as session:
        assert await session.scalar(select(func.count()).select_from(Bet)) == 24
    # Every member watches one prono and receives the bets of the 7 others on it.
    assert len(report.broadcasts) == 8 * 7
    assert all(delay is not None for delay in report.broadcasts)
    assert {"POST /orgs/{org}/pronos/{id}/bets", "GET /orgs/{org}/front-page"} <= set(
        report.timings
    )
    assert "toutes les routes" in report.summary()

    await discard(newsroom)
    async with transaction() as session:
        org = await session.get(Organisation, newsroom.org_id)
        assert org is not None and org.deleted_at is not None
        assert await session.scalar(select(func.count()).select_from(AuthSession)) == 0

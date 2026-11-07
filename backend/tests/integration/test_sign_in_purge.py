"""The worker's daily purge of the sign-ins through Keycloak started and never finished
(specs/002-keycloak-auth/data-model.md, « sign_in_attempts »)."""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from tests.contract.helpers import start_sign_in

from sibylle import clock
from sibylle.db.models import SignInAttempt
from sibylle.db.session import transaction
from sibylle.worker.jobs import purge_sign_in_attempts

pytestmark = pytest.mark.integration


async def test_the_expired_attempts_go_and_the_others_stay(
    client: httpx.AsyncClient, fake_clock: clock.FakeClock
) -> None:
    await start_sign_in(client, suite="/ancienne")
    fake_clock.advance(timedelta(minutes=9))
    await start_sign_in(client, suite="/recente")
    fake_clock.advance(timedelta(minutes=2))

    assert await purge_sign_in_attempts() == 1
    assert await purge_sign_in_attempts() == 0
    async with transaction() as session:
        left = (await session.scalars(select(SignInAttempt.next_path))).all()
    assert left == ["/recente"]

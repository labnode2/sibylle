import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from tests.conftest import MakeOrg, MakePerson

from sybille import clock
from sybille.db.models import Bet, Membership, Prono, Section
from sybille.db.session import transaction

pytestmark = pytest.mark.integration


async def test_simultaneous_bets_stay_consistent(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    async with transaction() as session:
        section = await session.scalar(select(Section).where(Section.org_id == org.id))
        assert section is not None
    created = await hugo.client.post(
        f"/api/orgs/{org.id}/pronos",
        json={
            "kind": "yes_no",
            "question": "Il pleuvra demain ?",
            "section_id": str(section.id),
            "options": [],
            "base_gain": 10,
            "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
        },
    )
    prono = created.json()
    yes = prono["options"][0]["id"]
    people = [await person(org, "reader") for _ in range(10)]

    # Each member sends two bets at once: 20 requests in flight.
    results = await asyncio.gather(
        *(
            p.client.post(
                f"/api/orgs/{org.id}/pronos/{prono['id']}/bets",
                json={"option_id": yes, "stake": stake},
            )
            for p in people
            for stake in (30, 60)
        )
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses == [201] * 10 + [409] * 10

    async with transaction() as session:
        bets = (await session.scalars(select(Bet).where(Bet.prono_id == prono["id"]))).all()
        stored = await session.get(Prono, prono["id"])
        members = (
            await session.scalars(select(Membership).where(Membership.org_id == org.id))
        ).all()
    assert sorted(b.rank for b in bets) == list(range(1, 11))
    assert len({b.membership_id for b in bets}) == 10
    assert stored is not None and stored.pot == sum(b.stake for b in bets)
    assert stored.bet_count == 10
    assert all(m.balance >= 0 for m in members)
    assert all(m.balance == 100 - b.stake for b in bets for m in members if m.id == b.membership_id)

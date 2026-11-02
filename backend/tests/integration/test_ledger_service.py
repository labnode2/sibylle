import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from tests.conftest import MakeMember, MakeOrg

from sibylle.db.models import LedgerEntry, Membership
from sibylle.db.session import transaction
from sibylle.domain import ledger as effects
from sibylle.services import ledger

pytestmark = pytest.mark.integration


async def test_entries_move_balance_and_score_together(
    make_org: MakeOrg, make_member: MakeMember
) -> None:
    org = await make_org()
    member = await make_member(org)
    assert member.balance == 100 and member.season_score == 0

    async with transaction() as session:
        await ledger.append(session, member.id, effects.stake(10))
        await ledger.append(session, member.id, effects.base_gain(20))
        await ledger.append(session, member.id, effects.pot_share(40, stake=10))
        await ledger.append(session, member.id, effects.purchase(30))

    async with transaction() as session:
        fresh = await session.get(Membership, member.id)
        assert fresh is not None
        assert fresh.balance == 100 - 10 + 20 + 40 - 30
        assert fresh.season_score == 20 + 30
        assert await ledger.check_caches(session, org.id) == []


async def test_a_reversal_restores_both_counters(
    make_org: MakeOrg, make_member: MakeMember
) -> None:
    org = await make_org()
    member = await make_member(org)
    async with transaction() as session:
        share = await ledger.append(session, member.id, effects.pot_share(40, stake=10))
        await ledger.reverse(session, share)
    async with transaction() as session:
        fresh = await session.get(Membership, member.id)
        assert fresh is not None
        assert (fresh.balance, fresh.season_score) == (100, 0)
        reversal = await session.scalar(
            select(LedgerEntry).where(LedgerEntry.reverses_entry_id == share.id)
        )
        assert reversal is not None and (reversal.amount, reversal.score_delta) == (-40, -30)


async def test_the_ledger_is_append_only(make_org: MakeOrg, make_member: MakeMember) -> None:
    org = await make_org()
    await make_member(org)
    with pytest.raises(DBAPIError):
        async with transaction() as session:
            await session.execute(text("UPDATE ledger_entries SET amount = 1000"))
    with pytest.raises(DBAPIError):
        async with transaction() as session:
            await session.execute(text("DELETE FROM ledger_entries"))


async def test_check_caches_spots_a_drift(make_org: MakeOrg, make_member: MakeMember) -> None:
    org = await make_org()
    member = await make_member(org)
    async with transaction() as session:
        await session.execute(
            text("UPDATE memberships SET balance = 999 WHERE id = :id"), {"id": member.id}
        )
    async with transaction() as session:
        mismatches = await ledger.check_caches(session, org.id)
    assert [(m.membership_id, m.balance, m.ledger_balance) for m in mismatches] == [
        (member.id, 999, 100)
    ]

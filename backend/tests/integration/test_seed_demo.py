import pytest
from sqlalchemy import select

from sybille.db.models import Organisation, Prono
from sybille.db.session import transaction
from sybille.seed import ORG_TITLE, seed_demo
from sybille.services.ledger import check_caches

pytestmark = pytest.mark.integration


async def test_the_demo_has_a_prono_in_every_state(db: None) -> None:
    await seed_demo()
    await seed_demo()  # twice: nothing is duplicated
    async with transaction() as session:
        org = await session.scalar(select(Organisation).where(Organisation.title == ORG_TITLE))
        assert org is not None
        rows = await session.execute(
            select(Prono.state, Prono.relaunch_count).where(Prono.org_id == org.id)
        )
        states = sorted((state, relaunched) for state, relaunched in rows)
        assert states == [
            ("cancelled", 0),
            ("closed", 0),
            ("open", 0),
            ("open", 0),
            ("open", 0),
            ("open", 1),
            ("resolved", 0),
        ]
        assert await check_caches(session, org.id) == []

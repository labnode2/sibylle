import asyncio
import uuid

import pytest
from sqlalchemy import select
from tests.conftest import MakeMember, MakeOrg
from tests.contract.helpers import waiting_on_a_lock

from sibylle.api.errors import AppError
from sibylle.db.models import Membership
from sibylle.db.session import transaction
from sibylle.services import orgs

pytestmark = pytest.mark.integration


async def demote(org_id: uuid.UUID, member_id: uuid.UUID) -> None:
    async with transaction() as session:
        await orgs.change_role(session, org_id, member_id, "journalist")


async def test_two_editors_demoting_each_other_at_once(
    make_org: MakeOrg, make_member: MakeMember
) -> None:
    """Inès and Hugo, the only two editors, demote each other at the same moment: the second
    change waits for the first, then is refused, and the newsroom keeps an editor."""
    org = await make_org()
    ines = await make_member(org, "editor", pseudo="Inès")
    hugo = await make_member(org, "editor", pseudo="Hugo")

    async with transaction() as session:
        await orgs.change_role(session, org.id, hugo.id, "journalist")
        second = asyncio.create_task(demote(org.id, ines.id))
        await waiting_on_a_lock(second)
    with pytest.raises(AppError) as refused:
        await second
    assert refused.value.code == "last_editor"

    async with transaction() as session:
        rows = await session.execute(
            select(Membership.pseudo, Membership.role).where(Membership.org_id == org.id)
        )
        roles = {pseudo: role for pseudo, role in rows}
    assert roles == {"Inès": "editor", "Hugo": "journalist"}

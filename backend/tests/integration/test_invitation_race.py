import asyncio
from datetime import timedelta

import pytest
from tests.conftest import ClientFor, MakeAccount
from tests.contract.helpers import AVATAR, create_org, token_from

from sybille import clock

pytestmark = pytest.mark.integration


async def test_two_people_racing_for_the_last_place(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    ines = await client_for(await make_account())
    org_id = (await create_org(ines))["org"]["id"]
    response = await ines.post(
        f"/api/orgs/{org_id}/invitations",
        json={
            "kind": "link",
            "max_uses": 1,
            "expires_at": (clock.now() + timedelta(days=1)).isoformat(),
        },
    )
    token = token_from(response.json()["url"])
    first, second = await client_for(await make_account()), await client_for(await make_account())

    results = await asyncio.gather(
        *(
            client.post(
                "/api/join",
                json={"token": token, "pseudo": pseudo, "avatar": AVATAR, "charter_accepted": True},
            )
            for client, pseudo in ((first, "Cami"), (second, "Léo"))
        )
    )
    assert sorted(r.status_code for r in results) == [201, 409]
    refused = next(r for r in results if r.status_code == 409)
    assert refused.json()["error"]["code"] == "invitation_invalid"

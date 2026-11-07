"""GET /api/me reads an unconfirmed address again in Keycloak (US2, research.md K9): at most once
a minute, never once confirmed, and a Keycloak that does not answer changes nothing for the
person (SC-006)."""

from datetime import timedelta

import pytest
from tests.conftest import ClientFor, MakeAccount
from tests.keycloak_fake import FakeKeycloak

from sibylle import clock
from sibylle.db.models import Account
from sibylle.db.session import transaction

pytestmark = pytest.mark.contract


async def test_an_unconfirmed_address_is_read_again_once_a_minute(
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_keycloak: FakeKeycloak,
    fake_clock: clock.FakeClock,
) -> None:
    account = await make_account(verified=False)
    signed_in = await client_for(account)

    def reads() -> list[str]:
        return fake_keycloak.calls_to(f"GET /admin/realms/sibylle/users/{account.keycloak_id}")

    assert (await signed_in.get("/api/me")).json()["email_verified"] is False
    assert len(reads()) == 1
    assert (await signed_in.get("/api/me")).json()["email_verified"] is False
    assert len(reads()) == 1  # within the minute

    # The person follows the link of Keycloak's e-mail, on another device say.
    fake_keycloak.users[str(account.keycloak_id)]["emailVerified"] = True
    fake_clock.advance(timedelta(seconds=61))
    assert (await signed_in.get("/api/me")).json()["email_verified"] is True
    assert len(reads()) == 2
    async with transaction() as session:
        stored = await session.get(Account, account.id)
        assert stored is not None
        assert stored.email_verified_at is not None and stored.identity_checked_at is not None

    # Confirmed: never read again.
    fake_clock.advance(timedelta(minutes=5))
    assert (await signed_in.get("/api/me")).json()["email_verified"] is True
    assert len(reads()) == 2


async def test_a_confirmed_account_never_asks_keycloak(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    signed_in = await client_for(await make_account(verified=True))
    assert (await signed_in.get("/api/me")).json()["email_verified"] is True
    assert fake_keycloak.calls == []


async def test_another_address_confirmed_in_keycloak_is_not_this_one(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    # The address changed in Keycloak and was confirmed there: the next sign-in copies it, with
    # its confirmation; until then, the account's own address stays unconfirmed.
    account = await make_account("ana@exemple.fr", verified=False)
    fake_keycloak.users[str(account.keycloak_id)].update(
        email="ana.b@exemple.fr", emailVerified=True
    )
    signed_in = await client_for(account)
    me = (await signed_in.get("/api/me")).json()
    assert (me["email"], me["email_verified"]) == ("ana@exemple.fr", False)


async def test_without_keycloak_the_known_state_stays(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    signed_in = await client_for(await make_account(verified=False))
    fake_keycloak.down = True
    response = await signed_in.get("/api/me")
    assert response.status_code == 200
    assert response.json()["email_verified"] is False

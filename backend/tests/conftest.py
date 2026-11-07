"""Shared fixtures: a real PostgreSQL (testcontainers), the simulated clock, a fake Keycloak and
HTTP clients.

Unit tests use none of the database fixtures, so they run without Docker.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

from sibylle import clock
from sibylle.config import get_settings
from sibylle.db.base import new_id
from sibylle.db.migrate import upgrade
from sibylle.db.models import (
    Account,
    AuthSession,
    Base,
    CatalogItem,
    Membership,
    Organisation,
    Section,
)
from sibylle.db.session import dispose_engine, transaction
from sibylle.domain.content import AVATAR_TEMPLATES
from sibylle.domain.ledger import starting_balance
from sibylle.services import deals, keycloak, ledger
from sibylle.services.security import new_token, token_hash
from tests import keycloak_fake
from tests.keycloak_fake import FakeKeycloak

PARIS = ZoneInfo("Europe/Paris")
DEFAULT_NOW = datetime(2026, 11, 2, 10, 0, tzinfo=PARIS)
ORIGIN = "http://localhost:5173"
DEFAULT_AVATAR: dict[str, Any] = AVATAR_TEMPLATES[0]["image"]


@pytest.fixture(scope="session", autouse=True)
def _keycloak_settings() -> None:
    """The realm and client of the fake Keycloak, whatever deploy/.env says."""
    os.environ.update(
        OIDC_ISSUER=keycloak_fake.ISSUER,
        KEYCLOAK_INTERNAL_URL=keycloak_fake.INTERNAL,
        OIDC_CLIENT_ID=keycloak_fake.CLIENT_ID,
        OIDC_CLIENT_SECRET=keycloak_fake.CLIENT_SECRET,
    )
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fake_keycloak() -> Iterator[FakeKeycloak]:
    """Keycloak, for every test: no call of the server reaches the network
    (tests/keycloak_fake.py)."""
    fake = FakeKeycloak()
    keycloak.use_transport(fake.transport)
    yield fake
    keycloak.use_transport(None)


@pytest.fixture(autouse=True)
def fake_clock(tmp_path: Path) -> Iterator[clock.FakeClock]:
    fake = clock.FakeClock(tmp_path / "clock.json")
    fake.set(DEFAULT_NOW)
    clock.set_clock(fake)
    yield fake
    clock.set_clock(None)


@pytest.fixture(autouse=True)
def _known_deal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deal of the week falls on the indigo frame at 20 %, which the other tests never buy:
    their purchases keep the usual prices (research.md J10)."""

    def indigo_frame(items: Sequence[CatalogItem]) -> tuple[CatalogItem, int]:
        return next(item for item in items if item.key == "frame-indigo"), 20

    monkeypatch.setattr(deals, "pick", indigo_frame)


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    with PostgresContainer("postgres:18", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        os.environ.update(
            DATABASE_URL=url,
            ENVIRONMENT="test",
            PUBLIC_ORIGIN=ORIGIN,
            SIBYLLE_CLOCK="system",
            UPLOAD_DIR=str(tmp_path_factory.mktemp("uploads")),
        )
        get_settings.cache_clear()
        upgrade(url)
        yield url


@pytest_asyncio.fixture
async def db(database_url: str) -> AsyncIterator[None]:
    """Empties every table after the test, but the reference data the migrations insert: the
    seasons and the catalog of the collection."""
    yield
    kept = {"seasons", "catalog_items"}
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables if t.name not in kept)
    async with transaction() as session:
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _dispose_engine() -> AsyncIterator[None]:
    yield
    await dispose_engine()


def _client(cookie: str | None = None) -> httpx.AsyncClient:
    from sibylle.main import create_app

    headers = {"X-Sibylle": "1", "Origin": ORIGIN}
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="https://testserver",
        headers=headers,
    )
    if cookie:
        client.cookies.set("sibylle_session", cookie)
    return client


@pytest_asyncio.fixture
async def client(db: None) -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as anonymous:
        yield anonymous


MakeAccount = Callable[..., Awaitable[Account]]
MakeOrg = Callable[..., Awaitable[Organisation]]
MakeMember = Callable[..., Awaitable[Membership]]
ClientFor = Callable[[Account], Awaitable[httpx.AsyncClient]]


@pytest.fixture
def make_account(db: None, fake_keycloak: FakeKeycloak) -> MakeAccount:
    """An account of Sibylle and its account in the fake Keycloak, tied as a first sign-in ties
    them."""

    async def make(
        email: str | None = None,
        *,
        first_name: str = "Camille",
        last_name: str = "Martin",
        verified: bool = True,
    ) -> Account:
        email = email or f"compte-{new_id().hex[-8:]}@exemple.fr"
        user = fake_keycloak.add_user(
            email, first_name=first_name, last_name=last_name, verified=verified
        )
        async with transaction() as session:
            account = Account(
                keycloak_id=uuid.UUID(user),
                email=email,
                first_name=first_name,
                last_name=last_name,
                email_verified_at=clock.now() if verified else None,
            )
            session.add(account)
        return account

    return make


@pytest.fixture
def make_org(db: None) -> MakeOrg:
    async def make(title: str = "Sophia Office", **settings: Any) -> Organisation:
        async with transaction() as session:
            org = Organisation(
                title=title, background_key="mer", charter="Charte de test.", **settings
            )
            session.add(org)
            await session.flush()
            session.add(Section(org_id=org.id, name="Général", position=0))
        return org

    return make


@pytest.fixture
def make_member(make_account: MakeAccount) -> MakeMember:
    async def make(
        org: Organisation,
        role: str = "reader",
        *,
        account: Account | None = None,
        pseudo: str | None = None,
    ) -> Membership:
        account = account or await make_account()
        async with transaction() as session:
            member = Membership(
                org_id=org.id,
                account_id=account.id,
                role=role,
                pseudo=pseudo or f"membre-{new_id().hex[-6:]}",
                avatar=DEFAULT_AVATAR,
                charter_accepted_at=clock.now(),
            )
            session.add(member)
            await session.flush()
            await ledger.append(session, member.id, starting_balance(org.starting_balance))
        async with transaction() as session:
            fresh = await session.get(Membership, member.id)
            assert fresh is not None
        return fresh

    return make


@pytest_asyncio.fixture
async def client_for(db: None) -> AsyncIterator[ClientFor]:
    clients: list[httpx.AsyncClient] = []

    async def make(account: Account) -> httpx.AsyncClient:
        token = new_token()
        async with transaction() as session:
            session.add(
                AuthSession(
                    account_id=account.id,
                    token_hash=token_hash(token),
                    expires_at=clock.now().replace(year=clock.now().year + 1),
                )
            )
        signed_in = _client(cookie=token)
        clients.append(signed_in)
        return signed_in

    yield make
    for signed_in in clients:
        await signed_in.aclose()


@dataclass
class Person:
    account: Account
    member: Membership
    client: httpx.AsyncClient


MakePerson = Callable[..., Awaitable[Person]]


@pytest.fixture
def person(make_account: MakeAccount, make_member: MakeMember, client_for: ClientFor) -> MakePerson:
    """A signed-in member of a newsroom, with their HTTP client."""

    async def make(org: Organisation, role: str = "reader", pseudo: str | None = None) -> Person:
        account = await make_account()
        member = await make_member(org, role, account=account, pseudo=pseudo)
        return Person(account, member, await client_for(account))

    return make


@pytest_asyncio.fixture
async def live_server(db: None) -> AsyncIterator[str]:
    """The app served by a real uvicorn on a free port (lifespan, WebSocket, real-time bus)."""
    import uvicorn

    from sibylle.main import create_app

    config = uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 - uvicorn exposes a flag, not an event
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"127.0.0.1:{port}"
    server.should_exit = True
    await task

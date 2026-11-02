"""Shared fixtures: a real PostgreSQL (testcontainers), the simulated clock and HTTP clients.

Unit tests use none of the database fixtures, so they run without Docker.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

from sybille import clock
from sybille.config import get_settings
from sybille.db.base import new_id
from sybille.db.models import Account, AuthSession, Base, Membership, Organisation, Section
from sybille.db.session import dispose_engine, transaction
from sybille.domain.content import AVATAR_TEMPLATES
from sybille.domain.ledger import starting_balance
from sybille.services import ledger
from sybille.services.security import hash_password, new_token, token_hash

PARIS = ZoneInfo("Europe/Paris")
DEFAULT_NOW = datetime(2026, 11, 2, 10, 0, tzinfo=PARIS)
ORIGIN = "http://localhost:5173"
PASSWORD = "lauriers-et-boules"
DEFAULT_AVATAR: dict[str, Any] = AVATAR_TEMPLATES[0]["image"]
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fake_clock(tmp_path: Path) -> Iterator[clock.FakeClock]:
    fake = clock.FakeClock(tmp_path / "clock.json")
    fake.set(DEFAULT_NOW)
    clock.set_clock(fake)
    yield fake
    clock.set_clock(None)


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    with PostgresContainer("postgres:18", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        os.environ.update(
            DATABASE_URL=url,
            ENVIRONMENT="test",
            PUBLIC_ORIGIN=ORIGIN,
            SYBILLE_CLOCK="system",
            UPLOAD_DIR=str(tmp_path_factory.mktemp("uploads")),
        )
        get_settings.cache_clear()
        config = Config(str(BACKEND / "alembic.ini"))
        config.attributes["database_url"] = url
        config.attributes["configure_logger"] = False
        command.upgrade(config, "head")
        yield url


@pytest_asyncio.fixture
async def db(database_url: str) -> AsyncIterator[None]:
    """Empties every table but the seasons after the test."""
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables if t.name != "seasons")
    async with transaction() as session:
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _dispose_engine() -> AsyncIterator[None]:
    yield
    await dispose_engine()


def _client(cookie: str | None = None) -> httpx.AsyncClient:
    from sybille.main import create_app

    headers = {"X-Sybille": "1", "Origin": ORIGIN}
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="https://testserver",
        headers=headers,
    )
    if cookie:
        client.cookies.set("sybille_session", cookie)
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
def make_account(db: None) -> MakeAccount:
    async def make(
        email: str | None = None,
        *,
        password: str = PASSWORD,
        first_name: str = "Camille",
        last_name: str = "Martin",
        verified: bool = True,
    ) -> Account:
        async with transaction() as session:
            account = Account(
                email=email or f"compte-{new_id().hex[-8:]}@exemple.fr",
                password_hash=hash_password(password),
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

    from sybille.main import create_app

    config = uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 - uvicorn exposes a flag, not an event
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"127.0.0.1:{port}"
    server.should_exit = True
    await task

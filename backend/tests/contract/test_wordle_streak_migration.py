"""Migration 0038: a Wordle game already over ends at the time of its first try, the only one kept;
a game won before the chain of wins paid no bonus. A game under way has no end yet."""

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from sibylle.db.migrate import alembic_config

pytestmark = pytest.mark.contract

FIRST_TRY = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
GAMES = (("won", 6), ("lost", None), ("playing", None))


async def _query(url: str, sql: str) -> list[tuple[object, ...]]:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        rows = [tuple(row) for row in await conn.execute(text(sql))]
    await engine.dispose()
    return rows


async def _insert_old_games(url: str) -> None:
    """A won, a lost and an unfinished game, a day apart, each begun at 9:00 UTC."""
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        # The foreign keys are not what is tested here.
        for fk in ("membership_id_memberships", "org_id_organisations"):
            await conn.execute(
                text(f"ALTER TABLE wordle_games DROP CONSTRAINT fk_wordle_games_{fk}")
            )
        org, member = uuid.uuid4(), uuid.uuid4()
        for days, (state, laurels) in enumerate(GAMES):
            await conn.execute(
                text(
                    "INSERT INTO wordle_games (id, org_id, membership_id, day, guesses, state,"
                    " laurels, created_at) VALUES (:id, :o, :m, :d, '{arbre}', :s, :l, :c)"
                ),
                {
                    "id": uuid.uuid4(),
                    "o": org,
                    "m": member,
                    "d": date(2026, 11, 20) + timedelta(days=days),
                    "s": state,
                    "l": laurels,
                    "c": FIRST_TRY + timedelta(days=days),
                },
            )
    await engine.dispose()


def test_games_already_over_end_at_their_first_try_and_paid_no_chain_bonus() -> None:
    with PostgresContainer("postgres:18", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        config = alembic_config(url)
        command.upgrade(config, "0037")
        asyncio.run(_insert_old_games(url))
        command.upgrade(config, "0038")
        rows = asyncio.run(
            _query(url, "SELECT state, finished_at, streak_bonus FROM wordle_games ORDER BY day")
        )
        assert rows == [
            ("won", FIRST_TRY, 0),
            ("lost", FIRST_TRY + timedelta(days=1), None),
            ("playing", None, None),
        ]
        command.downgrade(config, "0037")
        columns = asyncio.run(
            _query(
                url,
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'wordle_games'",
            )
        )
        assert {"finished_at", "streak_bonus"}.isdisjoint(name for (name,) in columns)

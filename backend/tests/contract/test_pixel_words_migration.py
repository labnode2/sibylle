"""Migration 0034: a drawing keeps its word as its only word."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from sibylle.db.migrate import alembic_config

pytestmark = pytest.mark.contract


async def _run(
    url: str, statements: list[tuple[str, dict[str, object]]]
) -> list[tuple[object, ...]]:
    engine = create_async_engine(url)
    rows: list[tuple[object, ...]] = []
    async with engine.begin() as conn:
        for sql, params in statements:
            result = await conn.execute(text(sql), params)
            if result.returns_rows:
                rows = [tuple(r) for r in result]
    await engine.dispose()
    return rows


def test_existing_drawings_keep_their_word() -> None:
    org, member, puzzle = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    with PostgresContainer("postgres:18", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        config = alembic_config(url)
        command.upgrade(config, "0033")
        # Only the columns the drawing needs: the rest has defaults, or is filled below.
        asyncio.run(_insert_old_puzzle(url, org, member, puzzle, now))
        command.upgrade(config, "0034")
        rows = asyncio.run(_run(url, [("SELECT words, words_normalized FROM pixel_puzzles", {})]))
        assert rows == [(["Café"], ["cafe"])]
        command.downgrade(config, "0033")
        rows = asyncio.run(_run(url, [("SELECT word, word_normalized FROM pixel_puzzles", {})]))
        assert rows == [("Café", "cafe")]


async def _insert_old_puzzle(
    url: str, org: uuid.UUID, member: uuid.UUID, puzzle: uuid.UUID, now: datetime
) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        # The foreign keys are not what is tested here.
        for fk in ("author_membership_id_memberships", "org_id_organisations"):
            await conn.execute(
                text(f"ALTER TABLE pixel_puzzles DROP CONSTRAINT fk_pixel_puzzles_{fk}")
            )
        await conn.execute(
            text(
                "INSERT INTO pixel_puzzles (id, org_id, author_membership_id, drawing, word,"
                " word_normalized, reveal_order, created_at)"
                " VALUES (:p, :o, :m, '{}'::jsonb, 'Café', 'cafe', '\\x00', :n)"
            ),
            {"p": puzzle, "o": org, "m": member, "n": now},
        )
    await engine.dispose()

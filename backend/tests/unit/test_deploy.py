"""What the containers rely on: the migrations found from the installed package, the commands
the Compose file runs, and the worker's heartbeat behind its health check."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from sibylle.cli import build_parser
from sibylle.db.migrate import MIGRATIONS, alembic_config
from sibylle.worker import main as worker

pytestmark = pytest.mark.unit


def test_the_migrations_are_found_from_the_package() -> None:
    config = alembic_config("postgresql+asyncpg://x@db/sibylle")
    assert config.get_main_option("script_location") == str(MIGRATIONS)
    assert config.attributes["database_url"] == "postgresql+asyncpg://x@db/sibylle"
    assert (MIGRATIONS / "env.py").is_file() and (MIGRATIONS / "script.py.mako").is_file()
    assert any(MIGRATIONS.glob("versions/0001_*.py"))


def test_the_compose_commands_parse() -> None:
    parser = build_parser()
    serve = parser.parse_args(["serve"])
    assert (serve.command, serve.host, serve.port) == ("serve", "0.0.0.0", 8000)
    assert parser.parse_args(["migrate"]).command == "migrate"
    assert parser.parse_args(["worker", "--check"]).check is True
    assert parser.parse_args(["worker"]).check is False


def test_the_worker_is_alive_while_it_beats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker, "HEARTBEAT", tmp_path / "alive")
    assert not worker.alive()
    asyncio.run(worker.beat())
    assert worker.alive()
    old = time.time() - worker.HEARTBEAT_MAX_AGE.total_seconds() - 1
    os.utime(worker.HEARTBEAT, (old, old))
    assert not worker.alive()

"""Alembic from the installed package: `sibylle migrate`, `sibylle serve` and the tests run the
migrations the same way, in the container as on a developer's machine (alembic.ini only serves
`alembic revision`)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config(database_url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("path_separator", "os")
    if database_url:
        config.attributes["database_url"] = database_url
    return config


def upgrade(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")

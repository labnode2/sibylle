"""Settings read from the environment (and from deploy/.env when the server runs from backend/)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../deploy/.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://sybille:sybille@localhost:5432/sybille"
    public_origin: str = "http://localhost:5173"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "Sybille <ne-pas-repondre@localhost>"

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:contact@localhost"

    upload_dir: Path = Path("./data/uploads")

    sybille_clock: Literal["system", "fake"] = "system"
    sybille_fake_clock_file: Path = Path("./.fake-clock")

    log_level: str = "INFO"

    @model_validator(mode="after")
    def _no_fake_clock_in_production(self) -> Self:
        if self.environment == "production" and self.sybille_clock == "fake":
            raise ValueError("SYBILLE_CLOCK=fake est interdit en production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

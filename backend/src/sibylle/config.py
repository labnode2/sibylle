"""Settings read from the environment (and from deploy/.env when the server runs from backend/)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../deploy/.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://sibylle:sibylle@localhost:5432/sibylle"
    public_origin: str = "http://localhost:5173"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "Sibylle <ne-pas-repondre@localhost>"

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:contact@localhost"

    upload_dir: Path = Path("./data/uploads")

    # Sign-in through Keycloak (specs/002-keycloak-auth/contracts/auth.md): the realm's public
    # address, where the browser goes and which the tokens carry; the address the server calls
    # Keycloak at (scheme, host and port; empty for the issuer's); the server's client in the
    # realm. The defaults are the local Keycloak of `make keycloak`.
    oidc_issuer: str = "http://localhost:8280/realms/sibylle"
    keycloak_internal_url: str | None = None
    oidc_client_id: str = "sibylle"
    oidc_client_secret: str = ""

    sibylle_clock: Literal["system", "fake"] = "system"
    sibylle_fake_clock_file: Path = Path("./.fake-clock")

    log_level: str = "INFO"

    @field_validator("oidc_issuer", "keycloak_internal_url")
    @classmethod
    def _no_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @model_validator(mode="after")
    def _no_fake_clock_in_production(self) -> Self:
        if self.environment == "production" and self.sibylle_clock == "fake":
            raise ValueError("SIBYLLE_CLOCK=fake est interdit en production")
        return self

    @model_validator(mode="after")
    def _keycloak_in_production(self) -> Self:
        if self.environment == "production":
            if not self.oidc_client_secret:
                raise ValueError("OIDC_CLIENT_SECRET est obligatoire en production")
            if urlsplit(self.oidc_issuer).scheme != "https":
                raise ValueError("OIDC_ISSUER doit être en https en production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def keycloak_realm_url(self) -> str:
        """The realm's address for the server's own calls (code exchange, keys, admin API): the
        issuer's path on KEYCLOAK_INTERNAL_URL, `http://keycloak:8080` in production, or the
        issuer itself."""
        if not self.keycloak_internal_url:
            return self.oidc_issuer
        return self.keycloak_internal_url + urlsplit(self.oidc_issuer).path

    @property
    def secure_cookies(self) -> bool:
        """The session cookie is `Secure`, except in development on a local network address in
        plain http (`make dev UI_HOST=192.168.71.12`, to try the app on a phone): browsers keep
        `Secure` cookies only on https and on localhost. Production always keeps it."""
        origin = urlsplit(self.public_origin)
        return (
            self.is_production
            or origin.scheme == "https"
            or origin.hostname in ("localhost", "127.0.0.1", "::1")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

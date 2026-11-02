"""Accounts and sessions: sign-up, sign-in, address check, password changes."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.config import get_settings
from sibylle.db.models import Account, AuthSession, EmailToken
from sibylle.services import notifications
from sibylle.services.security import (
    hash_password,
    needs_rehash,
    new_token,
    token_hash,
    verify_password,
)

SESSION_LIFETIME = timedelta(days=30)
VERIFY_EMAIL_LIFETIME = timedelta(hours=24)
RESET_PASSWORD_LIFETIME = timedelta(hours=1)
# Verifies against this hash when the address is unknown, so both cases take the same time.
_DUMMY_HASH = hash_password("pas-un-vrai-mot-de-passe")


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def find_by_email(session: AsyncSession, email: str) -> Account | None:
    account: Account | None = await session.scalar(
        select(Account).where(Account.email == normalize_email(email), Account.deleted_at.is_(None))
    )
    return account


async def open_session(session: AsyncSession, account: Account, user_agent: str | None) -> str:
    """Signs a browser in; returns the token for its cookie."""
    token = new_token()
    session.add(
        AuthSession(
            account_id=account.id,
            token_hash=token_hash(token),
            expires_at=clock.now() + SESSION_LIFETIME,
            user_agent=(user_agent or "")[:200] or None,
        )
    )
    return token


async def close_sessions(
    session: AsyncSession, account_id: uuid.UUID, *, keep_token: str | None = None
) -> None:
    statement = delete(AuthSession).where(AuthSession.account_id == account_id)
    if keep_token:
        statement = statement.where(AuthSession.token_hash != token_hash(keep_token))
    await session.execute(statement)


async def _email_token(
    session: AsyncSession, account: Account, purpose: str
) -> tuple[str, uuid.UUID]:
    lifetime = VERIFY_EMAIL_LIFETIME if purpose == "verify_email" else RESET_PASSWORD_LIFETIME
    token = new_token()
    row = EmailToken(
        account_id=account.id,
        purpose=purpose,
        token_hash=token_hash(token),
        expires_at=clock.now() + lifetime,
    )
    session.add(row)
    await session.flush()
    return token, row.id


async def send_verification(session: AsyncSession, account: Account) -> None:
    token, row_id = await _email_token(session, account, "verify_email")
    await notifications.enqueue(
        session,
        type="verify_email",
        account_id=account.id,
        dedupe_key=f"verify_email:{row_id}",
        payload={
            "first_name": account.first_name,
            "link": f"{get_settings().public_origin}/verifier-email?jeton={token}",
        },
    )


async def signup(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    user_agent: str | None,
) -> tuple[Account, str]:
    if await find_by_email(session, email):
        raise AppError("email_taken")
    account = Account(
        email=normalize_email(email),
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
    )
    session.add(account)
    await session.flush()
    token = await open_session(session, account, user_agent)
    await send_verification(session, account)
    return account, token


async def login(
    session: AsyncSession, email: str, password: str, user_agent: str | None
) -> tuple[Account, str] | None:
    """The account and a new session token, or None when the credentials are wrong."""
    account = await find_by_email(session, email)
    if account is None or account.password_hash is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(account.password_hash, password):
        return None
    if needs_rehash(account.password_hash):
        account.password_hash = hash_password(password)
    return account, await open_session(session, account, user_agent)


async def logout(session: AsyncSession, token: str | None) -> None:
    if token:
        await session.execute(
            delete(AuthSession).where(AuthSession.token_hash == token_hash(token))
        )


def update_account(account: Account, changes: dict[str, Any]) -> None:
    for field in ("first_name", "last_name", "theme", "reduce_motion", "locale"):
        if field in changes and changes[field] is not None:
            setattr(account, field, changes[field])


async def change_password(
    session: AsyncSession, account: Account, current: str, new: str, current_token: str | None
) -> None:
    if account.password_hash is None or not verify_password(account.password_hash, current):
        raise AppError("validation_error", {"current_password": "invalid"})
    account.password_hash = hash_password(new)
    await close_sessions(session, account.id, keep_token=current_token)


async def _use_token(session: AsyncSession, token: str, purpose: str) -> Account:
    row = await session.scalar(
        select(EmailToken)
        .where(EmailToken.token_hash == token_hash(token), EmailToken.purpose == purpose)
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= clock.now():
        raise AppError("token_invalid")
    account = await session.get(Account, row.account_id)
    if account is None or account.deleted_at is not None:
        raise AppError("token_invalid")
    row.used_at = clock.now()
    return account


async def verify_email(session: AsyncSession, token: str) -> None:
    account = await _use_token(session, token, "verify_email")
    account.email_verified_at = account.email_verified_at or clock.now()


async def request_password_reset(session: AsyncSession, email: str) -> None:
    """Sends a reset link when the address has an account; says nothing either way."""
    account = await find_by_email(session, email)
    if account is None:
        return
    token, row_id = await _email_token(session, account, "reset_password")
    await notifications.enqueue(
        session,
        type="reset_password",
        account_id=account.id,
        dedupe_key=f"reset_password:{row_id}",
        payload={
            "first_name": account.first_name,
            "link": f"{get_settings().public_origin}/mot-de-passe/nouveau?jeton={token}",
        },
    )


async def reset_password(session: AsyncSession, token: str, password: str) -> None:
    account = await _use_token(session, token, "reset_password")
    account.password_hash = hash_password(password)
    await close_sessions(session, account.id)

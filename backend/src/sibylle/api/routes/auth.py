"""Sign-up, sign-in, sign-out, address check and password reset."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from sibylle.api.deps import (
    SESSION_COOKIE,
    CurrentAccount,
    Db,
    Limits,
    clear_session_cookie,
    client_ip,
    limits,
)
from sibylle.api.errors import AppError
from sibylle.api.routes.me import me_of
from sibylle.api.schemas import LoginIn, Me, ResetConfirm, ResetRequest, SignupIn, TokenIn
from sibylle.config import get_settings
from sibylle.services import accounts
from sibylle.services.accounts import SESSION_LIFETIME

router = APIRouter(prefix="/auth", tags=["auth"])

RateLimits = Annotated[Limits, Depends(limits)]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="lax",
        path="/",
    )


@router.post("/signup", status_code=201)
async def signup(body: SignupIn, request: Request, response: Response, session: Db) -> Me:
    account, token = await accounts.signup(
        session,
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, token)
    return await me_of(session, account)


@router.post("/login")
async def login(
    body: LoginIn, request: Request, response: Response, session: Db, rate: RateLimits
) -> Me:
    email_key = f"email:{accounts.normalize_email(body.email)}"
    ip_key = f"ip:{client_ip(request)}"
    rate.login.check(email_key)
    rate.login_ip.check(ip_key)
    result = await accounts.login(
        session, body.email, body.password, request.headers.get("user-agent")
    )
    if result is None:
        rate.login.add(email_key)
        rate.login_ip.add(ip_key)
        raise AppError("invalid_credentials")
    account, token = result
    rate.login.reset(email_key)
    set_session_cookie(response, token)
    return await me_of(session, account)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: Db) -> None:
    await accounts.logout(session, request.cookies.get(SESSION_COOKIE))
    clear_session_cookie(response)


@router.post("/verify-email", status_code=204)
async def verify_email(body: TokenIn, session: Db) -> None:
    await accounts.verify_email(session, body.token)


@router.post("/verify-email/resend", status_code=204)
async def resend_verification(account: CurrentAccount, session: Db, rate: RateLimits) -> None:
    rate.resend_verification.hit(f"account:{account.id}")
    if account.email_verified_at is None:
        await accounts.send_verification(session, account)


@router.post("/password-reset", status_code=202)
async def request_password_reset(
    body: ResetRequest, request: Request, session: Db, rate: RateLimits
) -> None:
    email_key = f"email:{accounts.normalize_email(body.email)}"
    ip_key = f"ip:{client_ip(request)}"
    rate.password_reset.check(email_key)
    rate.password_reset_ip.check(ip_key)
    rate.password_reset.add(email_key)
    rate.password_reset_ip.add(ip_key)
    await accounts.request_password_reset(session, body.email)


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(body: ResetConfirm, session: Db) -> None:
    await accounts.reset_password(session, body.token, body.password)

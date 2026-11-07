"""Signing up and in through Keycloak, signing out (specs/002-keycloak-auth/contracts/auth.md).

The browser goes to Keycloak's pages by `/auth/login` and comes back by `/auth/callback`; in
between, a `sign_in_attempts` row, named by the `sibylle_signin` cookie, keeps the state, the
nonce and the PKCE verifier of that sign-in (research.md K3). The session that opens afterwards
is the `sibylle_session` of research.md R4.
"""

import logging
import secrets
from datetime import timedelta
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from sibylle import clock
from sibylle.api.deps import (
    SESSION_COOKIE,
    CurrentAccount,
    Db,
    Limits,
    clear_session_cookie,
    limits,
)
from sibylle.api.errors import AppError
from sibylle.config import get_settings
from sibylle.db.models import SignInAttempt
from sibylle.db.session import transaction
from sibylle.services import accounts, keycloak
from sibylle.services.accounts import SESSION_LIFETIME
from sibylle.services.security import new_token, token_hash

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)

RateLimits = Annotated[Limits, Depends(limits)]

SIGNIN_COOKIE = "sibylle_signin"
SIGNIN_PATH = "/api/auth"
SIGNIN_LIFETIME = timedelta(minutes=10)
# The pages of the interface the way back may end on (contracts/auth.md, « Pages »).
SIGN_IN_PAGE = "/connexion"
UNAVAILABLE_PAGE = "/connexion-indisponible"


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


def safe_next(path: str | None) -> str:
    """The page of Sibylle to come back to, checked like the interface's `nextPath`: a path of
    the app, never `//…`, nor anything a browser could read as another site (a backslash, a
    control character), nor the API itself; otherwise the front page."""
    if (
        not path
        or len(path) > 2000
        or not path.startswith("/")
        or path.startswith("//")
        or path.startswith("/api/")
        or "\\" in path
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in path)
    ):
        return "/"
    return path


def _page(path: str, next_path: str, **params: str) -> str:
    if next_path != "/":
        params["suite"] = next_path
    return f"{path}?{urlencode(params)}" if params else path


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _unavailable(next_path: str) -> RedirectResponse:
    return _redirect(_page(UNAVAILABLE_PAGE, next_path))


def _end_attempt(response: RedirectResponse) -> RedirectResponse:
    response.delete_cookie(
        SIGNIN_COOKIE,
        path=SIGNIN_PATH,
        secure=get_settings().secure_cookies,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/login", status_code=303, response_class=RedirectResponse)
async def login(
    session: Db,
    action: Literal["login", "signup", "password", "forgot"] = "login",
    suite: Annotated[str | None, Query(max_length=2000)] = None,
) -> RedirectResponse:
    """To Keycloak's sign-in page (`signup`: its sign-up page; `password`: a new password to
    choose; `forgot`: its forgotten password page), or to the page that says it does not answer.
    """
    next_path = safe_next(suite)
    if not await keycloak.realm_is_up():
        return _unavailable(next_path)
    if action == "forgot":
        return _redirect(keycloak.forgot_password_url())
    token, state, nonce = new_token(), new_token(), new_token()
    verifier, challenge = keycloak.new_pkce()
    session.add(
        SignInAttempt(
            token_hash=token_hash(token),
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            action=action,
            next_path=next_path,
            expires_at=clock.now() + SIGNIN_LIFETIME,
        )
    )
    response = _redirect(
        keycloak.authorization_url(action, state=state, nonce=nonce, code_challenge=challenge)
    )
    response.set_cookie(
        SIGNIN_COOKIE,
        token,
        max_age=int(SIGNIN_LIFETIME.total_seconds()),
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="lax",
        path=SIGNIN_PATH,
    )
    return response


@router.get("/callback", status_code=303, response_class=RedirectResponse)
async def callback(
    request: Request,
    session: Db,
    background: BackgroundTasks,
    code: Annotated[str | None, Query(max_length=4000)] = None,
    state: Annotated[str | None, Query(max_length=200)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    """The way back from Keycloak: the browser that started this sign-in, within 10 minutes and
    once, gets a session and goes on to its page; anything else ends on `/connexion?erreur=…`,
    without a session."""
    token = request.cookies.get(SIGNIN_COOKIE)
    attempt = None
    if token:
        attempt = await session.scalar(
            select(SignInAttempt)
            .where(SignInAttempt.token_hash == token_hash(token))
            .with_for_update()
        )
    next_path = attempt.next_path if attempt is not None else "/"

    def failed(reason: str) -> RedirectResponse:
        return _end_attempt(_redirect(_page(SIGN_IN_PAGE, next_path, erreur=reason)))

    if attempt is None:
        return failed("expired")
    # Single use: the attempt goes, whatever comes next.
    await session.delete(attempt)
    if (
        attempt.expires_at <= clock.now()
        or state is None
        or not secrets.compare_digest(state, attempt.state)
    ):
        return failed("expired")
    if error is not None:
        return failed("denied" if error == "access_denied" else "failed")
    if code is None:
        return failed("failed")
    try:
        id_token = await keycloak.exchange_code(code, attempt.code_verifier)
        identity = await keycloak.verify_id_token(id_token, attempt.nonce)
    except keycloak.IdentityUnavailable:
        return _end_attempt(_unavailable(next_path))
    except keycloak.Rejected as refused:
        log.warning("sign-in refused", extra={"reason": str(refused)})
        return failed("failed")
    try:
        signed_in = await accounts.sign_in(session, identity, request.headers.get("user-agent"))
    except AppError as refused:
        return failed(refused.code)
    # A new account's address check leaves once the browser is on its way (research.md K9).
    if signed_in.created and not identity.email_verified:
        background.add_task(accounts.send_first_verification, identity.sub)
    # The browser's former session, if it had one, gives way to the new one.
    await accounts.logout(session, request.cookies.get(SESSION_COOKIE))
    response = _redirect(next_path)
    set_session_cookie(response, signed_in.token)
    return _end_attempt(response)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    """Closes the session, then its Keycloak session, or Keycloak would sign the browser in again
    at once. The first is committed before Keycloak is called: Keycloak then tells this server of
    that session's end (a back-channel logout), which must not wait behind this request. Keycloak
    not answering closes Sibylle's session all the same: its own ends after 30 minutes without
    use (research.md K7)."""
    async with transaction() as session:
        sid = await accounts.logout(session, request.cookies.get(SESSION_COOKIE))
    clear_session_cookie(response)
    if sid:
        try:
            await keycloak.delete_session(sid)
        except keycloak.IdentityUnavailable:
            log.warning("keycloak's session stays open until it expires", extra={"sid": sid})


@router.post("/backchannel-logout", responses={400: {"description": "Jeton refusé"}})
async def backchannel_logout(
    logout_token: Annotated[str, Form(max_length=8000)], session: Db
) -> Response:
    """Keycloak tells of Keycloak sessions that ended elsewhere: signed out of another device by a
    new password, closed by an administrator, or by Sibylle's own sign-out (OpenID Connect
    Back-Channel Logout, research.md K8). Their Sibylle sessions end, WebSockets included. Called
    by Keycloak, not by browsers: the signed token is its proof, without X-Sibylle nor Origin."""
    try:
        logout = await keycloak.verify_logout_token(logout_token)
    except keycloak.Rejected as refused:
        log.warning("back-channel logout refused", extra={"reason": str(refused)})
        raise AppError("invalid_token") from refused
    except keycloak.IdentityUnavailable as error:
        raise AppError("identity_unavailable") from error
    ended = await accounts.end_keycloak_sessions(session, logout)
    log.info("signed out by keycloak", extra={"sid": logout.sid, "sessions": len(ended)})
    return Response(status_code=200, headers={"Cache-Control": "no-store"})


@router.post("/verify-email/resend", status_code=204)
async def resend_verification(account: CurrentAccount, rate: RateLimits) -> None:
    rate.resend_verification.hit(f"account:{account.id}")
    if account.email_verified_at is None:
        try:
            await accounts.send_verification(account)
        except keycloak.IdentityUnavailable as error:
            raise AppError("identity_unavailable") from error

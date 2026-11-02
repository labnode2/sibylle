"""The FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from sybille.api.deps import Limits
from sybille.api.errors import error_response, install_error_handlers
from sybille.api.routes import (
    auth,
    bets,
    content,
    health,
    invitations,
    me,
    members,
    orgs,
    pronos,
    reports,
    results,
    uploads,
)
from sybille.config import get_settings
from sybille.db.session import dispose_engine
from sybille.logs import configure_logging
from sybille.realtime import ws
from sybille.realtime.bus import Listener, asyncpg_dsn
from sybille.realtime.hub import Hub

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CsrfMiddleware:
    """Requests that change something must carry `X-Sybille: 1` and come from the app's origin."""

    def __init__(self, app: ASGIApp, origin: str) -> None:
        self.app = app
        self.origin = origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _UNSAFE_METHODS:
            headers = Headers(scope=scope)
            if headers.get("x-sybille") != "1" or headers.get("origin") != self.origin:
                await error_response("forbidden", 403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    hub = Hub()
    listener = Listener(asyncpg_dsn(get_settings().database_url), hub.dispatch)
    app.state.hub = hub
    await listener.start()
    yield
    await hub.close_all(1012)  # "service restart": browsers reconnect and reload
    await listener.stop()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="Sybille",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(CsrfMiddleware, origin=settings.public_origin)
    install_error_handlers(app)
    app.state.limits = Limits()
    for module in (
        health,
        content,
        auth,
        me,
        orgs,
        members,
        invitations,
        pronos,
        bets,
        results,
        reports,
        uploads,
    ):
        app.include_router(module.router, prefix="/api")
    app.include_router(ws.router, prefix="/api")
    return app

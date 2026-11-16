"""One JSON log line per HTTP request, written once the response is over.

What a line holds: method, path without its query string, status, duration and, when signed in,
the account. Error responses in the API's envelope add their code and refused fields. Never the
visitor's address, the query string (it carries the OIDC `code` on /api/auth/callback), the
request's body, its headers nor its cookies.
"""

import json
import logging
import re
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)

# Called every 10 s by the healthcheck of deploy/compose.prod.yml.
_SKIPPED = {("GET", "/api/health")}
# Secret parts of a path: a public card's token gives access to the card.
_MASKED = [(re.compile(r"^/api/public/cards/[^/]+$"), "/api/public/cards/{token}")]
# An error body bigger than this is not the API's envelope: not kept.
_MAX_ERROR_BODY = 64 * 1024


def _masked(path: str) -> str:
    for pattern, replacement in _MASKED:
        if pattern.match(path):
            return replacement
    return path


def _error_details(body: bytes) -> dict[str, Any]:
    """`code` and `fields` (names and codes) of an error in the API's envelope."""
    try:
        error = json.loads(body)["error"]
    except ValueError, KeyError, TypeError:
        return {}
    if not isinstance(error, dict):
        return {}
    details: dict[str, Any] = {}
    if isinstance(error.get("code"), str):
        details["code"] = error["code"]
    fields = error.get("fields")
    if isinstance(fields, dict) and fields:
        details["fields"] = {str(k): str(v) for k, v in fields.items()}
    return details


def _level(status: int) -> int:
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    return logging.INFO


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (scope["method"], scope["path"]) in _SKIPPED:
            await self.app(scope, receive, send)
            return
        # current_account writes the account here, through request.state.
        scope.setdefault("state", {})
        started = time.perf_counter()
        status = 0
        body = bytearray()
        keep_body = False

        async def send_and_watch(message: Message) -> None:
            nonlocal status, keep_body
            if message["type"] == "http.response.start":
                status = message["status"]
                keep_body = status >= 400
            elif message["type"] == "http.response.body" and keep_body:
                body.extend(message.get("body", b""))
                if len(body) > _MAX_ERROR_BODY:
                    keep_body = False
                    body.clear()
            await send(message)

        try:
            await self.app(scope, receive, send_and_watch)
        except Exception:
            # Starlette's outer middleware answers 500 once the exception goes on up.
            log.error("request", exc_info=True, extra=self._extra(scope, 500, started))
            raise
        extra = self._extra(scope, status, started)
        if body:
            extra.update(_error_details(bytes(body)))
        log.log(_level(status), "request", extra=extra)

    @staticmethod
    def _extra(scope: Scope, status: int, started: float) -> dict[str, Any]:
        extra: dict[str, Any] = {
            "method": scope["method"],
            "path": _masked(scope["path"]),
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        }
        account_id = scope.get("state", {}).get("account_id")
        if account_id is not None:
            extra["account_id"] = account_id
        return extra

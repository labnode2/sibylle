"""Every request the API gets leaves one log line, with its outcome: never the visitor's
address, the query string, the submitted values, the headers nor the cookies."""

import asyncio
import logging
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
import websockets
from tests.conftest import ORIGIN, MakeOrg, MakePerson

from sibylle import clock
from sibylle.logs import configure_logging

pytestmark = pytest.mark.contract

QUESTION = "Qui gagne le derby secret ?"


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[logging.LogRecord]]:
    # create_app() replaces the root handlers: keep them, and listen on the loggers themselves.
    monkeypatch.setattr("sibylle.main.configure_logging", lambda _level: None)
    seen: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record)

    logger = logging.getLogger("sibylle")
    handler = Collect(level=logging.INFO)
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield seen
    logger.removeHandler(handler)
    logger.setLevel(previous)


async def body(client: Any, org_id: str, **changes: Any) -> dict[str, Any]:
    sections = (await client.get(f"/api/orgs/{org_id}/sections")).json()
    data: dict[str, Any] = {
        "kind": "choice",
        "question": QUESTION,
        "section_id": sections[0]["id"],
        "options": ["Nice", "Monaco"],
        "base_gain": 20,
        "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
    }
    data.update(changes)
    return data


def only_request(records: list[logging.LogRecord]) -> logging.LogRecord:
    found = [r for r in records if r.getMessage() == "request"]
    assert len(found) == 1, [r.__dict__ for r in found]
    return found[0]


def anonymous(**headers: str) -> httpx.AsyncClient:
    from sibylle.main import create_app

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="https://testserver",
        headers=headers,
    )


async def test_a_successful_request_is_logged(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    cami = await person(org, "reader")
    records.clear()
    response = await cami.client.get(f"/api/orgs/{org.id}/sections")
    assert response.status_code == 200

    record = only_request(records)
    assert record.levelno == logging.INFO
    assert record.__dict__["method"] == "GET"
    assert record.__dict__["path"] == f"/api/orgs/{org.id}/sections"
    assert record.__dict__["status"] == 200
    assert isinstance(record.__dict__["duration_ms"], int)
    assert record.__dict__["account_id"] == str(cami.account.id)
    assert "code" not in record.__dict__


async def test_a_refused_prono_is_logged(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    past = (clock.now() - timedelta(days=1)).isoformat()
    data = await body(hugo.client, str(org.id), closes_at=past)
    records.clear()
    refused = await hugo.client.post(f"/api/orgs/{org.id}/pronos?secret=1", json=data)
    assert refused.status_code == 422
    assert refused.json()["error"]["fields"] == {"closes_at": "past"}

    record = only_request(records)
    assert record.levelno == logging.WARNING
    assert record.__dict__["method"] == "POST"
    assert record.__dict__["path"] == f"/api/orgs/{org.id}/pronos"
    assert record.__dict__["status"] == 422
    assert record.__dict__["code"] == "validation_error"
    assert record.__dict__["fields"] == {"closes_at": "past"}
    assert record.__dict__["account_id"] == str(hugo.account.id)
    assert QUESTION not in str(record.__dict__)
    assert "secret" not in str(record.__dict__)


async def test_a_malformed_body_is_logged(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    data = await body(hugo.client, str(org.id))
    del data["question"]
    data["options"] = [QUESTION, "Monaco"]
    records.clear()
    refused = await hugo.client.post(f"/api/orgs/{org.id}/pronos", json=data)
    assert refused.status_code == 422
    assert refused.json()["error"]["fields"] == {"question": "missing"}

    record = only_request(records)
    assert record.levelno == logging.WARNING
    assert record.__dict__["status"] == 422
    assert record.__dict__["code"] == "validation_error"
    assert record.__dict__["fields"] == {"question": "missing"}
    assert QUESTION not in str(record.__dict__)


async def test_a_404_is_logged_with_its_code(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    cami = await person(org, "reader")
    records.clear()
    missing = await cami.client.get(
        f"/api/orgs/{org.id}/pronos/00000000-0000-0000-0000-000000000000"
    )
    assert missing.status_code == 404

    record = only_request(records)
    assert record.levelno == logging.WARNING
    assert record.__dict__["status"] == 404
    assert record.__dict__["code"] == "not_found"
    assert "fields" not in record.__dict__


async def test_an_unknown_route_is_logged(db: None, records: list[logging.LogRecord]) -> None:
    async with anonymous() as client:
        missing = await client.get("/api/nowhere")
    assert missing.status_code == 404
    record = only_request(records)
    assert (record.__dict__["path"], record.__dict__["code"]) == ("/api/nowhere", "not_found")
    assert "account_id" not in record.__dict__


async def test_a_csrf_refusal_is_logged(db: None, records: list[logging.LogRecord]) -> None:
    async with anonymous(Origin="https://ailleurs.example") as client:
        refused = await client.post("/api/auth/logout")
    assert refused.status_code == 403
    record = only_request(records)
    assert record.levelno == logging.WARNING
    assert record.__dict__["method"] == "POST"
    assert record.__dict__["status"] == 403
    assert record.__dict__["code"] == "forbidden"
    assert "ailleurs" not in str(record.__dict__)


async def test_an_unhandled_exception_is_logged_with_its_trace(
    db: None, records: list[logging.LogRecord]
) -> None:
    from sibylle.main import create_app

    app = create_app()

    async def boom() -> None:
        raise RuntimeError("boom")

    app.add_api_route("/api/boom", boom)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="https://testserver",
    ) as client:
        failed = await client.get("/api/boom")
    assert failed.status_code == 500

    record = only_request(records)
    assert record.levelno == logging.ERROR
    assert record.__dict__["status"] == 500
    assert record.__dict__["path"] == "/api/boom"
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)


async def test_the_healthcheck_is_not_logged(db: None, records: list[logging.LogRecord]) -> None:
    async with anonymous() as client:
        assert (await client.get("/api/health")).status_code == 200
    assert [r for r in records if r.getMessage() == "request"] == []


async def test_the_query_string_is_not_logged(db: None, records: list[logging.LogRecord]) -> None:
    async with anonymous() as client:
        await client.get("/api/auth/callback?code=code-secret-oidc&state=etat-secret")
    record = only_request(records)
    assert record.__dict__["path"] == "/api/auth/callback"
    assert "code-secret-oidc" not in str(record.__dict__)
    assert "etat-secret" not in str(record.__dict__)


async def test_a_public_card_token_is_masked(db: None, records: list[logging.LogRecord]) -> None:
    async with anonymous() as client:
        missing = await client.get("/api/public/cards/jeton-de-carte-secret")
    assert missing.status_code == 404
    record = only_request(records)
    assert record.__dict__["path"] == "/api/public/cards/{token}"
    assert "jeton-de-carte-secret" not in str(record.__dict__)


def test_uvicorn_websocket_lines_are_filtered_out() -> None:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    uvicorn = logging.getLogger("uvicorn.error")
    filters, uvicorn_level = uvicorn.filters[:], uvicorn.level
    seen: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record)

    collect = Collect()
    try:
        configure_logging("info")
        configure_logging("info")  # once more, as each create_app() does: one filter
        uvicorn.setLevel(logging.INFO)  # a live_server before may have left it at WARNING
        uvicorn.addHandler(collect)
        uvicorn.info('%s - "WebSocket %s" [accepted]', "203.0.113.7:5000", "/api/ws")
        uvicorn.info('%s - "WebSocket %s" 403', "203.0.113.7:5000", "/api/ws")
        uvicorn.info("Application startup complete.")
    finally:
        uvicorn.removeHandler(collect)
        uvicorn.filters[:] = filters
        uvicorn.setLevel(uvicorn_level)
        root.handlers[:] = handlers
        root.setLevel(level)
    assert [r.getMessage() for r in seen] == ["Application startup complete."]


async def test_websocket_connections_are_logged_without_address(
    live_server: str, make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    cami = await person(org, "reader")
    url = f"ws://{live_server}/api/ws"
    cookie = {"Cookie": f"sibylle_session={cami.client.cookies.get('sibylle_session')}"}

    with pytest.raises(websockets.exceptions.InvalidStatus):
        await websockets.connect(url, origin="https://ailleurs.example")  # type: ignore[arg-type]
    anonymous_ws = await websockets.connect(url, origin=ORIGIN)  # type: ignore[arg-type]
    await asyncio.wait_for(anonymous_ws.wait_closed(), timeout=5)
    signed_in = await websockets.connect(
        url,
        origin=ORIGIN,  # type: ignore[arg-type]
        additional_headers=cookie,
    )
    await signed_in.close()
    await asyncio.sleep(0.3)

    lines = [r for r in records if r.name == "sibylle.realtime.ws"]
    assert [(r.getMessage(), r.levelno, r.__dict__.get("reason")) for r in lines] == [
        ("websocket refused", logging.WARNING, "origin"),
        ("websocket refused", logging.WARNING, "unauthenticated"),
        ("websocket opened", logging.INFO, None),
        ("websocket closed", logging.INFO, None),
    ]
    assert lines[2].__dict__["account_id"] == str(cami.account.id)
    assert lines[3].__dict__["account_id"] == str(cami.account.id)
    assert isinstance(lines[3].__dict__["duration_ms"], int)
    assert "127.0.0.1" not in str([r.__dict__ for r in lines])

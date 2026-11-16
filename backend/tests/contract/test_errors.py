"""Every 422 leaves a log line naming the refused fields, never their values."""

import logging
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from tests.conftest import MakeOrg, MakePerson

from sibylle import clock

pytestmark = pytest.mark.contract

QUESTION = "Qui gagne le derby secret ?"


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[logging.LogRecord]]:
    # create_app() replaces the root handlers: keep them, and listen on the logger itself.
    monkeypatch.setattr("sibylle.main.configure_logging", lambda _level: None)
    seen: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record)

    logger = logging.getLogger("sibylle.api.errors")
    handler = Collect(level=logging.WARNING)
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
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


def only_validation_record(records: list[logging.LogRecord]) -> logging.LogRecord:
    found = [r for r in records if r.getMessage() == "validation error"]
    assert len(found) == 1
    record = found[0]
    assert record.levelno == logging.WARNING
    assert QUESTION not in str(record.__dict__)
    return record


async def test_a_refused_prono_is_logged(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    past = (clock.now() - timedelta(days=1)).isoformat()
    refused = await hugo.client.post(
        f"/api/orgs/{org.id}/pronos?secret=1",
        json=await body(hugo.client, str(org.id), closes_at=past),
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["fields"] == {"closes_at": "past"}

    record = only_validation_record(records)
    assert record.__dict__["method"] == "POST"
    assert record.__dict__["path"] == f"/api/orgs/{org.id}/pronos"
    assert record.__dict__["status"] == 422
    assert record.__dict__["fields"] == {"closes_at": "past"}


async def test_a_malformed_body_is_logged(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    data = await body(hugo.client, str(org.id))
    del data["question"]
    data["options"] = [QUESTION, "Monaco"]
    refused = await hugo.client.post(f"/api/orgs/{org.id}/pronos", json=data)
    assert refused.status_code == 422
    assert refused.json()["error"]["fields"] == {"question": "missing"}

    record = only_validation_record(records)
    assert record.__dict__["method"] == "POST"
    assert record.__dict__["path"] == f"/api/orgs/{org.id}/pronos"
    assert record.__dict__["status"] == 422
    assert record.__dict__["fields"] == {"question": "missing"}


async def test_other_errors_are_not_logged(
    make_org: MakeOrg, person: MakePerson, records: list[logging.LogRecord]
) -> None:
    org = await make_org()
    cami = await person(org, "reader")
    missing = await cami.client.get(
        f"/api/orgs/{org.id}/pronos/00000000-0000-0000-0000-000000000000"
    )
    assert missing.status_code == 404
    assert records == []

"""JSON logs on standard output, one object per line."""

import json
import logging
import sys
from datetime import UTC, datetime

_STANDARD = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class NoWebSocketAddress(logging.Filter):
    """Drops uvicorn's `<address> - "WebSocket /api/ws" [accepted]` lines (and their refusals),
    which name the visitor's address: the endpoint writes its own lines, without it
    (realtime/ws.py)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (isinstance(record.msg, str) and record.msg.startswith('%s - "WebSocket '))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # httpx notes each call to Keycloak at INFO; its failures come through services/keycloak.py.
    uvicorn = logging.getLogger("uvicorn.error")
    if not any(isinstance(f, NoWebSocketAddress) for f in uvicorn.filters):
        uvicorn.addFilter(NoWebSocketAddress())
    logging.getLogger("httpx").setLevel(max(root.level, logging.WARNING))

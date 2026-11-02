"""Server-side texts (errors, e-mail subjects, push notifications): one catalog per locale."""

import json
from functools import cache
from pathlib import Path
from typing import Any

DEFAULT_LOCALE = "fr"
_DIR = Path(__file__).parent


@cache
def _catalog(locale: str) -> dict[str, Any]:
    path = _DIR / f"{locale}.json"
    if not path.exists():
        path = _DIR / f"{DEFAULT_LOCALE}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def t(key: str, locale: str = DEFAULT_LOCALE, **params: Any) -> str:
    """The text at a dotted key, with `{name}` placeholders filled in; the key itself if missing."""
    node: Any = _catalog(locale)
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return key
        node = node[part]
    return str(node).format(**params) if params else str(node)

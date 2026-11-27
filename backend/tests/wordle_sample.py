"""A small word file for Wordle, in the format of wordle-fr.json (domain/wordle_words.py), and a
download that serves it, for the tests: never the real file, never the network.

Its six tiers hold 20 made-up words each, from `aaaaa` in the first to `faaat` in the last: the
first letter of a word is its tier. Its 1 000 guesses are the answers and words beginning with
`z`.
"""

import json
from dataclasses import dataclass
from typing import Any

from sibylle.services.wordle_lists import DownloadFailed

TIERS = 6
PER_TIER = 20
GUESSES = 1_000
_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _four(number: int) -> str:
    """Four letters for a number: 0 is `aaaa`, 1 `aaab`, 26 `aaba`."""
    return "".join(_LETTERS[number // 26**power % 26] for power in (3, 2, 1, 0))


def word(tier: int, index: int = 0) -> str:
    """The word of rank `index` (from 0) in the tier of rank `tier` (from 1)."""
    return _LETTERS[tier - 1] + _four(index)


def tier_words(tier: int) -> list[str]:
    return [word(tier, index) for index in range(PER_TIER)]


def words_of(*tiers: int) -> set[str]:
    return {each for tier in tiers for each in tier_words(tier)}


def sample() -> dict[str, Any]:
    """The file as decoded JSON, fresh each time: change it to make another version."""
    answers = [
        {
            "id": f"tranche-{rank}",
            "min": 2.0 ** (TIERS - rank),
            "max": None if rank == 1 else 2.0 ** (TIERS - rank + 1),
            "count": PER_TIER,
            "words": [
                {"word": each, "spelling": each, "freq": 2.0 ** (TIERS - rank), "kind": ["noun"]}
                for each in tier_words(rank)
            ],
        }
        for rank in range(1, TIERS + 1)
    ]
    others = ["z" + _four(index) for index in range(GUESSES - TIERS * PER_TIER)]
    return {
        "name": "Mots d'essai",
        "answers": answers,
        "guesses": sorted(words_of(*range(1, TIERS + 1)) | set(others)),
    }


def encoded(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=1).encode()


@dataclass
class FakeWordleFile:
    """What the tests' download serves: no file at first, as if the network failed, until a test
    puts one in (`serve`)."""

    content: bytes | None = None
    downloads: int = 0

    def serve(self, data: dict[str, Any] | bytes | None) -> None:
        """Serves this file from now on; None makes the download fail."""
        self.content = encoded(data) if isinstance(data, dict) else data

    async def download(self, url: str) -> bytes:
        self.downloads += 1
        if self.content is None:
            raise DownloadFailed("the tests' network is off")
        return self.content

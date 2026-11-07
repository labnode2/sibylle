"""Pixel images: avatars, newsroom logos and Pixel mystère drawings.

A drawing is `{"size": 16 | 32, "palette": "base-v1", "pixels": "<base64>"}`: one byte per pixel,
each an index in the palette, 0 being transparent. The same palette lives in
frontend/src/ui/palette.ts.
"""

import base64
import binascii
from collections.abc import Collection
from typing import Any

PALETTE_NAME = "base-v1"
SIZES = (16, 32)

# 1–32: drawn from the Gazette avatars of the canvas, open to everyone.
_BASE = (
    "#1d1b2b", "#3c2a24", "#3a3d45", "#5c3a2e", "#2a2f7a", "#71442b", "#22804a", "#a8432a",
    "#885837", "#3a3ea9", "#33a25f", "#987333", "#d44647", "#c56938", "#4a50d0", "#c99a18",
    "#d39a6a", "#e2b54a", "#f2c230", "#fb8194", "#e2a48e", "#ffb066", "#c6f06a", "#9be3b4",
    "#8fb0ff", "#f3c9a5", "#ffe28a", "#f5d0b0", "#c9cbff", "#d9dbff", "#ffd0e4", "#f4f6fb",
)  # fmt: skip
# 33–48: the vivid PICO-8 colours, unlocked with laurels.
_UNLOCKABLE = (
    "#000000", "#1d2b53", "#7e2553", "#008751", "#ab5236", "#5f574f", "#c2c3c7", "#fff1e8",
    "#ff004d", "#ffa300", "#ffec27", "#00e436", "#29adff", "#83769c", "#ff77a8", "#ffccaa",
)  # fmt: skip
# 49–52: rare colours of the crystal ball, unlocked by secret codes.
_RARE = ("#6e74ff", "#8f94ff", "#6267e8", "#8a6a12")

COLORS: tuple[str | None, ...] = (None, *_BASE, *_UNLOCKABLE, *_RARE)
BASE_INDICES = frozenset(range(1, 1 + len(_BASE)))
UNLOCKABLE_INDICES = frozenset(range(1 + len(_BASE), 1 + len(_BASE) + len(_UNLOCKABLE)))
RARE_INDICES = frozenset(range(1 + len(_BASE) + len(_UNLOCKABLE), len(COLORS)))

# The colours an avatar gets for free: the skin tones (which also make hair and beards), then ink,
# paper, red, indigo and gold. The other colours of the base palette are sold in the collection
# for avatars; newsroom logos and Pixel mystère drawings keep the whole base palette.
SKIN_INDICES = frozenset({2, 4, 6, 9, 14, 17, 21, 26, 28})
AVATAR_INDICES = SKIN_INDICES | {1, 13, 15, 19, 32}
SOLD_BASE_INDICES = BASE_INDICES - AVATAR_INDICES


class PixelImageError(ValueError):
    pass


def decode(data: dict[str, Any]) -> bytes:
    try:
        return base64.b64decode(data["pixels"], validate=True)
    except (binascii.Error, ValueError, TypeError) as error:
        raise PixelImageError("pixels must be base64") from error


def encode(size: int, indices: bytes) -> dict[str, Any]:
    return {"size": size, "palette": PALETTE_NAME, "pixels": base64.b64encode(indices).decode()}


def validate_pixel_image(
    data: object, unlocked: Collection[int] = (), base: Collection[int] = BASE_INDICES
) -> dict[str, Any]:
    """Checks a drawing; colours beyond `base` (the base palette, or an avatar's free colours)
    must be in `unlocked`."""
    if not isinstance(data, dict) or set(data) != {"size", "palette", "pixels"}:
        raise PixelImageError("a drawing has exactly size, palette and pixels")
    size = data["size"]
    if type(size) is not int or size not in SIZES:
        raise PixelImageError("size must be 16 or 32")
    if data["palette"] != PALETTE_NAME:
        raise PixelImageError(f"palette must be {PALETTE_NAME}")
    if not isinstance(data["pixels"], str):
        raise PixelImageError("pixels must be base64")
    pixels = decode(data)
    if len(pixels) != size * size:
        raise PixelImageError(f"a {size}×{size} drawing has {size * size} pixels")
    allowed = set(base) | set(unlocked)
    for index in set(pixels):
        if index != 0 and (index >= len(COLORS) or index not in allowed):
            raise PixelImageError(f"colour {index} is not available")
    return {"size": size, "palette": PALETTE_NAME, "pixels": data["pixels"]}

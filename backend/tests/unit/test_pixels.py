import base64

import pytest

from sibylle.domain.content import AVATAR_TEMPLATES
from sibylle.domain.pixels import (
    AVATAR_INDICES,
    BASE_INDICES,
    COLORS,
    RARE_INDICES,
    SKIN_INDICES,
    SOLD_BASE_INDICES,
    UNLOCKABLE_INDICES,
    PixelImageError,
    decode,
    validate_pixel_image,
)

pytestmark = pytest.mark.unit


def image(indices: list[int], size: int = 16, palette: str = "base-v1") -> dict[str, object]:
    return {"size": size, "palette": palette, "pixels": base64.b64encode(bytes(indices)).decode()}


def test_the_palette_has_base_unlockable_and_rare_colours() -> None:
    assert COLORS[0] is None
    assert BASE_INDICES == frozenset(range(1, 33))
    assert UNLOCKABLE_INDICES == frozenset(range(33, 49))
    assert RARE_INDICES == frozenset(range(49, 53))
    assert len(COLORS) == 53
    assert all(c is not None and c.startswith("#") and len(c) == 7 for c in COLORS[1:])


def test_a_drawing_in_base_colours_is_valid() -> None:
    data = image([0, 1, 32, 15] * 64)
    assert validate_pixel_image(data) == data


def test_a_32_by_32_drawing_is_valid() -> None:
    assert validate_pixel_image(image([1] * 1024, size=32))["size"] == 32


@pytest.mark.parametrize(
    "data",
    [
        image([1] * 255),  # one pixel short
        image([1] * 257),
        image([1] * 576, size=24),  # unsupported size
        image([1] * 256, palette="pico-8"),
        image([53] + [1] * 255),  # unknown index
        {"size": 16, "palette": "base-v1", "pixels": "!!pas du base64!!"},
        {"size": 16, "palette": "base-v1"},
        {"size": "16", "palette": "base-v1", "pixels": base64.b64encode(bytes(256)).decode()},
        "pas un dessin",
    ],
)
def test_malformed_drawings_are_refused(data: object) -> None:
    with pytest.raises(PixelImageError):
        validate_pixel_image(data)


@pytest.mark.parametrize("index", [33, 48, 49, 52])
def test_extra_colours_need_to_be_unlocked(index: int) -> None:
    data = image([index] + [1] * 255)
    with pytest.raises(PixelImageError):
        validate_pixel_image(data)
    assert validate_pixel_image(data, unlocked={index}) == data


def test_an_avatar_gets_the_skin_tones_and_five_colours_for_free() -> None:
    assert AVATAR_INDICES == SKIN_INDICES | {1, 13, 15, 19, 32}
    assert AVATAR_INDICES < BASE_INDICES
    assert SOLD_BASE_INDICES == BASE_INDICES - AVATAR_INDICES
    assert len(SOLD_BASE_INDICES) == 18
    sold = sorted(SOLD_BASE_INDICES)[0]
    with pytest.raises(PixelImageError):
        validate_pixel_image(image([sold] * 256), base=AVATAR_INDICES)
    assert validate_pixel_image(image([sold] * 256), {sold}, AVATAR_INDICES)
    # The rest of the drawings keep the whole base palette.
    assert validate_pixel_image(image([sold] * 256))


def test_the_default_avatars_use_only_free_colours() -> None:
    assert len(AVATAR_TEMPLATES) == 10
    for template in AVATAR_TEMPLATES:
        validate_pixel_image(template["image"], base=AVATAR_INDICES)
        assert set(decode(template["image"])) - {0} <= AVATAR_INDICES, template["name"]

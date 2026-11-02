"""Platform content shared by every newsroom: avatar and logo templates, card backgrounds, the
default charter. The templates come from the Gazette canvas atlas (templates.json)."""

import json
from pathlib import Path
from typing import Any

from sybille.domain.pixels import encode

_TEMPLATES = json.loads((Path(__file__).parent / "templates.json").read_text(encoding="utf-8"))

# Avatars offered when joining a newsroom (Cami, Inès, Hugo, Léo, Manon's cat, Yanis, Chloé).
AVATAR_TEMPLATES: list[dict[str, Any]] = _TEMPLATES["avatars"]
# Starting point for a newsroom's logo.
LOGO_TEMPLATES: list[dict[str, Any]] = _TEMPLATES["logos"]


def _silhouette() -> dict[str, Any]:
    """A neutral grey bust, for the members of a deleted account."""
    grey, light = 3, 29  # base-v1: #3a3d45 and #c9cbff
    pixels = bytearray([light] * 256)
    for y in range(16):
        for x in range(16):
            head = (x - 7.5) ** 2 + (y - 6) ** 2 <= 12
            shoulders = y >= 12 and abs(x - 7.5) <= 6.5
            if head or shoulders:
                pixels[y * 16 + x] = grey
    return encode(16, bytes(pixels))


DEFAULT_AVATAR: dict[str, Any] = _silhouette()

# Keys of the newsroom card backgrounds; the gradients live in frontend/src/styles/backgrounds.css.
BACKGROUND_KEYS = frozenset({"mer", "aube", "nuit", "foret", "papier", "brique"})

DEFAULT_CHARTER = """\
Sybille se joue entre collègues et entre proches, sans argent ni lot : les lauriers ne \
s'échangent contre rien de réel.

En rejoignant la rédaction, je m'engage à :
- respecter les autres membres, dans les pronos comme dans les réactions ;
- ne pas proposer de prono sur la santé ou la vie privée des collègues, ni sur la politique ;
- signaler un résultat erroné plutôt que de m'en prendre à qui l'a désigné.

La rédaction en chef modère la rédaction : elle peut corriger un résultat, annuler un prono \
et traiter les signalements."""

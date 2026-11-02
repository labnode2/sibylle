"""Platform content the interface needs before any newsroom exists: avatar and logo templates,
card backgrounds and the default charter."""

from fastapi import APIRouter
from pydantic import BaseModel

from sybille.api.schemas import PixelImage
from sybille.domain.content import (
    AVATAR_TEMPLATES,
    BACKGROUND_KEYS,
    DEFAULT_CHARTER,
    LOGO_TEMPLATES,
)

router = APIRouter(tags=["content"])


class Template(BaseModel):
    key: str
    name: str
    image: PixelImage


class Content(BaseModel):
    avatars: list[Template]
    logos: list[Template]
    backgrounds: list[str]
    charter: str


@router.get("/content")
async def get_content() -> Content:
    return Content.model_validate(
        {
            "avatars": AVATAR_TEMPLATES,
            "logos": LOGO_TEMPLATES,
            "backgrounds": sorted(BACKGROUND_KEYS),
            "charter": DEFAULT_CHARTER,
        }
    )

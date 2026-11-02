"""Images attached to pronos (research.md R10): re-encoded as WebP of 1,200 px at most, without
metadata, stored under UPLOAD_DIR with a random name, read by the newsroom's members only."""

import asyncio
import io
import uuid
from pathlib import Path

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from sybille.api.errors import AppError
from sybille.config import get_settings
from sybille.db.models import Membership, Upload

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1200


def _reencode(data: bytes) -> tuple[bytes, int, int]:
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = source.convert("RGBA" if "A" in source.getbands() else "RGB")
    except Exception as error:  # not an image, truncated, too many pixels…
        raise AppError("validation_error", {"file": "invalid"}) from error
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    # Saving without `exif` drops the metadata (camera, place…).
    image.save(out, "WEBP", quality=85)
    return out.getvalue(), image.width, image.height


async def save_upload(session: AsyncSession, member: Membership, data: bytes) -> Upload:
    if len(data) > MAX_BYTES:
        raise AppError("too_large")
    webp, width, height = await asyncio.to_thread(_reencode, data)
    key = f"{member.org_id}/{uuid.uuid4().hex}.webp"
    path = get_settings().upload_dir / key
    await asyncio.to_thread(_write, path, webp)
    upload = Upload(
        org_id=member.org_id,
        uploaded_by=member.id,
        width=width,
        height=height,
        size_bytes=len(webp),
        storage_key=key,
    )
    session.add(upload)
    await session.flush()
    return upload


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


async def upload_path(session: AsyncSession, member: Membership, upload_id: uuid.UUID) -> Path:
    upload = await session.get(Upload, upload_id)
    if upload is None or upload.org_id != member.org_id:
        raise AppError("not_found")
    return get_settings().upload_dir / upload.storage_key

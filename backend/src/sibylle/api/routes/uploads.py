"""Images attached to pronos."""

import uuid

from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.errors import AppError
from sibylle.api.schemas import UploadOut
from sibylle.services import uploads

router = APIRouter(prefix="/orgs/{org_id}/uploads", tags=["uploads"])


@router.post("", status_code=201)
async def upload_image(
    org_id: uuid.UUID, file: UploadFile, member: CurrentMember, session: Db
) -> UploadOut:
    data = await file.read(uploads.MAX_BYTES + 1)
    upload = await uploads.save_upload(session, member, data)
    return UploadOut(id=upload.id, width=upload.width, height=upload.height)


@router.get("/{upload_id}", response_class=FileResponse)
async def get_image(
    org_id: uuid.UUID, upload_id: uuid.UUID, member: CurrentMember, session: Db
) -> FileResponse:
    path = await uploads.upload_path(session, member, upload_id)
    if not path.exists():
        raise AppError("not_found")
    # The name never changes for a given image: the browser may keep it, privately.
    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )

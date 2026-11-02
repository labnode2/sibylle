from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from sybille.db.session import transaction

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["ok", "error"]


@router.get("/health")
async def health(response: Response) -> Health:
    try:
        async with transaction() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return Health(status="error", db="error")
    return Health(status="ok", db="ok")

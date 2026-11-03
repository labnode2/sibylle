"""The signed-in account: its own data and its newsrooms, the export of everything about it,
and its deletion (US11)."""

from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.deps import SESSION_COOKIE, CurrentAccount, Db
from sibylle.api.schemas import AccountDeletion, Me, MePatch, PasswordChange
from sibylle.db.models import Account, Membership, Organisation
from sibylle.domain.seasons import PARIS
from sibylle.services import accounts, coins, export

router = APIRouter(tags=["me"])


async def me_of(session: AsyncSession, account: Account) -> Me:
    rows = await session.execute(
        select(Organisation, Membership)
        .join(Membership, Membership.org_id == Organisation.id)
        .where(
            Membership.account_id == account.id,
            Membership.status == "active",
            Organisation.deleted_at.is_(None),
        )
        .order_by(Membership.joined_at)
    )
    memberships = [(org, member) for org, member in rows.all()]
    in_play = await coins.in_play(session, [member.id for _, member in memberships])
    return Me.of(account, memberships, in_play)


@router.get("/me")
async def get_me(account: CurrentAccount, session: Db) -> Me:
    return await me_of(session, account)


@router.patch("/me")
async def update_me(body: MePatch, account: CurrentAccount, session: Db) -> Me:
    accounts.update_account(account, body.model_dump(exclude_unset=True))
    return await me_of(session, account)


@router.post("/me/password", status_code=204)
async def change_password(
    body: PasswordChange, request: Request, account: CurrentAccount, session: Db
) -> None:
    await accounts.change_password(
        session,
        account,
        body.current_password,
        body.new_password,
        request.cookies.get(SESSION_COOKIE),
    )


@router.get(
    "/me/export",
    response_class=JSONResponse,
    responses={200: {"description": "Un fichier JSON à télécharger"}},
)
async def export_my_data(account: CurrentAccount, session: Db) -> JSONResponse:
    data: dict[str, Any] = await export.export(session, account)
    day = clock.now().astimezone(PARIS).date().isoformat()
    return JSONResponse(
        jsonable_encoder(data),
        headers={"Content-Disposition": f'attachment; filename="sibylle-mes-donnees-{day}.json"'},
    )


@router.delete("/me", status_code=204)
async def delete_me(
    body: AccountDeletion, response: Response, account: CurrentAccount, session: Db
) -> None:
    await accounts.delete_account(session, account)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")

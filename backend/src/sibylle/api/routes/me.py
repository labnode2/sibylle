"""The signed-in account: its own data and its newsrooms."""

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle.api.deps import SESSION_COOKIE, CurrentAccount, Db
from sibylle.api.schemas import Me, MePatch, PasswordChange
from sibylle.db.models import Account, Membership, Organisation
from sibylle.services import accounts, coins

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

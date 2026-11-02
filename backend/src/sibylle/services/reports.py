"""Reports: a member flags a wrong result or a content; the editors hear of it at once."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle.api.errors import AppError
from sibylle.db.models import Membership, Report
from sibylle.domain.permissions import Action, Role, can
from sibylle.realtime import bus
from sibylle.services.pronos import get_prono


async def create_report(
    session: AsyncSession,
    member: Membership,
    prono_id: uuid.UUID,
    kind: str,
    message: str | None,
) -> Report:
    if not can(member.role, Action.REPORT):
        raise AppError("forbidden")
    prono = await get_prono(session, member, prono_id)
    report = Report(
        org_id=prono.org_id,
        prono_id=prono.id,
        reporter_membership_id=member.id,
        kind=kind,
        message=message or None,
    )
    session.add(report)
    await session.flush()
    editors = (
        await session.scalars(
            select(Membership.account_id).where(
                Membership.org_id == prono.org_id,
                Membership.role == Role.EDITOR.value,
                Membership.status == "active",
            )
        )
    ).all()
    if editors:
        await bus.publish(
            session,
            "report.created",
            {"report_id": str(report.id), "prono_id": str(prono.id), "kind": kind},
            topics=[f"me:{account_id}" for account_id in editors],
        )
    return report

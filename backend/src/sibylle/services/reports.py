"""Reports: a member flags a wrong result or a content; the editors hear of it at once, handle it,
and its author is told."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Membership, Prono, Report
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


async def list_reports(
    session: AsyncSession, org_id: uuid.UUID, state: str | None
) -> list[tuple[Report, Prono, Membership]]:
    """The newsroom's reports, newest first, with their prono and their author."""
    query = (
        select(Report, Prono, Membership)
        .join(Prono, Prono.id == Report.prono_id)
        .join(Membership, Membership.id == Report.reporter_membership_id)
        .where(Report.org_id == org_id)
    )
    if state:
        query = query.where(Report.state == state)
    rows = await session.execute(query.order_by(Report.created_at.desc(), Report.id.desc()))
    return [(report, prono, author) for report, prono, author in rows]


async def handle_report(
    session: AsyncSession,
    editor: Membership,
    report_id: uuid.UUID,
    state: str,
    note: str | None,
) -> Report:
    """Closes an open report as resolved (after a correction, say) or dismissed."""
    report = await session.scalar(
        select(Report)
        .where(Report.id == report_id, Report.org_id == editor.org_id)
        .with_for_update()
    )
    if report is None:
        raise AppError("not_found")
    if report.state != "open":
        raise AppError("invalid_state")
    report.state = state
    report.handled_by = editor.id
    report.handled_at = clock.now()
    report.resolution_note = note or None
    await session.flush()
    author = await session.get(Membership, report.reporter_membership_id)
    assert author is not None
    await bus.publish(
        session,
        "report.handled",
        {"report_id": str(report.id), "prono_id": str(report.prono_id), "state": state},
        topics=[f"me:{author.account_id}"],
    )
    return report

"""Demo data (`sibylle seed-demo`): the « Sophia Office » newsroom, its five members and a few
pronos in every state (open, closed, resolved, relaunched, cancelled).

Idempotent, and refused in production. Accounts and password are listed in backend/seed/README.md.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.config import get_settings
from sibylle.db.models import Account, Membership, Organisation, Prono, PronoOption, Section
from sibylle.db.session import transaction
from sibylle.domain.content import AVATAR_TEMPLATES
from sibylle.domain.lifecycle import State
from sibylle.services import bets, coins, orgs, pronos, results
from sibylle.services.security import hash_password

DEMO_PASSWORD = "lauriers-de-demo"
ORG_TITLE = "Sophia Office"

# (pseudo, e-mail, role, avatar template)
PEOPLE = [
    ("Inès", "ines@demo.sibylle.test", "editor", "t1"),
    ("Hugo", "hugo@demo.sibylle.test", "journalist", "t2"),
    ("Cami", "cami@demo.sibylle.test", "reader", "t0"),
    ("Léo", "leo@demo.sibylle.test", "reader", "t3"),
    ("Manon", "manon@demo.sibylle.test", "reader", "t4"),
]


SECTIONS = ["Général", "Bureau", "Foot"]
FIRST_QUESTION = "Qui gagnera le tournoi de baby-foot ?"


def _avatar(key: str) -> dict[str, object]:
    return next(t["image"] for t in AVATAR_TEMPLATES if t["key"] == key)


class _Demo:
    """Publishes pronos and places bets through the same services as the API."""

    def __init__(self, session: AsyncSession, org: Organisation) -> None:
        self.session = session
        self.org = org
        self.members: dict[str, Membership] = {}
        self.sections: dict[str, Section] = {}

    async def load(self) -> None:
        rows = await self.session.scalars(
            select(Membership).where(Membership.org_id == self.org.id)
        )
        self.members = {m.pseudo: m for m in rows}
        for position, name in enumerate(SECTIONS):
            section = await self.session.scalar(
                select(Section).where(Section.org_id == self.org.id, Section.name == name)
            )
            if section is None:
                section = Section(org_id=self.org.id, name=name, position=position)
                self.session.add(section)
                await self.session.flush()
            self.sections[name] = section

    async def publish(
        self, author: str, section: str, kind: str, question: str, **fields: Any
    ) -> Prono:
        fields.setdefault("base_gain", 20)
        if not fields.get("open_ended"):
            fields.setdefault("closes_at", clock.now() + timedelta(days=3))
        return await pronos.create_prono(
            self.session,
            self.members[author],
            {"kind": kind, "question": question, "section_id": self.sections[section].id} | fields,
        )

    async def option(self, prono: Prono, label: str) -> Any:
        return await self.session.scalar(
            select(PronoOption.id).where(
                PronoOption.prono_id == prono.id, PronoOption.label == label
            )
        )

    async def bet(
        self, pseudo: str, prono: Prono, stake: int, answer: str | Decimal | date
    ) -> None:
        await bets.place_bet(
            self.session,
            self.members[pseudo],
            prono.id,
            option_id=await self.option(prono, answer) if isinstance(answer, str) else None,
            number_value=answer if isinstance(answer, Decimal) else None,
            date_value=answer if isinstance(answer, date) else None,
            stake=stake,
        )

    async def close(self, prono: Prono) -> None:
        """What the worker does at closing time."""
        prono.closes_at = clock.now() - timedelta(minutes=5)
        await pronos.set_state(self.session, prono, State.CLOSED, "closed")

    async def seed(self) -> None:
        today = clock.now().date()
        foosball = await self.publish(
            "Hugo", "Bureau", "choice", FIRST_QUESTION, options=["Produit", "Tech", "Ventes"]
        )
        await self.bet("Cami", foosball, 20, "Tech")
        await self.bet("Léo", foosball, 10, "Produit")
        await self.bet("Manon", foosball, 0, "Tech")

        coffees = await self.publish(
            "Hugo",
            "Bureau",
            "number",
            "Combien de cafés Hugo boira-t-il jeudi ?",
            number_unit="cafés",
        )
        await self.bet("Cami", coffees, 10, Decimal("4"))
        await self.bet("Inès", coffees, 0, Decimal("6"))

        machine = await self.publish(
            "Inès",
            "Bureau",
            "date",
            "Quand la machine à café sera-t-elle réparée ?",
            open_ended=True,
            closes_at=None,
        )
        await self.bet("Léo", machine, 10, today + timedelta(days=10))

        deadline = await self.publish(
            "Hugo", "Général", "yes_no", "Le bouclage de vendredi finira-t-il avant 20 h ?"
        )
        await self.bet("Cami", deadline, 10, "Oui")
        await self.bet("Léo", deadline, 20, "Non")
        await self.bet("Manon", deadline, 0, "Oui")
        await self.close(deadline)

        derby = await self.publish(
            "Hugo", "Foot", "choice", "Nice ou Monaco samedi ?", options=["Nice", "Nul", "Monaco"]
        )
        await self.bet("Cami", derby, 10, "Nice")
        await self.bet("Léo", derby, 10, "Monaco")
        await self.bet("Manon", derby, 20, "Nice")
        await self.bet("Inès", derby, 10, "Nul")
        await self.close(derby)
        await results.resolve(
            self.session,
            self.members["Hugo"],
            derby.id,
            results.Result(correct_option_ids=[await self.option(derby, "Nice")]),
        )

        lens = await self.publish("Hugo", "Foot", "yes_no", "L'OM battra-t-il Lens ?")
        await self.bet("Manon", lens, 10, "Oui")
        await self.close(lens)
        await results.relaunch(
            self.session,
            self.members["Hugo"],
            lens.id,
            closes_at=clock.now() + timedelta(days=5),
            result_expected_at=None,
            reason="Match reporté",
        )

        costumes = await self.publish(
            "Inès",
            "Bureau",
            "choice",
            "Qui gagnera le concours de déguisements ?",
            options=["Produit", "Tech", "Ventes"],
        )
        await self.bet("Léo", costumes, 15, "Ventes")
        await results.cancel(
            self.session, self.members["Inès"], costumes.id, "Concours reporté à l'an prochain"
        )


async def seed_demo() -> str:
    if get_settings().is_production:
        raise SystemExit("seed-demo est refusé en production")
    async with transaction() as session:
        accounts: dict[str, Account] = {}
        for pseudo, email, _, _ in PEOPLE:
            account = await session.scalar(select(Account).where(Account.email == email))
            if account is None:
                account = Account(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    first_name=pseudo,
                    last_name="Démo",
                    email_verified_at=clock.now(),
                )
                session.add(account)
                await session.flush()
            accounts[pseudo] = account

        ines = accounts["Inès"]
        org = await session.scalar(
            select(Organisation)
            .join(Membership, Membership.org_id == Organisation.id)
            .where(Organisation.title == ORG_TITLE, Membership.account_id == ines.id)
        )
        if org is None:
            org, _ = await orgs.create_org(
                session,
                ines,
                title=ORG_TITLE,
                background_key="mer",
                logo=None,
                pseudo="Inès",
                avatar=_avatar("t1"),
            )
        for pseudo, _, role, template in PEOPLE[1:]:
            exists = await session.scalar(
                select(Membership.id).where(
                    Membership.org_id == org.id, Membership.account_id == accounts[pseudo].id
                )
            )
            if exists is None:
                await orgs.add_member(
                    session,
                    org,
                    accounts[pseudo],
                    role=role,
                    pseudo=pseudo,
                    avatar=_avatar(template),
                )
        await session.flush()
        demo = _Demo(session, org)
        await demo.load()
        seeded = await session.scalar(
            select(Prono.id).where(Prono.org_id == org.id, Prono.question == FIRST_QUESTION)
        )
        if seeded is None:
            await demo.seed()
        # This week's conversion of gold laurels, so that the demo shows its coins and the good
        # news without waiting for Monday. Once per week, like the worker's.
        await coins.grant_week(session, org_id=org.id, arrived_before=clock.now())
        return f"{ORG_TITLE} : {len(PEOPLE)} membres, 7 pronos, code {org.access_code}"

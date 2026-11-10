"""Load test of a busy newsroom (T149, SC-002 and SC-004).

A newsroom of 100 members and 20 open pronos, made straight in the database of the app. Every
member opens a WebSocket that follows the newsroom and one prono, as the screen of that prono
does. Then, all of them at once: they open the app together, bet on the same prono in the same
instant (the burst), then go through the other pronos (open it, bet, back to the front page)
and end on the leaderboard, spending `--think` seconds on a screen on average (2 by default;
0 makes it a stress test, every member firing requests back to back). The script measures:

- the time of every HTTP answer, per route: its p95 must stay under 200 ms;
- the time from the moment a bet is sent to the moment each other member who watches that
  prono receives it on their WebSocket: under 2 s every time (SC-002).

Run it against the local app, from backend/, while `make dev` runs in another terminal (or
`make db` and `make api`):

    uv run python tests/load/run_load.py
    uv run python tests/load/run_load.py --api http://localhost:8010 --origin http://localhost:5199

`--api` is the server (port API_PORT of the Makefile, 8000 by default) and `--origin` the
address of the interface (http://UI_HOST:WEB_PORT), which the server checks. The script reads
DATABASE_URL like the server (deploy/.env). It exits with 1 when a threshold is missed or a
request fails. At the end the newsroom is deleted (only marked, as an editor deletes one) and
the sessions it opened are closed; `--keep` leaves both, to look at the newsroom in the app.
The accounts stay, with e-mails at @charge.sibylle.test. Refused in production.

`make api` serves with --reload: a file saved in backend/ during the run restarts the server,
and the run fails with lost requests and bets. Results depend on the machine; when the load
runs on the same one as the server, close what else uses the processor.
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import httpx
import websockets
from sqlalchemy import delete, select

from sibylle import clock
from sibylle.config import get_settings
from sibylle.db.models import (
    Account,
    AuthSession,
    Membership,
    Organisation,
    PronoOption,
    Section,
)
from sibylle.db.session import dispose_engine, transaction
from sibylle.domain.content import AVATAR_TEMPLATES
from sibylle.domain.ledger import starting_balance
from sibylle.services import ledger, orgs, pronos
from sibylle.services.security import new_token, token_hash

ROUTE_P95_MS = 200.0
BROADCAST_MAX_S = 2.0
# Seconds a member spends on a screen before the next one, on average.
DEFAULT_THINK = 2.0
EMAIL_DOMAIN = "charge.sibylle.test"


@dataclass
class Member:
    pseudo: str
    token: str
    watches: uuid.UUID


@dataclass
class Newsroom:
    org_id: uuid.UUID
    members: list[Member]
    # prono id → its option ids
    pronos: dict[uuid.UUID, list[uuid.UUID]]


@dataclass
class Report:
    # route template → durations in ms
    timings: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    # one per (bet, other member watching its prono), in s; None when it never came
    broadcasts: list[float | None] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    bets: int = 0
    sockets: int = 0
    elapsed: float = 0.0

    def p95(self, values: list[float]) -> float:
        return percentile(values, 95)

    def problems(self) -> list[str]:
        found = list(self.failures)
        for route, values in sorted(self.timings.items()):
            if self.p95(values) > ROUTE_P95_MS:
                found.append(f"p95 de {route} : {self.p95(values):.0f} ms > {ROUTE_P95_MS:.0f}")
        missing = sum(1 for delay in self.broadcasts if delay is None)
        if missing:
            found.append(f"{missing} pari(s) jamais reçu(s) par un membre qui regardait le prono")
        arrived = [delay for delay in self.broadcasts if delay is not None]
        if arrived and max(arrived) > BROADCAST_MAX_S:
            found.append(f"diffusion la plus lente : {max(arrived):.2f} s > {BROADCAST_MAX_S} s")
        if not self.broadcasts:
            found.append("aucune diffusion mesurée")
        return found

    def summary(self) -> str:
        every = [value for values in self.timings.values() for value in values]
        lines = [
            f"{self.sockets} WebSockets ouvertes, {self.bets} paris en {self.elapsed:.1f} s, "
            f"{len(every)} requêtes",
            "",
            f"{'route':<44} {'n':>5} {'p50':>7} {'p95':>7} {'max':>7}   (ms)",
        ]
        rows = sorted(self.timings.items()) + [("toutes les routes", every)]
        for route, values in rows:
            lines.append(
                f"{route:<44} {len(values):>5} {percentile(values, 50):>7.1f} "
                f"{self.p95(values):>7.1f} {max(values, default=0):>7.1f}"
            )
        arrived = [delay * 1000 for delay in self.broadcasts if delay is not None]
        lines += [
            "",
            f"diffusion d'un pari aux autres membres : {len(arrived)}/{len(self.broadcasts)} "
            f"reçues, p50 {percentile(arrived, 50):.0f} ms, p95 {percentile(arrived, 95):.0f} ms, "
            f"max {max(arrived, default=0):.0f} ms",
        ]
        return "\n".join(lines)


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[pct - 1]


async def prepare(members: int, open_pronos: int) -> Newsroom:
    """The newsroom, its members (each with a signed-in session) and its open pronos."""
    if get_settings().is_production:
        raise SystemExit("Le test de charge est refusé en production.")
    avatar = AVATAR_TEMPLATES[0]["image"]
    run = uuid.uuid4().hex[:6]
    tokens = [new_token() for _ in range(members)]
    async with transaction() as session:
        org = Organisation(
            title=f"Charge {run}", background_key="mer", charter="Rédaction du test de charge."
        )
        session.add(org)
        await session.flush()
        section = Section(org_id=org.id, name="Général", position=0)
        session.add(section)
        rows: list[Membership] = []
        for i, token in enumerate(tokens):
            account = Account(
                keycloak_id=uuid.uuid4(),
                email=f"{run}-{i:03}@{EMAIL_DOMAIN}",
                first_name="Charge",
                last_name=f"{i:03}",
                email_verified_at=clock.now(),
            )
            session.add(account)
            await session.flush()
            session.add(
                AuthSession(
                    account_id=account.id,
                    token_hash=token_hash(token),
                    expires_at=clock.now() + timedelta(days=1),
                )
            )
            member = Membership(
                org_id=org.id,
                account_id=account.id,
                # The first one publishes the pronos; the others are readers.
                role="editor" if i == 0 else "reader",
                pseudo=f"Charge {i:03}",
                avatar=avatar,
                charter_accepted_at=clock.now(),
            )
            session.add(member)
            await session.flush()
            await ledger.append(session, member.id, starting_balance(org.starting_balance))
            rows.append(member)
        await session.flush()
        made: dict[uuid.UUID, list[uuid.UUID]] = {}
        for n in range(open_pronos):
            prono = await pronos.create_prono(
                session,
                rows[0],
                {
                    "kind": "choice",
                    "question": f"Prono de charge n° {n + 1} ?",
                    "section_id": section.id,
                    "options": ["Oui", "Non", "Peut-être"],
                    "base_gain": 10,
                    "closes_at": clock.now() + timedelta(days=1),
                },
            )
            await session.flush()
            made[prono.id] = []
        await session.flush()
        for option in await session.scalars(
            select(PronoOption).where(PronoOption.prono_id.in_(made)).order_by(PronoOption.id)
        ):
            made[option.prono_id].append(option.id)
        org_id = org.id
    ids = list(made)
    return Newsroom(
        org_id=org_id,
        members=[
            Member(pseudo=f"Charge {i:03}", token=token, watches=ids[i % len(ids)])
            for i, token in enumerate(tokens)
        ],
        pronos=made,
    )


async def discard(newsroom: Newsroom) -> None:
    """Deletes the newsroom as its editor would, and closes the sessions of the test."""
    async with transaction() as session:
        org = await session.get(Organisation, newsroom.org_id)
        if org is not None and org.deleted_at is None:
            await orgs.delete_org(session, org)
        await session.execute(
            delete(AuthSession).where(
                AuthSession.token_hash.in_([token_hash(m.token) for m in newsroom.members])
            )
        )


class Watcher:
    """One member's WebSocket: notes when each bet on the prono they watch arrives."""

    def __init__(self, member: Member) -> None:
        self.member = member
        self.arrivals: dict[str, float] = {}
        self.socket: Any = None
        self.reader: asyncio.Task[None] | None = None

    async def open(self, api: str, origin: str, org_id: uuid.UUID) -> None:
        self.socket = await websockets.connect(
            api.replace("http", "ws", 1) + "/api/ws",
            origin=origin,  # type: ignore[arg-type]
            additional_headers={"Cookie": f"sibylle_session={self.member.token}"},
            max_queue=None,
        )
        topics = [f"org:{org_id}", f"prono:{self.member.watches}"]
        await self.socket.send(json.dumps({"type": "subscribe", "topics": topics}))
        async with asyncio.timeout(10):
            while True:
                message = json.loads(await self.socket.recv())
                if message.get("type") == "subscribed":
                    if message["topics"] != topics:
                        raise RuntimeError(f"abonnements refusés : {message}")
                    break
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        async for raw in self.socket:
            received = time.monotonic()
            message = json.loads(raw)
            if message.get("type") == "ping":
                await self.socket.send(json.dumps({"type": "pong"}))
            elif (
                message.get("type") == "event"
                and message.get("event") == "bet.placed"
                and message.get("topic", "").startswith("prono:")
            ):
                self.arrivals[message["data"]["bet"]["id"]] = received

    async def close(self) -> None:
        if self.reader:
            self.reader.cancel()
        if self.socket:
            await self.socket.close()


async def run(
    api: str,
    origin: str,
    newsroom: Newsroom,
    *,
    think: float = 0.0,
    seed: int = 0,
    wait: float = 5.0,
) -> Report:
    """The scenario, every member at once:

    1. everybody opens the app together: their account, the front page, the first prono;
    2. everybody bets on that prono in the same instant (the burst, timed apart);
    3. everybody goes through the other pronos (open it, bet, back to the front page) and ends
       on the list of pronos and the leaderboard, waiting between two screens a random time
       of `think` seconds on average (0: no wait at all, a stress test).
    """
    report = Report()
    base = f"/api/orgs/{newsroom.org_id}"
    # bet id → (prono, bettor, sent at)
    sent: dict[str, tuple[uuid.UUID, str, float]] = {}
    shuffle = random.Random(seed)
    first, *others = newsroom.pronos
    orders = [shuffle.sample(others, len(others)) for _ in newsroom.members]
    watchers = [Watcher(member) for member in newsroom.members]
    clients = [
        httpx.AsyncClient(
            base_url=api,
            headers={"X-Sibylle": "1", "Origin": origin},
            cookies={"sibylle_session": member.token},
            timeout=30,
        )
        for member in newsroom.members
    ]

    async def call(
        client: httpx.AsyncClient, route: str, method: str, url: str, **kwargs: Any
    ) -> httpx.Response | None:
        started = time.monotonic()
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as error:
            report.failures.append(f"{method} {url} : {error!r}")
            return None
        report.timings[f"{method} {route}"].append((time.monotonic() - started) * 1000)
        if response.is_error:
            report.failures.append(f"{method} {url} : {response.status_code} {response.text}")
            return None
        return response

    async def pause() -> None:
        if think:
            await asyncio.sleep(shuffle.uniform(0, 2 * think))

    async def bet(
        client: httpx.AsyncClient, member: Member, prono_id: uuid.UUID, route: str
    ) -> None:
        started = time.monotonic()
        placed = await call(
            client,
            route,
            "POST",
            f"{base}/pronos/{prono_id}/bets",
            json={
                "option_id": str(shuffle.choice(newsroom.pronos[prono_id])),
                "stake": shuffle.randint(0, 4),
            },
        )
        if placed is not None:
            sent[placed.json()["id"]] = (prono_id, member.pseudo, started)

    async def arrive(client: httpx.AsyncClient) -> None:
        await call(client, "/me", "GET", "/api/me")
        await call(client, "/orgs/{org}/front-page", "GET", f"{base}/front-page")
        await call(client, "/orgs/{org}/pronos/{id}", "GET", f"{base}/pronos/{first}")

    async def browse(client: httpx.AsyncClient, member: Member, order: list[uuid.UUID]) -> None:
        for prono_id in order:
            await pause()
            await call(client, "/orgs/{org}/pronos/{id}", "GET", f"{base}/pronos/{prono_id}")
            await pause()
            await bet(client, member, prono_id, "/orgs/{org}/pronos/{id}/bets")
            await pause()
            await call(client, "/orgs/{org}/front-page", "GET", f"{base}/front-page")
        await pause()
        await call(client, "/orgs/{org}/pronos", "GET", f"{base}/pronos")
        await pause()
        await call(client, "/orgs/{org}/leaderboard", "GET", f"{base}/leaderboard")

    members = list(zip(newsroom.members, clients, orders, strict=True))
    try:
        await asyncio.gather(*(w.open(api, origin, newsroom.org_id) for w in watchers))
        report.sockets = len(watchers)
        started = time.monotonic()
        await asyncio.gather(*(arrive(client) for _, client, _ in members))
        await asyncio.gather(
            *(bet(c, m, first, "/orgs/{org}/pronos/{id}/bets (rafale)") for m, c, _ in members)
        )
        await asyncio.gather(*(browse(c, m, order) for m, c, order in members))
        report.elapsed = time.monotonic() - started
        report.bets = len(sent)

        expected = [
            (w, bet_id)
            for bet_id, (prono_id, pseudo, _) in sent.items()
            for w in watchers
            if w.member.watches == prono_id and w.member.pseudo != pseudo
        ]
        deadline = time.monotonic() + wait
        # The sockets fill `arrivals` as the events come; give the last ones a moment.
        while time.monotonic() < deadline and any(b not in w.arrivals for w, b in expected):  # noqa: ASYNC110
            await asyncio.sleep(0.05)
        for w, bet_id in expected:
            arrived = w.arrivals.get(bet_id)
            report.broadcasts.append(None if arrived is None else arrived - sent[bet_id][2])
    finally:
        await asyncio.gather(*(w.close() for w in watchers))
        await asyncio.gather(*(client.aclose() for client in clients))
    return report


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--api", default="http://localhost:8000", help="adresse du serveur")
    parser.add_argument(
        "--origin",
        default=None,
        help="adresse de l'interface, vérifiée par le serveur (PUBLIC_ORIGIN par défaut)",
    )
    parser.add_argument("--members", type=int, default=100)
    parser.add_argument("--pronos", type=int, default=20)
    parser.add_argument(
        "--think",
        type=float,
        default=DEFAULT_THINK,
        help="secondes entre deux écrans d'un membre, en moyenne (0 : aucune, test de stress)",
    )
    parser.add_argument("--keep", action="store_true", help="garder la rédaction du test")
    args = parser.parse_args(argv)
    origin = args.origin or get_settings().public_origin
    try:
        async with httpx.AsyncClient() as probe:
            await probe.get(f"{args.api}/api/health")
    except httpx.HTTPError:
        print(f"Le serveur ne répond pas sur {args.api} : lance d'abord make dev.", file=sys.stderr)
        return 2

    newsroom = await prepare(args.members, args.pronos)
    print(f"Rédaction de charge prête : {args.members} membres, {args.pronos} pronos ouverts.")
    try:
        report = await run(args.api, origin, newsroom, think=args.think)
    finally:
        if not args.keep:
            await discard(newsroom)
        await dispose_engine()
    print(report.summary())
    problems = report.problems()
    for problem in problems[:20]:
        print(f"ÉCHEC : {problem}", file=sys.stderr)
    if not problems:
        print(
            f"\nOK : p95 de chaque route < {ROUTE_P95_MS:.0f} ms, "
            f"chaque pari diffusé en < {BROADCAST_MAX_S:.0f} s."
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

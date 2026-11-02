"""The `sibylle` command."""

import argparse
import asyncio
import json
import re
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from sibylle import clock

_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def parse_duration(text: str) -> timedelta:
    """`2h`, `30m`, `1d12h`, `90s`, `1w`…"""
    parts = re.findall(r"(\d+)([smhdw])", text)
    if not parts or "".join(n + u for n, u in parts) != text:
        raise argparse.ArgumentTypeError(f"durée invalide : {text!r} (exemples : 2h, 30m, 1d12h)")
    return timedelta(**{_UNITS[unit]: int(n) for n, unit in parts})


def parse_instant(text: str) -> datetime:
    instant = datetime.fromisoformat(text)
    if instant.tzinfo is None:
        raise argparse.ArgumentTypeError("l'instant doit avoir un fuseau, par exemple +01:00")
    return instant


def _openapi(_: argparse.Namespace) -> None:
    from sibylle.main import create_app

    json.dump(create_app().openapi(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _clock_set(args: argparse.Namespace) -> None:
    clock.set_fake_now(args.instant)
    print(clock.now().isoformat())


def _clock_advance(args: argparse.Namespace) -> None:
    clock.advance_fake(args.duration)
    print(clock.now().isoformat())


def _clock_show(_: argparse.Namespace) -> None:
    print(clock.now().isoformat())


def _worker(_: argparse.Namespace) -> None:
    from sibylle.worker.main import run_worker

    asyncio.run(run_worker())


def _jobs_run(args: argparse.Namespace) -> None:
    from sibylle.db.session import dispose_engine
    from sibylle.worker.jobs import REGISTRY

    if args.name not in REGISTRY:
        raise SystemExit(f"tâche inconnue : {args.name} (voir `sibylle jobs list`)")

    async def run() -> None:
        try:
            result = await REGISTRY[args.name].run()
            print(f"{args.name}: {result}")
        finally:
            await dispose_engine()

    asyncio.run(run())


def _seed_demo(_: argparse.Namespace) -> None:
    from sibylle.db.session import dispose_engine
    from sibylle.seed import seed_demo

    async def run() -> None:
        try:
            print(await seed_demo())
        finally:
            await dispose_engine()

    asyncio.run(run())


def _seasons_close(args: argparse.Namespace) -> None:
    from sibylle.db.session import dispose_engine
    from sibylle.worker.jobs import close_finished_seasons

    async def run() -> None:
        try:
            print(f"close_finished_seasons: {await close_finished_seasons(args.org)}")
        finally:
            await dispose_engine()

    asyncio.run(run())


def _secret_code_add(args: argparse.Namespace) -> None:
    from sibylle.db.session import dispose_engine, transaction
    from sibylle.services.collection import add_secret_code

    async def run() -> None:
        try:
            async with transaction() as session:
                await add_secret_code(session, args.code, args.item_key)
            print(f"code ajouté pour {args.item_key}")
        except LookupError as error:
            raise SystemExit(f"objet inconnu : {args.item_key}") from error
        finally:
            await dispose_engine()

    asyncio.run(run())


def _jobs_list(_: argparse.Namespace) -> None:
    from sibylle.worker.jobs import REGISTRY

    for job in REGISTRY.values():
        cron = " ".join(f"{field}={value}" for field, value in job.cron.items())
        print(f"{job.name}\t{cron}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sibylle", description="Sibylle : outils du serveur")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("openapi", help="écrit le schéma OpenAPI sur la sortie standard")

    clock_parser = commands.add_parser("clock", help="horloge simulée (SIBYLLE_CLOCK=fake)")
    clock_commands = clock_parser.add_subparsers(dest="clock_command", required=True)
    set_parser = clock_commands.add_parser("set", help="pose l'instant simulé")
    set_parser.add_argument("instant", type=parse_instant)
    advance_parser = clock_commands.add_parser("advance", help="avance l'horloge simulée")
    advance_parser.add_argument("duration", type=parse_duration)
    clock_commands.add_parser("show", help="affiche l'instant courant")

    commands.add_parser("worker", help="lance le processus de tâches planifiées")

    jobs_parser = commands.add_parser("jobs", help="tâches du worker")
    jobs_commands = jobs_parser.add_subparsers(dest="jobs_command", required=True)
    run_parser = jobs_commands.add_parser("run", help="exécute une tâche une fois")
    run_parser.add_argument("name")
    jobs_commands.add_parser("list", help="liste les tâches et leur planning")

    seasons_parser = commands.add_parser("seasons", help="saisons")
    seasons_commands = seasons_parser.add_subparsers(dest="seasons_command", required=True)
    close_parser = seasons_commands.add_parser(
        "close", help="clôture les saisons finies (toutes les rédactions, ou une seule)"
    )
    close_parser.add_argument("--org", type=uuid.UUID, help="identifiant d'une rédaction")

    code_parser = commands.add_parser("secret-code", help="codes secrets de la collection")
    code_commands = code_parser.add_subparsers(dest="secret-code_command", required=True)
    add_parser = code_commands.add_parser(
        "add", help="ajoute un code (seule son empreinte est gardée ; jamais dans le dépôt)"
    )
    add_parser.add_argument("code")
    add_parser.add_argument(
        "item_key", help="clé d'un objet du catalogue, par exemple ball-halloween"
    )

    commands.add_parser("seed-demo", help="crée la rédaction de démonstration (hors production)")
    return parser


_HANDLERS: dict[tuple[str, str | None], Callable[[argparse.Namespace], None]] = {
    ("openapi", None): _openapi,
    ("clock", "set"): _clock_set,
    ("clock", "advance"): _clock_advance,
    ("clock", "show"): _clock_show,
    ("worker", None): _worker,
    ("jobs", "run"): _jobs_run,
    ("jobs", "list"): _jobs_list,
    ("seasons", "close"): _seasons_close,
    ("secret-code", "add"): _secret_code_add,
    ("seed-demo", None): _seed_demo,
}


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    handler = _HANDLERS[(args.command, getattr(args, f"{args.command}_command", None))]
    handler(args)

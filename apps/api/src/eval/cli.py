"""``python -m src.eval`` — capture a fixture, load one, run the battery.

Three verbs, and which database each one touches is the whole of the safety
story:

- ``capture`` **reads** the application store and writes a file. It is the only
  verb that opens ``DATABASE_URL`` at all, and it never writes to it.
- ``load`` writes the fixture into ``EVAL_DATABASE_URL``, and refuses if that is
  unset or resolves to the application's database.
- ``run`` loads and then runs the battery, entirely inside the eval database —
  the store, the traces and the ledger.

Exit codes are the interface, because ``make eval`` is what invokes this: 0 for a
run that finished, 1 for anything else. A run stopped at its budget ceiling
exits 1 and says so, because it produced no score.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

from src.core.config import get_settings

from . import categories as _categories  # noqa: F401 - seats the battery
from .capture import CAPTURE_HISTORY_SESSIONS, capture_fixture
from .fixture import latest_seed_path, read_seed, seed_path, write_seed
from .harness import EvalMode, build_harness
from .report import write_report
from .store import create_schema, eval_engine, eval_session_factory, load_fixture
from .verdict import verdict

logger = logging.getLogger("src.eval")


def _resolved_seed(path: str | None, directory: Path):
    return read_seed(Path(path) if path else latest_seed_path(directory))


def _eval_factory():
    engine = eval_engine()
    create_schema(engine)
    return eval_session_factory(engine)


def capture(args: argparse.Namespace) -> int:
    from src.core.database import sync_session_factory

    directory = Path(args.out or get_settings().eval_fixture_dir)
    session = sync_session_factory()
    try:
        seed = capture_fixture(
            session,
            trading_day=date.fromisoformat(args.trading_day)
            if args.trading_day
            else None,
            history_sessions=args.history_sessions,
        )
    finally:
        session.close()
    path = write_seed(seed_path(directory, seed.fixture_version), seed)
    print(f"captured {seed.fixture_version} -> {path}")
    for role, symbol in sorted(seed.manifest.roles.items(), key=lambda i: i[0].value):
        print(f"  {role.value:<20} {symbol}")
    return 0


def load(args: argparse.Namespace) -> int:
    settings = get_settings()
    seed = _resolved_seed(args.fixture, Path(settings.eval_fixture_dir))
    loaded = load_fixture(seed, _eval_factory())
    print(f"loaded {loaded.fixture_version} at {loaded.trading_day}")
    return 0


def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    seed = _resolved_seed(args.fixture, Path(settings.eval_fixture_dir))
    harness = build_harness(
        mode=EvalMode(args.mode),
        seed=seed,
        session_factory=_eval_factory(),
        settings=settings,
    )
    result = asyncio.run(harness.run())
    path = write_report(result, Path(args.report_dir or settings.eval_report_dir))
    harness.record_report_path(result, path)
    print(f"{result.mode.value} run {result.run_id} -> {path}")
    if not result.complete:
        print(f"stopped: {result.stopped_reason}", file=sys.stderr)
        return 1

    scored = verdict(result)
    for item in scored.categories:
        print(f"  {item.category.value}: {item.summary}")
    if not scored.passed:
        # Named rather than counted: a category total tells an operator that
        # something regressed and nothing about what, and finding out by hand is
        # the next thing they would do anyway.
        for failure in scored.failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    if not result.mode.gating:
        print("non-gating: a smoke run may not be attached to a pull request")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.eval")
    sub = parser.add_subparsers(dest="command", required=True)

    capture_parser = sub.add_parser(
        "capture", help="freeze one Trading Day of the real store into a seed"
    )
    capture_parser.add_argument("--trading-day", default=None)
    capture_parser.add_argument(
        "--history-sessions", type=int, default=CAPTURE_HISTORY_SESSIONS
    )
    capture_parser.add_argument("--out", default=None)
    capture_parser.set_defaults(handler=capture)

    load_parser = sub.add_parser("load", help="load a seed into the eval database")
    load_parser.add_argument("--fixture", default=None)
    load_parser.set_defaults(handler=load)

    run_parser = sub.add_parser("run", help="run the Eval Battery")
    run_parser.add_argument("--mode", choices=[mode.value for mode in EvalMode], required=True)
    run_parser.add_argument("--fixture", default=None)
    run_parser.add_argument("--report-dir", default=None)
    run_parser.set_defaults(handler=run)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except Exception as failure:  # noqa: BLE001 - the CLI is the boundary
        # Loud, and on stderr, because every failure this catches is one the
        # ADR asks for by name: a version mismatch, a fixture that lost a
        # property, a database that is not separate.
        print(f"{type(failure).__name__}: {failure}", file=sys.stderr)
        return 1


__all__ = ["build_parser", "main"]

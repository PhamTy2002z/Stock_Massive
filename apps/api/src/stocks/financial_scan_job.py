"""Scanning quarterly statements, one symbol at a time, resumably and without a ledger.

**There is no checkpoint table.** Progress is derived from the store: a symbol
that already holds every requested part at the newest quarter the store knows is
skipped. The write is an idempotent upsert, so a run interrupted anywhere resumes
for free, and there is no second record of progress that can disagree with the
rows sitting next to it.

**"The newest quarter" is the store's own.** On a first run there is none and
nothing is skipped. After a quarterly release the first symbol to answer with
the new quarter moves the reference forward, and every symbol behind it is
fetched again — which is exactly the behaviour a scan wants in earnings season
and the reason the schedule is weekly then and monthly otherwise.

**One symbol failing does not end the run.** Market scope is 1,523 symbols times
up to four requests against a provider with no SLA; a run that stopped on the
first timeout would never finish, and there is nothing to lose by continuing —
the failed symbol simply has no new quarter until next time.

**One part is one transaction.** Not one symbol: a company that never reports a
cash flow — and there are such rows in a register that holds funds and shells —
would otherwise lose its income statement to the same rollback on every run,
forever, because the failure comes back every time. So each part commits on its
own and the symbol is reported as failed with the parts that did land already
stored.

**The job does not know the tier.** Pacing is the provider wrapper's exponential
backoff, which is the only thing that can see a rate limit. A free-tier run is
slower than a Bronze one and otherwise identical.

Scopes:

- ``declared`` — the 30 symbols the Universe declares.
- ``market`` — every share the listing register lists.
"""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.database import get_sync_db
from src.stocks.financial import STATEMENTS
from src.stocks.financial.fetch import PART_RATIO, PARTS, Fetch, RatioFetch
from src.stocks.financial.store import ingest_symbol
from src.stocks.models import FinancialRatioSnapshot, FinancialStatementLine
from src.stocks.universe import build_universe

logger = logging.getLogger(__name__)

SCOPE_DECLARED = "declared"
SCOPE_MARKET = "market"
SCOPES = (SCOPE_DECLARED, SCOPE_MARKET)

SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class SymbolReport:
    """One symbol's line in the run log."""

    symbol: str
    skipped: bool = False
    rows_written: int = 0
    calls: int = 0
    periods: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None


@dataclass
class ScanReport:
    """What one run did, in terms the operator asked about."""

    scope: str
    parts: tuple[str, ...]
    symbols: list[SymbolReport] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return sum(1 for report in self.symbols if not report.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for report in self.symbols if report.skipped)

    @property
    def rows_written(self) -> int:
        return sum(report.rows_written for report in self.symbols)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(
            report.symbol for report in self.symbols if report.error is not None
        )


def scope_symbols(session: Session, scope: str) -> tuple[str, ...]:
    """The symbols a scope covers, in a stable order.

    Stable so an interrupted run walks the market the same way next time, which
    is what makes "already stored" a resumable answer rather than a guess about
    which symbols were reached.
    """
    if scope == SCOPE_DECLARED:
        return tuple(build_universe(session).symbols)
    if scope == SCOPE_MARKET:
        return tuple(build_universe(session, with_market=True).market)
    raise ValueError(f"{scope!r} is not a scope; expected one of {SCOPES}")


def newest_stored_periods(session: Session) -> tuple[str | None, str | None]:
    """The newest quarter each table holds, or None while it is empty.

    Two references and not one: the statements come from VCI and the ratios from
    KBS, and the two sources publish a quarter on their own schedule. Judging a
    ratio's currency by the statements' newest quarter would refetch every symbol
    forever whenever one source ran ahead of the other.
    """
    statements = session.execute(
        select(func.max(FinancialStatementLine.period))
    ).scalar_one_or_none()
    ratios = session.execute(
        select(func.max(FinancialRatioSnapshot.period))
    ).scalar_one_or_none()
    return statements, ratios


def is_current(
    session: Session,
    symbol: str,
    *,
    parts: Sequence[str],
    statement_reference: str | None,
    ratio_reference: str | None,
) -> bool:
    """Whether this symbol needs no call at all.

    Every requested part has to be present at its table's newest quarter. Part
    completeness alone would freeze a symbol at whatever quarter it was first
    scanned on; currency alone would leave a symbol that only ever got its income
    statement permanently without a balance sheet.
    """
    symbol = symbol.upper()
    wanted_statements = [part for part in parts if part in STATEMENTS]
    if wanted_statements:
        if statement_reference is None:
            return False
        stored = set(
            session.execute(
                select(FinancialStatementLine.statement)
                .where(
                    FinancialStatementLine.symbol == symbol,
                    FinancialStatementLine.period == statement_reference,
                )
                .distinct()
            ).scalars()
        )
        if not set(wanted_statements) <= stored:
            return False

    if PART_RATIO in parts:
        if ratio_reference is None:
            return False
        has_ratios = session.execute(
            select(FinancialRatioSnapshot.symbol)
            .where(
                FinancialRatioSnapshot.symbol == symbol,
                FinancialRatioSnapshot.period == ratio_reference,
            )
            .limit(1)
        ).first()
        if has_ratios is None:
            return False

    return True


def run(
    *,
    scope: str,
    parts: Sequence[str] = PARTS,
    session_factory: SessionFactory = get_sync_db,
    fetch_statement: Fetch | None = None,
    fetch_ratio: RatioFetch | None = None,
    observed_at: datetime | None = None,
) -> ScanReport:
    """Scan one scope and report what happened per symbol.

    ``session_factory``, the two fetchers and ``observed_at`` are injectable so
    the suite can prove the skip rule and the failure isolation without reaching
    the network; production passes none of them.
    """
    if scope not in SCOPES:
        raise ValueError(f"{scope!r} is not a scope; expected one of {SCOPES}")
    unknown_parts = [part for part in parts if part not in PARTS]
    if unknown_parts:
        raise ValueError(f"{unknown_parts} are not parts; expected some of {PARTS}")
    wanted = tuple(parts)
    report = ScanReport(scope=scope, parts=wanted)

    with session_factory() as session:
        targets = scope_symbols(session, scope)
    if not targets:
        logger.warning(
            "Scope %s covers no symbols. For %s that means the listing register "
            "is empty — refresh it before asking for the market",
            scope,
            SCOPE_MARKET,
        )
        return report

    logger.info(
        "Financial scan starting: scope=%s symbols=%d parts=%s",
        scope,
        len(targets),
        ",".join(wanted),
    )
    for symbol in targets:
        report.symbols.append(
            _one_symbol(
                symbol,
                parts=wanted,
                session_factory=session_factory,
                fetch_statement=fetch_statement,
                fetch_ratio=fetch_ratio,
                observed_at=observed_at,
            )
        )

    logger.info(
        "Financial scan done: scope=%s attempted=%d skipped=%d rows=%d failed=%d",
        scope,
        report.attempted,
        report.skipped,
        report.rows_written,
        len(report.failures),
    )
    return report


def _one_symbol(
    symbol: str,
    *,
    parts: tuple[str, ...],
    session_factory: SessionFactory,
    fetch_statement: Fetch | None,
    fetch_ratio: RatioFetch | None,
    observed_at: datetime | None,
) -> SymbolReport:
    """One symbol, one part per transaction, never raising into the run.

    The skip decision is taken in a session of its own rather than carried from
    the scope pass, so a symbol filled by a concurrent run is seen as filled.
    """
    symbol = symbol.upper()
    try:
        with session_factory() as session:
            statement_reference, ratio_reference = newest_stored_periods(session)
            if is_current(
                session,
                symbol,
                parts=parts,
                statement_reference=statement_reference,
                ratio_reference=ratio_reference,
            ):
                logger.info(
                    "%s skipped: already holds %s at %s",
                    symbol,
                    ",".join(parts),
                    statement_reference,
                )
                return SymbolReport(symbol=symbol, skipped=True)
    except Exception as exc:  # noqa: BLE001 - one symbol must not end the run
        logger.warning("%s failed to read its own progress: %s", symbol, exc)
        return SymbolReport(symbol=symbol, error=str(exc))

    written = 0
    calls = 0
    periods: set[str] = set()
    errors: list[str] = []

    for part in parts:
        try:
            with session_factory() as session:
                outcome = ingest_symbol(
                    session,
                    symbol,
                    parts=(part,),
                    fetch_statement=fetch_statement,
                    fetch_ratio=fetch_ratio,
                    observed_at=observed_at,
                )
        except Exception as exc:  # noqa: BLE001 - one part must not cost the rest
            logger.warning("%s %s failed: %s", symbol, part, exc)
            errors.append(f"{part}: {exc}")
            continue
        written += outcome.rows_written
        calls += outcome.calls
        periods.update(outcome.periods)

    logger.info(
        "%s: rows_written=%d calls=%d periods=%s failed_parts=%d",
        symbol,
        written,
        calls,
        ",".join(sorted(periods, reverse=True)),
        len(errors),
    )
    return SymbolReport(
        symbol=symbol,
        rows_written=written,
        calls=calls,
        periods=tuple(sorted(periods, reverse=True)),
        error="; ".join(errors) if errors else None,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.stocks.financial_scan_job",
        description="Fill the quarterly financial store from the provider.",
    )
    parser.add_argument("--scope", required=True, choices=list(SCOPES))
    parser.add_argument(
        "--statements",
        nargs="+",
        choices=list(PARTS),
        default=list(PARTS),
        help=(
            "Which parts to fetch. Each costs one request per symbol; 'ratio' "
            "lands in the ratio table from its own provider source."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    args = _parse_args(argv)
    report = run(scope=args.scope, parts=tuple(args.statements))
    if report.failures:
        # A non-zero exit so an operator sees it, after every other symbol has
        # been written. Re-running the same command retries only what failed.
        logger.warning("Symbols that failed: %s", ", ".join(report.failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

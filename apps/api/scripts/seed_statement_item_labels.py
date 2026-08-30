"""Name the market's statement lines once, from one symbol per reporting template.

``financial_statement_line`` holds 302.528 numbers under provider ids and no
labels. Every frame handed to the browser labels its columns in Vietnamese
(``studies/contracts.py::Frame``), so without this table a financial frame is a
grid headed ``business_income_tax_deferred``.

**One symbol per reporting template.** A bank's income statement is 26 lines, a
securities house's 79 and a steelmaker's 25, and they share almost nothing
(``stocks/models.py::FinancialStatementLine``). STB, SSI and HPG are one of
each — and **BVH is the fourth**, added 2026-08-29 after the first seed reached
88,7% and every one of the 73 unlabelled ids turned out to be an insurer's
(``provision_for_catastrophe_reserve``, ``subrogation_recoveries``,
``loss_from_life_insurance``). A fifth symbol under a template already seeded
adds nothing but a request, which is why coverage is reported rather than
assumed: the run prints what fraction of the ids actually stored now have a
Vietnamese label, and a number under the target is a signal to seed another
representative rather than to invent a heading.

**Four parts per symbol, sixteen requests total.** The three statements plus the
ratio response, whose ids a frame has to head as well. The ratio response
carries no ``item_en`` — KBS ignores ``lang="en"`` — so its labels are stored
with a NULL English column rather than skipped.

**Idempotent.** The write is an upsert keyed ``(statement, item_id)``, so a
second run rewrites the same rows and adds none. Re-running with a different
symbol is how a label filed under the wrong template gets corrected.

Run by hand, once:

    make seed-statement-labels

``--symbols`` overrides the three, ``--dry-run`` fetches and reports without
writing.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter

from sqlalchemy import select

from src.alpha.models import FinancialStatementItem
from src.core.database import get_sync_db
from src.core.quota import QuotaLane, quota_arbiter, quota_lane
from src.stocks.financial import fetch, store
from src.stocks.financial.fetch import PART_RATIO, PARTS
from src.stocks.models import FinancialRatioSnapshot, FinancialStatementLine

logger = logging.getLogger("seed_statement_item_labels")

#: One symbol per reporting template. STB reports under the bank template, SSI
#: under the securities house's, HPG under the general one (measured 2026-08-27)
#: and BVH under the insurer's (measured 2026-08-29, from the ids the first
#: three left unlabelled). Together they reach 100% of the ids the store holds.
REPRESENTATIVES: tuple[str, ...] = ("STB", "SSI", "HPG", "BVH")

#: The share of stored ids that should end up labelled. Not a gate that stops
#: the run — a shortfall is a fact to act on, and the action is to seed another
#: representative, which needs the run to have finished first.
COVERAGE_TARGET = 0.95


def _fetch_labels(symbol: str, part: str) -> list[dict]:
    """One symbol's labels for one part, or an empty list with the reason logged.

    A part that fails is skipped rather than aborting the seed: the templates are
    independent, and eleven parts of labels are worth more than none.
    """
    try:
        # Counted before the call and not only wrapped in a lane. ``financial/
        # fetch.py`` has never asked the arbiter — it predates it — so a lane
        # around a call that never acquires would be decoration. Sixteen calls is
        # small, and small is exactly the size of thing that stops being counted.
        quota_arbiter().acquire()
        frame = (
            fetch.fetch_ratio(symbol)
            if part == PART_RATIO
            else fetch.fetch_statement(symbol, part)
        )
        return fetch.label_rows(symbol, part, frame)
    except Exception as error:  # noqa: BLE001 - one part's failure is not the run's
        logger.warning("%s %s: no labels (%s)", symbol, part, error)
        return []


def _coverage(session) -> tuple[int, int, dict[str, tuple[int, int]]]:
    """How many stored ``(statement, item_id)`` pairs now carry a label.

    Counted against what the store actually holds rather than against what the
    provider answered, because the question a frame asks is "can I head this
    column", and the columns a frame can have are the ones with numbers under
    them.

    The ratio table counts too. It is a separate table filled from a separate
    provider response, and a ratio frame heads its columns from the same label
    table — leaving it out of the denominator would report full coverage while a
    whole source drew raw ids.
    """
    stored = set(
        session.execute(
            select(
                FinancialStatementLine.statement, FinancialStatementLine.item_id
            ).distinct()
        ).all()
    )
    stored |= {
        (PART_RATIO, item_id)
        for (item_id,) in session.execute(
            select(FinancialRatioSnapshot.item_id).distinct()
        ).all()
    }
    labelled = set(
        session.execute(
            select(FinancialStatementItem.statement, FinancialStatementItem.item_id)
        ).all()
    )
    per_statement: dict[str, tuple[int, int]] = {}
    for statement in sorted({name for name, _ in stored}):
        want = {pair for pair in stored if pair[0] == statement}
        have = want & labelled
        per_statement[statement] = (len(have), len(want))
    return len(stored & labelled), len(stored), per_statement


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        default=",".join(REPRESENTATIVES),
        help="Comma-separated representatives, one per reporting template.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report coverage without writing a row.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    if not symbols:
        parser.error("--symbols named nothing")

    rows: list[dict] = []
    per_symbol: Counter[str] = Counter()
    # Sixteen provider calls, spent through the one arbiter that owns the
    # account's allowance. ``BACKFILL`` stands aside for a caller with a user
    # waiting behind it, which is what an operator's one-off job should do to an
    # allowance a conversation is also drawing on.
    with quota_lane(QuotaLane.BACKFILL):
        for symbol in symbols:
            for part in PARTS:
                part_rows = _fetch_labels(symbol, part)
                rows.extend(part_rows)
                per_symbol[symbol] += len(part_rows)
                logger.info("%s %s: %d labels", symbol, part, len(part_rows))

    if not rows:
        logger.error("no labels fetched; nothing to write")
        return 1

    written = 0
    with get_sync_db() as session:
        if not args.dry_run:
            written = store.write_statement_items(session, rows)
            session.flush()
        have, want, per_statement = _coverage(session)
        if args.dry_run:
            session.rollback()

    logger.info(
        "fetched %d label rows from %s; wrote %d",
        len(rows),
        ", ".join(f"{symbol}={count}" for symbol, count in per_symbol.items()),
        written,
    )
    for statement, (covered, total) in per_statement.items():
        share = covered / total if total else 0.0
        logger.info("%s: %d/%d ids labelled (%.1f%%)", statement, covered, total, share * 100)

    share = have / want if want else 0.0
    logger.info("overall: %d/%d stored ids labelled (%.1f%%)", have, want, share * 100)
    if share < COVERAGE_TARGET:
        logger.warning(
            "below the %.0f%% target: seed another representative rather than "
            "inventing a heading",
            COVERAGE_TARGET * 100,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

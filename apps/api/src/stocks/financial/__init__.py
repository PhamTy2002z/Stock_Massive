"""The quarterly financial store: fetch it, store it, name it, read it.

Four modules, in the order a number travels through them:

- ``fetch`` — the provider call and the wide-to-long normalisation, including
  the occurrence index that makes a repeated ``item_id`` storable.
- ``store`` — the idempotent upsert, so a scan run twice writes nothing new.
- ``templates`` — the only place that decides which stored line answers a named
  concept, and the only place that says ``unknown``.
- ``reads`` — one symbol's quarters, and one quarter across the market.

``src/stocks/financial_scan_job.py`` is the operator's entry point.

**This module imports nothing.** ``fetch`` imports pandas and vnstock at module
load, as the daily provider does, and a reader that only wants stored numbers —
a Signal Field, a Study — should not pay for that. So the vocabulary the read
side needs lives here, where importing the package costs nothing, and the
provider module imports it from here rather than the other way round.
"""

STATEMENT_INCOME = "income"
STATEMENT_BALANCE = "balance"
STATEMENT_CASHFLOW = "cashflow"
STATEMENTS = (STATEMENT_INCOME, STATEMENT_BALANCE, STATEMENT_CASHFLOW)

__all__ = [
    "STATEMENTS",
    "STATEMENT_BALANCE",
    "STATEMENT_CASHFLOW",
    "STATEMENT_INCOME",
]

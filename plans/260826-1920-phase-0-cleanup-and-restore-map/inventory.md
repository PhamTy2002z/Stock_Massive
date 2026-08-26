# Phase 0 cleanup inventory

Recorded against `93c23cf065ace06012d50b9ad83c6eb553fca418` on 2026-08-26.

## Empty stocks shells

The nine target directories contain no source files. Their only contents are
ignored `__pycache__/*.pyc` artifacts:

- `apps/api/src/stocks/{analytics,company,financial,market,monitor,news,price,trading}`
- `apps/api/src/stocks/realtime/dnse`

The retained siblings are `providers`, `realtime`, `signals`, `schemas`,
`shared`, `models.py`, `universe.py`, `trading_day.py`, and
`listing_roster.py`.

## Signal-module reverse imports

The plan's 12-module orphan assumption does not match the current source. The
runtime registry exposes 30 fields, and 11 target modules are live directly or
transitively:

| Module | Reverse-import evidence | Decision |
|---|---|---|
| `corporate_actions` | `signals/bars.py` | Keep |
| `cross_sectional` | `signals/registry.py`, `signals/serving.py` | Keep |
| `foreign_flow` | `signals/registry.py` | Keep |
| `foreign_share_flow` | `signals/serving.py` | Keep |
| `fundamentals` | `signals/fields.py`, `signals/cross_sectional.py`, `signals/serving.py` | Keep |
| `indicators` | `signals/registry.py`, `tests/test_indicator_pack.py` | Keep |
| `market_behavior` | `signals/registry.py` | Keep |
| `moments` | `signals/{cross_sectional,market_behavior,risk}.py` | Keep |
| `nulls` | No source or test importer | Delete |
| `reference` | `signals/fields.py`, `signals/foreign_flow.py`, `signals/serving.py` | Keep |
| `risk` | `signals/registry.py` | Keep |
| `volatility` | `signals/registry.py`, `signals/risk.py`, `tests/test_signal_registry.py` | Keep |

Deleting the 11 live modules would remove public `list_fields` entries and
violate the plan constraint that runtime and wire contracts remain unchanged.
The pre-cleanup registry snapshot is 30 fields with registry version
`6804372f00b0c017`.

## Stale settings

Zero-caller settings eligible for removal from `src/core/config.py` are:

- `fiinquant_username`, `fiinquant_password`
- `realtime_ingestion_enabled`, `dnse_api_key`, `dnse_api_secret`,
  `dnse_board_ids`, `realtime_queue_size`, `realtime_worker_count`,
  `realtime_shutdown_timeout_seconds`, `realtime_boards`, and
  `_complete_realtime_configuration`
- `backfill_enabled`, `backfill_hour`, `backfill_minute`,
  `backfill_symbols_per_run`, `backfill_depth_days`,
  `backfill_main_source_days`
- `warmup_window_trading_days`
- `alpha_desk_suggestions_enabled`
- Intraday collector, profit census/cohort, collector, corporate-action job,
  market-index/catch-up, Analysis dispatcher, sector-historical job, and
  removed Evidence Manifest settings (`git_sha`)

`alpha_desk_enabled` must remain: `src/core/llm/config.py` reads it and startup
capability enforcement plus direct tests rely on that public config key.
Corresponding stale forwarding exists in the environment templates and both
Docker Compose manifests.

## Alembic drop candidates

Repository and restored-backup head are both `e2c4a7d19b63`. The exact
FK-safe candidate order, based on zero live consumers outside stale ORM
declarations, is:

1. `analysis_tool_call`
2. `analysis_run`
3. `watchlist_entries`
4. `analysis`
5. `cohort_members`
6. `cohort_versions`
7. `profit_ranking_census_runs`
8. `symbol_backfills`
9. `stock_intraday_bars`
10. `stock_daily_ohlcv`

The following initially proposed realtime tables must remain because
`src/stocks/realtime/storage.py` still owns them and
`signals/foreign_share_flow.py` reads `realtime_events`:
`realtime_events`, `realtime_checkpoints`, `realtime_spills`,
`realtime_health`, and `realtime_reconciliation_audits`.

The backup and current Docker DB each expose the same 27 public tables
(including `alembic_version`), so a table-set diff alone cannot identify dead
ownership. The running `stockmassive-db-1` is shared with another worktree;
schema validation must target the disposable restored database, not its main
`stockmassive` database.

## Backup

- Path: `backups/pre-rip-out-260825.sql.gz`
- Compressed size: 7.2 MiB
- SHA-256: `81aa1d42e8a47725b77c2dd8542e6f03fa757e3345337027ff7731dd870dcba4`
- Format: gzip-wrapped PostgreSQL 16.13 plain-text SQL dump
- Uncompressed size: 81,622,467 bytes
- `gzip -t`: pass
- `pg_restore --list`: inapplicable to text-format dumps; it correctly directs
  the caller to `psql`
- Full `psql -v ON_ERROR_STOP=1` restore into disposable `restore_check`: pass
- Sample restored row counts: `users=34`, `agent_thread=55`,
  `stock_daily_ohlcv=119525`, `realtime_events=0`

## Baseline tests

- API: `make test` — 940 passed, 0 failed (97 warnings)
- Web: `pnpm test` — 406 passed, 0 failed across 32 files

## Git rollback anchor

```text
93c23cf docs(claude,docs): rewrite around the harness-first pivot
f4821d9 refactor(web): rip market surfaces down to the chat view
9611982 refactor(api): rip market surfaces down to the chat lane
```

## Security finding

Tracked `text.md` contained non-empty values for eight credential-shaped keys
despite claiming to be ignored. Values were redacted from the working tree and
must be rotated because removal from the current file does not remove Git
history.

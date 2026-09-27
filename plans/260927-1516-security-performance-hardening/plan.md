# Security, performance and concurrency hardening

Status: done (uncommitted) · Branch: feat/host-owned-numbers (shared working tree with
the English-webapp plan `260927-1503-english-ui-answer-language`)
Source: `plans/reports/security-260927-1509-full-codebase-audit.md`

## Outcome
Every finding in the audit (C1, H1–H7, M1–M21, L1–L20) is fixed or explicitly
recorded as not changed with a reason, with tests for non-trivial logic, and
the whole system is ready: backend suite, web lint/type-check/test/build pass,
the dev stack boots healthy on the new migration.

## Decisions taken for the audit's open questions
1. The API stays reachable only through Caddy (API site) and the Next proxy; no
   published host ports in prod. Dev ports bind to `127.0.0.1`.
2. Self-registration stays open (product decision, unchanged); the per-user LLM
   caps come back by removing the compose `:-0` fallbacks.
3. Prod gets a Redis service; credential endpoints fail closed without it.
4. Stop-before-start is not assumed: active Turns carry a heartbeat, and the
   startup sweep and the periodic reaper only settle Turns whose heartbeat is stale.
5. The 1 h lane deadline and 3 system slots are intentional; unchanged.
6. One active Turn per user across Threads stays; the web scopes Stop/busy to
   the Thread that owns the live Turn.

## Constraints
- No user-facing string changes (the English-webapp plan owns copy).
- No public HTTP/SSE payload change except: `/capabilities` requires auth,
  `/docs` + `/openapi.json` off when `ENVIRONMENT=production`.
- One additive migration (column + indexes); back up the dev DB first.
- Don't drop data; don't fork/patch flint-chart.

## Phases and file ownership
| # | Scope | Findings | Files |
|---|-------|----------|-------|
| 1 | Infra + deps | C1, H1, H2, H3, M1, M5 (Caddy), M16, L20 | compose files, Caddyfile, Dockerfiles, web package.json/lock, next.config.js |
| 2 | Core + auth | M2, M3, M4 (API side), M6, M12, L1, L2, L5, L6 | core/{ratelimit,redis,config,database}.py, auth/*, agent/limits.py, agent/router.py |
| 3 | Agent capability plane | H7, M5 (API), M7, M8, M13, L3, L4, L8–L12 | executor.py, tools/web.py, core/web_lane.py, security.py, untrusted.py, tools/memory.py, attachments.py |
| 4 | Turn lifecycle + perf | H5, H6, M9, M10, M11, M14, L7, L13, L14 | loop.py, grounding.py, turns.py, persistence.py, core/llm/admission.py, vnstock_provider.py, compaction.py, main.py, new migration |
| 5 | Web | H4, M4 (Next side), M5 (Next), M15, M17–M21, L15–L19 | apps/web/src (listed files only) |
| 6 | Verify | all | full suites, build, dev stack restart, migration |

## Acceptance
- `make test` (apps/api) and `pnpm --dir apps/web lint type-check test` pass;
  `E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build` passes.
- `pnpm audit` shows no critical/high in runtime deps.
- `alembic upgrade head` applies on the dev DB after a `pg_dump` backup; api
  restarts healthy.
- Each fixed finding has a regression test where the logic is non-trivial.

## Result
See `plans/reports/implementation-260927-1641-security-performance-hardening.md`.

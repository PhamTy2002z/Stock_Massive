# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

VisgniteAI / Stock_Massive: an authenticated research desk for Vietnamese
listed equities (HOSE, HNX, UPCOM). The web interface is English; an answer is
written in the language of the user's question, and the labels the host writes
into it follow that answer's language. It is an **agent harness for
financial research** — tool calling, durable Turn state, context management,
permissions, guardrails, an evidence/claim ledger and memory — not a
market-data terminal and not a local analysis engine. Answers must stay
traceable to their source, timing and uncertainty; refusing is a valid outcome.

Two apps, no root workspace:

- `apps/api` — FastAPI + SQLAlchemy/Alembic + Postgres + Redis (Python).
- `apps/web` — Next.js 15 / React 18 / TanStack Query / Tailwind, managed with
  `pnpm` and its own `apps/web/pnpm-lock.yaml`. Do not add a root lockfile.

## Commands

Dev stack (root `package.json`):

```bash
pnpm dev              # docker compose (db, redis, api) --wait, then Next.js on the host
pnpm dev:web          # web only
pnpm logs:api
pnpm db:migrate       # alembic upgrade head inside the api container
pnpm db:shell
```

The `api` container bind-mounts `apps/api/src` and `apps/api/alembic`, so Python
changes need `docker compose restart api`, not a rebuild. API boot takes ~50s
because the LLM Capability Probe makes real model calls on startup
(`LLM_CAPABILITY_PROBE_ENABLED`).

Backend (run on the host, from `apps/api`; the Makefile prefers `.venv/`):

```bash
make test                                              # full suite
make test-one T=tests/test_agent_loop.py K="tool"      # one file / -k filter
.venv/bin/pytest tests/test_agent_loop.py::test_name -q
python -m compileall -q src tests
```

`pytest.ini` excludes the `network` (live vnstock), `redis_server` and
`model_behaviour` (live model) markers by default; opt in with `-m <marker>`.

Web (from repo root):

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test                        # vitest
pnpm --dir apps/web exec vitest run src/lib/format.test.ts
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e                    # playwright; boots tests.e2e.server on :8010 and web on :3010
```

`next build` writes into `.next` and breaks a running `next dev`; build into
another dir instead: `E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build`.

A local Homebrew Postgres holds `127.0.0.1:5432`, so a host-side run (`make test`
included) talks to *it*, not to Docker, unless `DATABASE_URL` says otherwise; its
schema is kept by the tests' `create_all`, not by alembic. Dev compose binds db,
api and web to `127.0.0.1` only — set `POSTGRES_PORT=5433` in `.env` before the db
container is recreated, or the bind collides with Homebrew.

## Architecture

`apps/api/src/agent/ARCHITECTURE.md` is the detailed runtime description (in
Vietnamese). The big picture:

- **Turn lifecycle** (`agent/turns.py`, `service.py`, `router.py`, `sse.py`):
  `POST` creates a durable `agent_turn` row idempotently, then runs the agent in a
  background task detached from the request. Progress streams over SSE with
  replay; the Turn settles atomically (message + status + `terminal_reason`) in
  one transaction. A running Turn heartbeats every 20s (`agent_turn.heartbeat_at`);
  the startup sweep and a 60s reaper settle only active Turns whose heartbeat is
  older than 90s, so a second process sharing the DB keeps its Turns.
- **Loop** (`agent/loop.py`): model ↔ tool rounds bounded by a **lane**
  (`lanes.py`: max rounds, external-call budget, deadline). The model plans the
  order; the host owns budget, permission and stop reason. The deep lane runs
  `evidence/pipeline.py` (plan → research → counterevidence → clean-context
  verifier) and writes to the claim ledger (`evidence/ledger.py`).
- **Capability plane**: tools register only through `agent/registry.py` +
  `agent/tools/`; `toolsets.py` resolves the per-mode/profile surface;
  `executor.py` validates args by schema, checks permission and guardrails
  (`guardrails.py`: allow → warn → block → halt), and runs `PARALLEL_SAFE`
  reads concurrently with stable result order. There is no second dispatch path.
- **Context** (`messages.py`, `budget.py`, `compaction.py`, `prompt/`): a static,
  cacheable system prompt with runtime values in a tail; older Turns kept as
  prose only; a reduction ladder ending in `context_overflow` when still too big;
  thread summaries run out-of-band after settle.
- **LLM gateway** (`core/llm/`): OpenAI-compatible route configured by `LLM_*`
  env, with admission, budget ledger (monthly/turn/user caps), circuit breaker
  and typed provider recovery. `ALPHA_DESK_ENABLED` validates the price table at
  startup.
- **Untrusted content** (`untrusted.py`, `threat_patterns.py`): web/tool output is
  wrapped and scanned; it can never change policy, permissions, memory scope or
  instructions. `remember_fact`, the only write tool, is blocked once a Turn has
  read untrusted content.
- **Web** (`apps/web/src`): `components/shell/` is the chat workspace (composer,
  inspector pane, shell state); `lib/alpha-desk/` is the Turn/SSE client;
  `components/signal-desk/` + `lib/flint/` render the Signal Desk chart.

## Capability boundary

- Tool catalog: `web_search`, `fetch_url`, `session_search`, `remember_fact`,
  `recall_facts`, plus the vn-equity pack's `get_market_data`,
  `get_financial_ratios` (both refuse outside the `personal_internal` profile;
  statements go through the `FinancialsProvider` adapter — KBS + Vietcap for
  dev only), `get_company_events`, `get_company_news`, `screen_stocks` and
  `calculate` (fixed operations, formula printed). Every vnstock call goes
  through `agent/tools/vnstock_provider.py`: guest quota is 20 req/min and
  `vnai` calls `sys.exit` on breach, so the gate stops at 16 (48 when
  `VNSTOCK_API_KEY` holds a community key) and turns a `SystemExit` into a
  `rate_limited` refusal. Provider reads are memoised in process
  (`vnstock_provider.cached`); `retrieved_at` is when the data was fetched.
- Every answer's figures and full dates (`dd/mm/yyyy`) are checked by
  `agent/evidence/grounding.py` against that Turn's tool data, dated and labelled in place (`chưa kiểm chứng`,
  `nguồn cũ` — or `unverified`, `stale source` in an English answer, chosen by
  `evidence/numbers.answer_language`; `apps/web/src/lib/alpha-desk/figure-markers.ts`
  reads both sets), with one repair round; each answered Turn writes a claim ledger. Adding a
  tool, MCP, multi-agent, code execution or side-effect tool is a scope decision
  for the product owner, not an implementation detail.
- Signal Desk is a composer mode (`Chat | Signal Desk` pill), a right-hand pane
  and one visual part. `mode` travels on the Turn body; `chat` never produces a
  visual part.
- `CreateTurnRequest` is `extra="forbid"` (`agent/schemas.py`): a Turn-body field
  the schema doesn't declare 422s every Turn. Change schema and client together.
- The chart core is `flint-chart`, pinned exact. Don't fork, patch, copy its
  templates, post-process its ECharts output or persist a generated option. The
  host builds a `ChartAssemblyInput` from accepted market evidence; the model
  sends no numbers.
- Retired, do not restore: the analysis board and its blocks, Study/Board DSL,
  widget catalog, chart runtimes other than flint, artifact rows and
  `GET /artifacts/{id}`, local indicator/calculation tools, stock-store reads and
  their schedulers, global watchlists. `apps/api/src/stocks/` and `src/studies/`
  are untracked `__pycache__` leftovers — never import from them.
- Treat public HTTP/SSE contracts, data drops/migrations, default permissions and
  the research-vs-advice legal boundary as one-way doors: stop and ask.
- Don't drop historical DB data during code cleanup; back up before any schema
  or data change.

## References

- `plans/260906-1557-financial-research-agent/` — current (proposed, not yet
  approved) system plan; `plans/260905-0001-signal-desk-visual-harness/` blocks it.
- `docs/hermes/` (start from `hermes-synthesis-*.md`) and `docs/opencode/` are
  research on the runtimes this harness learns from, not descriptions of this code.
- `DESIGN.md` — UI design system.
- `apps/api/AGENTS.md` is vnstock's third-party onboarding file, not a project contract.

# The Eval Fixture and the Eval Battery

Implements `docs/adr/0016` and `docs/specs/0003-intelligent-quant-architecture.md` §A7.
Code lives in `apps/api/src/eval/`.

Two things are documented here because neither is derivable from the code: **how
to re-freeze a fixture**, and **which database each command is allowed to touch**.

## The three databases

| Command | Reads | Writes |
| --- | --- | --- |
| `make eval-fixture` | `DATABASE_URL` | a seed file only |
| `make eval-fixture-load` | the seed file | `EVAL_DATABASE_URL` |
| `make eval` / `make eval-smoke` | the seed file, `EVAL_DATABASE_URL` | `EVAL_DATABASE_URL` |

**Running the battery cannot write to dev or production.** `EVAL_DATABASE_URL`
must be set and must not resolve to the same host, port and database name as
`DATABASE_URL`; the code refuses otherwise, and it compares destinations rather
than strings, so the same database spelled with a different driver is still
refused.

Everything a run writes lands in the eval database, the ledger included —
`llm_call_usage` and `eval_run`. That is the same atomic reservation of
ADR-0014 pointed at a different database, not a different mechanism.

**The cost of that, stated rather than buried.** ADR-0014 puts a $5/month eval
lane inside the $50 envelope. Because the ledger lives in the eval database, that
lane is counted *there* — so eval spend does not appear in the production
envelope, and dropping the eval database resets the lane. Two ceilings still
bind a run honestly: the per-run **$2.5**, and the eval lane as accumulated in
the eval database. What is lost is the single monthly view across all four lanes.

This follows from issue #93's criterion — *the eval database is separate from dev
and production, and running the battery cannot write to either* — which cannot be
satisfied while writing the ledger to production. If the monthly view matters
more than that criterion, the decision to revisit is this one, and it is a
one-line change of session factory in `harness.build_harness`.

Set it up once:

```bash
createdb stockmassive_eval          # or CREATE DATABASE from psql
export EVAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/stockmassive_eval
```

No migration step. The eval database is disposable and its schema is created
from the models on load; what actually guards against drift is the fixture's
`schema_version`, which is checked before anything is written.

## Re-freezing a fixture

```bash
cd apps/api
make eval-fixture                       # newest Trading Day in the store
# or: .venv/bin/python -m src.eval capture --trading-day 2026-08-14
```

The command prints the new `fixture_version` and the symbol seated in each role.
Commit the file it wrote under `eval/fixtures/`. **Do not edit it** — the
version is a digest of the contents, so an edited seed is refused on the next
read.

### Symbols are selected by property, never named

There is no list of tickers to maintain, and that is the point. A hand-written
list stops being true: the symbol that was limit-locked in August is liquid by
November, and a re-freeze against the same list produces a fixture that has
quietly lost category E.

So the store is scanned and the first symbol satisfying each probe is seated.
The probes are in `src/eval/roles.py` and each is answered by the real code —
`prepare_bars()`'s own refusals, and `industry_for_icb` over the stored ICB
level-2 code:

| Seat | What has to be true |
| --- | --- |
| `below_min_sessions` | `prepare_bars()` refuses `insufficient_history` at the price-zone field's floor |
| `price_basis_seam` | `prepare_bars()` refuses `mixed_price_basis` over a 250-session window (ADR-0006) |
| `limit_lock_dense` | at least a fifth of the served window is limit-locked |
| `bank` / `real_estate` / `retail` | the stored ICB level-2 code selects that industry block |
| `ordinary` | classified, and none of the three |
| `outside_universe` | listed by an exchange and outside the pinned Universe |

The hard seats are filled first, and that ordering is load-bearing: a symbol
below `min_sessions` is rare and is very often also a bank, so filling the bank
seat first would take the only candidate the data-gap category has.

**A store that cannot fill a seat produces a refusal, not a fixture.** Capture
at a different Trading Day, or widen the Universe. Do not freeze a fixture
without its deliberate bad cases: the battery would then report a category E
score over cases that were never exercised.

### What is captured, and what is not

Captured: `listing_roster`, `provider_snapshots` (including the benchmark
index), `corporate_actions`, `analysis` — for the seated symbols, over
`CAPTURE_HISTORY_SESSIONS` trading sessions ending at the fixture's day.

Not captured, and seated by the loader instead: the eval user and its watchlist.
A real account's watchlist is personal data and would make the fixture depend on
whoever was logged in on capture day.

Not captured, deliberately: the cohort tables. The Universe is pinned in the
manifest as the declared half, so it is one written-down list rather than a list
plus a ranking that only means something with all fifty of its members present.

### Versions, and failing loud

A fixture records `fixture_version`, `registry_version`, `profile_version`,
`tool_catalog_version` and `schema_version`. **A mismatch refuses to load and
refuses to start the battery, naming the version that moved.** The failure mode
being designed out is not a crash — it is a green run: an old fixture passed
through a new Signal Registry produces flattering scores at precisely the moment
the registry changed.

When `fixture_version` changes, the previous baseline is void (ADR-0016). The
run is marked `baseline_reset` — see [The baseline](#the-baseline).

## Running the battery

```bash
make eval-smoke   # dev route, zero cost, NO gating value
make eval         # production route and models, hard $2.5 ceiling
```

`smoke` proves the harness and the deterministic assertions still work. It does
not exercise the production model, so it may not be attached to a pull request,
and its report is written under a filename that cannot occupy the baseline's.

`gate` is the real thing. Every provider call reserves against `llm_call_usage`
with `owner_type = 'eval_run'` and the run's id, inside the same locked
transaction every other call passes through. **On the $2.5 ceiling the run stops
and reports `eval_budget_exhausted`.** It exits non-zero and its result carries
no score: a battery that truncates itself and publishes a total is a battery
that lies. A case interrupted mid-way is dropped whole rather than scored on one
run of three.

Each case runs **three times** and all three outcomes are kept. The thresholds
live in `src/eval/baseline.py`: **A, C and F at 3/3**, **B ≥ 90%**, **D and E ≥
85%**, and the hard fail on a backwards sign overrides every rate.

### The two surfaces

One run covers both. Turn cases go through the deployed `AgentLoop`; Analysis
cases run the **nightly pipeline** over the same fixture — the same lifecycle,
the same envelope, the same single strict structured-output call and the same
semantic validation — inside the same `eval_run` and the same ceiling. Roughly
ten Analysis cases, scored by D and E, and the report keeps the lanes apart in
its totals and in its case sections.

Two things about `src/eval/analysis_lane.py` are worth knowing before reading it:

- **Its generations are charged to the `eval_run`, not to the Analysis Run.**
  The redirect happens at the client boundary, and the production per-call
  ceilings are asked *first*, on the spend the producer built — otherwise the
  battery would admit an envelope the nightly pass refuses.
- **The pair is cleared before each of the three runs.** Production is
  idempotent per `(symbol, trading_day)` and the fixture carries the `analysis`
  rows the real store held, so a lane that did not clear them would score one
  generation three times and call it agreement.

Three checks belong to that lane alone, and each re-decides something
`validate_fragment` already enforced — an enforcement proved by the code that
performs it is not proved: `citedFieldIds` is a subset of the **active Analysis
Field Profile**, refused fields never support the verdict, and exactly one axis
carries `lead`.

## What the machine decides, and what it must not

The deterministic layer (`src/eval/scoring.py`) decides six things on the Turn
lane: block structure, Evidence Manifest validity, `citedFieldIds` re-resolved
against the Turn's own traces, `answer_kind`, refusal presence, and a
direction-word lexicon inside `descriptive` answers. On the Analysis lane it
decides the three checks above, what the case expected the pipeline to do with
that seat, and the same direction lexicon over the artifact's prose.

**There is no LLM judge, anywhere in the scoring path**, and there is a test
that says so structurally rather than a promise in a docstring. An uncalibrated
judge is the same self-certification ADR-0010 rejected, and calibrating one
needs human labels first — so v1 collects the labels instead. Interpretation
fidelity and contradictory-evidence exposure are the human rubric's, and nothing
here guesses at them.

An individual case is an **Eval Case** and is never called a probe: **Capability
Probe** already means the boot-time LLM route contract test.

## The Eval Report

Every run writes `docs/eval/<date>-<prompt_version>.md` and stamps the path onto
`eval_run.report_path`. A **smoke** run's report carries the mode and a short run
id in its filename instead, so it can never occupy the name a baseline is read
from.

The report carries the run id, the mode, the route and exact model, the four
versions, per-category scores with the two lanes separable, the diff against
baseline, the three rubric questions, and the **verbatim answers being judged**.
That last one is not padding: it is one of ADR-0016's three defences against a
rubber-stamped rubric, because the text a reviewer scored stays readable in the
file.

Two things the report does **not** decide. It shows deterministic passes only —
the human rubric's scores enter the same thresholds in the pull request, not in
`eval_run` — and it never marks a run "passed": that word belongs to the
baseline query, which is arithmetic over the same totals.

## The baseline

The baseline is the **most recent passing gate run**, resolved from `eval_run` by
query (`src/eval/baseline.py`). Smoke runs and unfinished runs are excluded in
SQL; the per-category thresholds are applied in Python over the rows that come
back, because expressing them over JSONB would be a second copy of the same
rule in a dialect nothing tests.

A run that recorded a **hard fail** — a registered field narrated backwards in
sign or direction, at 1/3 — does not pass whatever its rates say, so it can
never become a baseline. The case ids are stored in
`eval_run.category_totals.hard_fails` and named at the top of the report.

- **A drop of two case-equivalents or more in any category is surfaced even
  while the category is above threshold**, and **must be explained in prose in
  the pull request**. It does not block the merge. A case-equivalent is a whole
  case's worth of passing — the rate change scaled by the number of cases — so
  the rule survives a battery that grew.
- **When `fixture_version` changes the previous baseline is void.** The run is
  marked `baseline_reset`, its report shows no diff at all, and **that pull
  request may not claim "no regression"**: comparing scores across two fixtures
  compares two different exams.

## The merge rule

There is no `.github/workflows` here, so this is a process rule rather than a
workflow file nobody runs.

**A pull request that touches any of the following must carry an Eval Report in
its body — run id, per-category scores, and the diff against baseline — and must
not merge into `develop` without one:**

- the System Prompt Contract (`src/agent/prompt.py`, `prompt_version`);
- tool schemas or `tool_catalog_version` (`src/agent/tools/`);
- the Signal Registry (`src/stocks/signals/`);
- the Analysis Field Profile (`src/alpha/field_profile.py`);
- `llm_model_*` — the route or either model;
- the agent loop (`src/agent/loop.py`);
- the Recommendation Validator.

**A pull request touching only UI, the Collector or Widget rendering needs no
gate run.**

Only a **complete gate run** may be attached. A smoke run has no gating value,
and a run that stopped at its ceiling has no score.

## What is not built yet

- The Turn lane's cases across the safety and false-refusal categories —
  issues #95 and #96. The Analysis lane's ten are seated
  (`src/eval/analysis_cases.py`).

Until the rest are registered, those categories report `∅` in the report rather
than a clean sheet, and a run missing a category cannot be a baseline.

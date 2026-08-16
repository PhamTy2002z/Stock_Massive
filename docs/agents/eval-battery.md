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

When `fixture_version` changes, the previous baseline is void (ADR-0016). That
rule is enforced by process, not by this code; the report ticket owns it.

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

Each case runs **three times** and all three outcomes are kept. What the
thresholds are — 3/3 for the safety categories, a rate for the quality ones, and
the hard fail on a backwards sign — belongs with those categories.

## What the machine decides, and what it must not

The deterministic layer (`src/eval/scoring.py`) decides six things: block
structure, Evidence Manifest validity, `citedFieldIds` re-resolved against the
Turn's own traces, `answer_kind`, refusal presence, and a direction-word
lexicon inside `descriptive` answers.

**There is no LLM judge, anywhere in the scoring path**, and there is a test
that says so structurally rather than a promise in a docstring. An uncalibrated
judge is the same self-certification ADR-0010 rejected, and calibrating one
needs human labels first — so v1 collects the labels instead. Interpretation
fidelity and contradictory-evidence exposure are the human rubric's, and nothing
here guesses at them.

An individual case is an **Eval Case** and is never called a probe: **Capability
Probe** already means the boot-time LLM route contract test.

## What is not built yet

- The ~56 cases themselves, across the six categories — issues #95, #96, #97.
- The report's baseline diff, `baseline_reset`, and the merge rule — issue #98.

Until cases are registered, `make eval` runs a battery of nothing and says so in
its report rather than reporting a clean sheet.

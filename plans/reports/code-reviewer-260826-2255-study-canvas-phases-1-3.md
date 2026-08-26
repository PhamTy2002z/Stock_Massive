# Code Review — study-artifact-canvas phases 01–03

Branch `feat/study-canvas` (bde4e00, 83c14f2, fcb6729 + docs commit c01c148)
against `refactor/harness-first`. Review only — no repository code was changed.

## Scope

- Files: 33 source/test files, ~2.100 LOC of Python + 1 line of TS + 2 generated
  contract files.
- Focus: `src/studies/*`, `src/stocks/intraday/*`, `AgentArtifact`, two alembic
  revisions, the studies/intraday test suites.
- Verification run: full API suite, full web gate set, alembic head/check/offline
  downgrade, and six adversarial probes against the arithmetic and the ingest
  (scratchpad only, not committed).

## Verified state (measured, not taken on trust)

| Gate | Result |
|---|---|
| `make test` (host, apps/api) | **1025 passed**, 28,4 s (plan records 1024) |
| `pnpm type-check` · `lint` · `test` · `build` | green — 406 tests / 32 files |
| `alembic heads` | single head `c2e94a7b1f30`, applied |
| `alembic check` | only pre-existing drift (`agent_knowledge`, `agent_message`); **nothing** from the two new tables |
| offline downgrade SQL, both revisions | clean index+table drops |
| studies → agent import | none — dependency direction holds |
| `.frames` readers outside `runner.py` | none |

Caveat on that first row: host `make test` reaches a **brew** Postgres on
`127.0.0.1:5432` that shadows the compose one, and its schema is maintained by
`Base.metadata.create_all` rather than by alembic (it sits at revision
`a4c71d9e5b28`). The alembic rows above were checked in the container, against
the compose database. See D8.

## Overall assessment

The structure is good and unusually well-argued: the declaration-with-no-defaults
contract, the import-time widget check, the per-run frame/widget/kind check in the
runner, and the two generated-contract equality tests are real safety, not
decoration. The session grid is measured rather than assumed and the correction
it records (ATC at 14:45) is load-bearing and well evidenced.

The arithmetic underneath it is where the problems are. **Two defects make the
model-facing headline say things the data does not support**, and both are
already visible in the artifact fixture this branch published. Three more sit in
the ingest, one of which aborts the database transaction on bad provider data.

Verdict: do not build phase 04 on top of D1–D3 without fixing them. A tool layer
that hands the model a `peakOccurrence` computed the way it is now will produce
confident Vietnamese sentences about a number that is an artifact of dictionary
ordering.

---

## Critical / High

### D1 — `avg_share` divides by presence count, so shares do not sum to 1 and quiet buckets are systematically inflated

`apps/api/src/studies/intraday_liquidity.py:248` and `:255-257`

`shares.setdefault(label, []).append(...)` only appends on sessions where the
bucket exists, and the mean divides by `len(shares[label])`. Three consequences,
in increasing order of harm.

**a) The documented invariant is false.** `_phase_summary`'s docstring
(`:268-271`) says "A phase's share is the share of the whole session that lands
in it, so the four add to 1", and the module docstring (`:31-32`) says the same.
Concrete input:

```python
by_session = {"d1": {"09:15": 50.0, "14:45": 50.0},
              "d2": {"14:45": 100.0}}
# phaseSummary -> {'ato': 0.0, 'am': 0.5, 'pm': 0.0, 'atc': 0.75}   sum = 1.25
```

**b) A bias, not just a rounding nit.** `ingest.py:186` drops blank buckets, so a
bucket's absence *means* nobody traded in it — a factual share of 0 for that
session. Averaging over only the sessions where it did trade over-states exactly
the buckets that are sometimes empty. The quieter the bucket, the larger the
over-statement. This is live: the branch's own smoke record
(`plans/260826-2158-study-artifact-canvas/plan.md`) is 3.985 rows over 250
sessions = 15,94 buckets/session against a 16-bucket HOSE grid, so real STB
sessions are missing buckets.

**c) The headline names the wrong peak window.** `:147` ranks by `avg_share`
alone. 29 ordinary sessions of 16 equal buckets plus one thin session holding
only `14:45`:

```
peak = 14:45   avg_share = 0.0938   peakOccurrence = "1/30"
runner-up = 09:15  avg_share = 0.0625
phaseSummary sum = 1.0313
```

The study announces as *the* peak window a bucket that was the peak once in
thirty sessions — the precise failure the module docstring says spike frequency
exists to prevent, except the ranking never consults it.

**Fix:** divide by `len(by_session)` (absent bucket contributes 0 share to that
session). The heatmap keeps `None` for display — that part is right and should
not change. The sum-to-1 invariant then becomes true, the bias disappears, and
the two tests that claim to protect it become able to fail. Decide the same
question for `avg_amount` explicitly, and put the denominator in the column
label either way.

### D2 — spike frequency ties are broken by clock order, and the published fixture already shows it

`apps/api/src/studies/intraday_liquidity.py:240-245`

`sorted(buckets.items(), key=lambda item: item[1], reverse=True)[:SPIKE_TOP_N]`
is a stable sort over a dict whose insertion order is `bucket_start` ascending
(`reads.bars_for` orders by it), so on a tie the earliest bucket wins the spike
credit.

Evidence from the repository's own generated artifact,
`contracts/fixtures/artifact-intraday-liquidity.json`, `headline.top3`:

```json
{"window": "09:15", "share": 0.0537, "avgAmount": 100000.0, "occurrence": "30/30"},
{"window": "09:30", "share": 0.0537, "avgAmount": 100000.0, "occurrence": "9/30"}
```

The fixture gives 09:15 and 09:30 exactly 100.000 in every one of the 30
sessions. "09:15 was among the two busiest buckets in 30 of 30 sessions" is not
a fact about the data; it is a fact about which key pandas inserted first. A
model reading this headline will write that sentence in Vietnamese to a user.

Second, smaller face of the same bug: a session with two or fewer stored buckets
gives *every* bucket spike credit (probe: 12 sessions of two buckets → both
report `12/12`).

**Fix:** credit every bucket tied at the cut (`amount >= second_highest`), or
skip the credit when the session holds `<= SPIKE_TOP_N` buckets, or require a
strict margin. Any of these; the current number is not reproducible from the
data.

### D3 — a repeated bucket in one provider frame aborts the transaction with an untyped error

`apps/api/src/stocks/intraday/ingest.py:227-242`

Verified empirically against the dev database (`ZZPROBE`, cleaned up):

```
RAISED: ProgrammingError (psycopg2.errors.CardinalityViolation)
ON CONFLICT DO UPDATE command cannot affect row a second time
```

Two problems, not one. The error type contradicts the module docstring
(`:17-20`: "a response whose columns are not the ones documented raises rather
than writing a partial day") — this is a valid-shaped response producing a raw
SQLAlchemy `ProgrammingError`. And a `CardinalityViolation` **aborts the
transaction**: in phase 04 that poisons the turn's session, so the
`agent_tool_call` row recording the failure cannot be written either. The lane
would lose the turn, not just the study.

**Fix:** dedupe `rows` on `(symbol, bucket_start)` keeping the last occurrence
before `insert().values(rows)`. One dict comprehension; also makes
`IngestOutcome.rows_written` honest (today it returns `len(rows)` — rows
*submitted*, not rows written).

---

## Medium

### D4 — NaN volume with valid prices raises a bare `ValueError`

`apps/api/src/stocks/intraday/ingest.py:199`, guard at `:215`

Verified: `ValueError: cannot convert float NaN to integer`. `_is_blank` inspects
only `open` and `close`. A NaN `high` is handled correctly (typed
`IntradayIngestError` from `_vnd`), but volume is not. Same contract violation as
D3, lower blast radius. Extend `_is_blank` to volume, or convert in `_vnd`'s
sibling.

### D5 — an interior gap is never refilled

`apps/api/src/stocks/intraday/ingest.py:155-167`

Verified: store 19 of 20 days with 2026-08-10 missing, then call
`ensure_bars(sessions=10)` twice. The second call asks
`(2026-08-22, 2026-08-22)` and the hole stays empty permanently. Because
`sessions_used` counts *stored* sessions, `intraday_liquidity` then reports
`health="normal"` (`intraday_liquidity.py:183`) over a window that silently skips
a trading day. The docstring at `:160-163` addresses the *short store* case; it
does not address a hole in the middle, and there is no test for one.

**Fix options:** compare `len(days)` against expected trading days before
choosing the warm path, or make the warm path ask from `today - sessions*2` days
(still one request, still idempotent), or record a coverage watermark.

### D6 — permanent full-year refetch for a symbol whose history is shorter than the question

`apps/api/src/stocks/intraday/ingest.py:165`

`stored_days < sessions` keeps the cold path forever for a newly listed symbol,
or any symbol with fewer than `sessions` sessions available upstream: every
question re-fetches 365 days and re-upserts thousands of rows in one statement.
Against the plan's ≤12 s cold / ≤8 s warm P50 budget this is a permanent worst
case rather than a first-call one.

### D7 — `_round` destroys any amount below 1 and rounds half-to-even

`apps/api/src/studies/intraday_liquidity.py:422-424`

Verified: `_round(0.4)=0.0`, `_round(0.5)=0.0`, `_round(2.5)=2.0`,
`_round(0.0004)=0.0`. Applied to `peakAvgAmount`, `top3[].avgAmount`, the tiles
value, and both amount columns of the `profile` and `ranking` frames. For an
illiquid symbol the headline states **0 shares** for a bucket that did trade —
the same false claim the module rejects for heatmap holes ("0 nghĩa là không ai
giao dịch, là một khẳng định sai"), made in the one place a model will read.

Secondary: it returns `float`, so the model-facing headline carries
`"peakAvgAmount": 380000.0` rather than `380000`.

### D8 — the study tests delete a real symbol's rows, and only a local accident keeps that harmless

`apps/api/tests/studies/test_intraday_liquidity.py:52-54` and
`apps/api/tests/studies/artifact_fixture.py:105`

Both issue `DELETE FROM bar_intraday_15m WHERE symbol = 'STB'` — the real
symbol, not a synthetic one. `test_ingest.py` and `test_reads.py` get this right
(`INGST`, `READS`), and the study tests already inject Universe membership via
`monkeypatch`, so nothing forces the real ticker.

What saves it today is an accident of this machine, not the design. Verified:

- a brew Postgres (PID 923) binds `127.0.0.1:5432` and shadows the Docker one,
  so host `make test` writes to the **brew** `stockmassive`, where
  `bar_intraday_15m` holds 0 rows;
- the Docker `stockmassive` still holds the smoke window intact —
  `select symbol, count(*) … group by symbol` → `STB | 3985`, matching the
  3.985 rows the plan records.

Point the suite at the compose database — which the project's own guidance for
host runs prescribes (`DATABASE_URL` at the LAN IP rather than `localhost`), and
which any CI job would do — and `make test` deletes those 3.985 real rows.

Related finding from the same check, pre-existing rather than introduced here but
newly load-bearing: the brew test database sits at alembic revision
`a4c71d9e5b28` while `bar_intraday_15m` exists there anyway, created by
`Base.metadata.create_all(checkfirst=True)` in the test fixtures. **`make test`
therefore never exercises either of the two new revisions** — the migration path
is only proven in the container. Worth knowing before trusting a green suite as
evidence that the schema change is sound.

### D9 — nothing imports `src.studies`, so the import cost and the import-time check both land on first use

`apps/api/src/studies/__init__.py:29` → `src/stocks/intraday/__init__.py:13` →
`ingest.py:36,40`

Measured on this machine: `import src.main` = 1,12 s and does **not** load
vnstock; `import src.studies` then costs a further 2,10 s warm, 6,11 s cold.
Phase 02's stated intent ("import pandas/vnstock ở module load (container
start), không import lười trong handler — audit N11") is not achieved yet,
because no module loaded at startup imports studies. Unless phase 04 imports the
studies package from something `src/main` pulls in, the first canvas question
pays those seconds out of the ≤8 s budget.

Same cause, second effect: `registry._check` — the import-time guard that refuses
a widget no viewer has — never runs at boot today. A broken Study declaration
would be discovered by the first user question, not by the container failing to
start.

---

## Low

### D10 — the settle rule is written twice, and one copy is dead

`apps/api/src/stocks/intraday/reads.py:72-85` vs `:138-153`. Both are correct
today and both encode "closed once 15:00 VN has passed". `latest_closed_session`
has no caller anywhere in the repo. `_closed_days(session, symbol, now=now)[:1]`
collapses them. Also `reads.py:160` exports `day_in_vn`, which the module imports
and never uses.

### D11 — `bars_for(now=...)` silently trusts the process timezone for a naive value

`apps/api/src/stocks/intraday/reads.py:142-143`. `astimezone` on a naive
datetime interprets it as system-local. Verified that the real caller is safe:
`context.as_of` is aware UTC and converts correctly. On a UTC container a naive
`now` would move the closed-session boundary by seven hours. One
`if now.tzinfo is None: raise` removes the class.

### D12 — a session whose stored volume is all zero gets two different answers

`intraday_liquidity.py:248` records share `0.0`; `_heatmap_frame:338-341` records
`None` for the same cells. The session still counts toward `sessionsUsed` and
toward the spike denominator, and the two earliest buckets collect the
tie-broken spike credit (verified). Reachable when a bucket carries a price with
zero volume.

### D13 — an off-grid bucket would inflate the denominator while being invisible in the numerators

`intraday_liquidity.py:239` sums *every* label in the session for `total`, while
`:260-262` only emits labels that are in `SESSION_BUCKET_LABELS`. Unreachable
through the current ingest (labels are derived from grid-filtered timestamps),
but it is an asymmetry by construction rather than by check. Relatedly,
`_phase_summary:275-277` would raise `ValueError: hour must be in 0..23` on a
label that is not a time.

### D14 — CLAUDE.md states a guarantee that has no test behind it yet

The amended CLAUDE.md says "`StudyResult.frames` … **không bao giờ** vào message
gửi model. … **Test đọc transcript giữ luật này.**" No such test exists — it is
phase 04 work, and the plan's acceptance criterion #2 still lists it as pending.
`contracts.py:17-18` and the `AgentArtifact` docstring make the same claim in the
present tense. A forward-looking promise written into the repository's authority
document is the kind of confident sentence a later reader will build on.

### D15 — scope hygiene (not in these three commits, but in the branch working tree)

`apps/web/package.json` has an uncommitted devDependency `agentation ^3.0.2`,
and an untracked `apps/web/src/components/dev/agentation-toolbar.tsx` is wired
into `apps/web/src/app/layout.tsx`'s `RootLayout`. Under "không thêm dependency
mới nếu chưa hỏi", make sure this does not ride along in the phase-04 commit.

---

## Answers to the specific questions asked

**Frames never reaching the model — structural or conventional?**
Structural at the runner boundary, conventional beyond it. `StoredArtifact`
(`contracts.py:255-270`) is the only value `run()` returns and carries no frames;
grep confirms nothing outside `runner.py` reads `.frames`. Two residual channels:
(a) `definition.compute` is public and `StudyResult` is exported from
`src.studies.__all__`, so a phase-04 tool could bypass `run()`; (b)
`canvas_spec` *is* on `StoredArtifact`, and `CanvasBlock.options` is a free-form
`Mapping[str, Any]` chosen by `view` — a view that computed a max or a domain
into options would put numbers on the model-facing side without tripping any
check. No current view does. Phase 04's test should assert on the **tool result
payload keys**, not only on the transcript.

**`median` over an empty list.** Unreachable. `_bucket_statistics:260-262` only
emits labels present in `amounts`, and every list there has at least one element.
Verified.

**Division by zero on a zero-total session.** Guarded in both places
(`:248`, `:338-341`), but inconsistently — see D12.

**`context.as_of` (UTC) through `bars_for`.** Works correctly; verified by probe
and by `test_reads.py`. The latent hazard is naive input, not UTC input (D11).

**Timezone handling in `moment.to_pydatetime().replace(tzinfo=VN_TZ)`.**
Correct *given* that vnstock returns naive VN-local timestamps, which the probe
record supports, and `VN_TZ` is a `ZoneInfo` so `replace` carries no LMT offset
trap. It is a relabel, not a conversion — if the provider ever starts returning
aware UTC timestamps the whole store shifts seven hours silently, and
`phase_of(moment.time())` at `:185` would misfile the phase too. A one-line
assertion that the incoming timestamp is naive would pin the assumption.

**`_vnd` precision.** `(Decimal(str(value)) * 1000).quantize(Decimal("0.0001"))`
against `Numeric(20,4)` — sound, no context-precision risk at VND magnitudes.

## Test quality

Real assertions, on the whole: the golden session grid, the negative registry
cases, the runner's four failure modes, and the two generated-contract equality
tests all fail for the right reasons. Four weaknesses:

1. `test_intraday_liquidity.py:112-119` and `:131-140` assert the sum-to-1
   invariant against a fixture where **every session has every bucket** —
   line 118 (`assert len(cells) == len(HOSE_BUCKETS)`) pins that. The invariant
   they claim to protect is exactly the one D1 breaks, and the fixture is
   constructed so they cannot fail. Add one session missing a bucket.
2. `:105-109` computes the expected `peakAvgAmount` with denominator
   `TOTAL_SESSIONS`, which matches the implementation only because the spike
   bucket is present in all 30 sessions. It would pass under either denominator —
   it does not pin the choice.
3. No coverage for: a duplicate bucket in one frame (D3), NaN volume (D4), a tie
   in the spike ranking (D2), a `total == 0` session (D12), or an interior gap
   (D5).
4. Cleanup is correct — `get_sync_db` commits on exit (`src/core/database.py:74-84`),
   so the teardown deletes land. The problem is *what* one of them deletes (D8).

## What will bite phase 04

1. **Five distinct escape paths** out of a study run, of which the phase-04 file
   documents two: `StudyRefused` (→ `ok` / `no_value:`), `StudyParamsInvalid`
   (→ retry), `RuntimeError` from the runner's checks, `IntradayIngestError`,
   and the uncaught `ProgrammingError` of D3 — the last of which leaves the
   session unusable for the `agent_tool_call` write.
2. **`requires=("intraday_bar_15m",)` is inert.** Nothing maps it to
   `ensure_bars`, and `compute` never ingests. The plan's "lần đầu hỏi một mã →
   backfill 1 năm" has no trigger yet; phase 04 has to supply it, and D6 decides
   how expensive it is.
3. **`runner.run` flushes, it does not commit.** If the tool tells the model an
   artifact id and a later step in the turn rolls back, the id points at nothing.
4. **Authorization.** `agent_artifact` has no owner column; the only route is
   `thread_id → agent_thread.user_id`, and `thread_id` is nullable. A
   `GET /artifacts/{id}` written as "no thread ⇒ no owner ⇒ public" would leak.
   UUIDv4 unguessability is not authorization. Decide the rule for null-thread
   artifacts before the endpoint exists.
5. **Import placement** — D9.

## Recommended actions, in order

1. Fix D1 (share denominator) and D2 (tie-breaking). Both change the numbers a
   model narrates, and both need `contracts/fixtures/artifact-intraday-liquidity.json`
   regenerated via `make contracts` afterwards.
2. Fix D3 (dedupe before upsert) and D4 (NaN volume), with tests for both.
3. Fix D8 (use a synthetic symbol) before anyone points the suite at the compose
   database. Also note that `make test` on this machine does not run against the
   migrated database at all.
4. Strengthen the two sum-to-1 tests with a session that is missing a bucket, so
   D1 cannot come back.
5. Decide D5 (interior gap) and D6 (permanent cold path) explicitly — either fix
   or record as accepted with the reason.
6. Fix D7 (`_round` below 1, banker's rounding, float in the headline).
7. Collapse D10, guard D11, reconcile D12.
8. Soften the CLAUDE.md sentence in D14 to "phase 04 will pin this by test", or
   land the test with phase 04 and leave the sentence.

## Metrics

- API tests: 1025 passed (0 failed), 28,4 s.
- Web: 406 passed / 32 files; type-check, lint, build green.
- Python type coverage: not measurable — no mypy/ruff configured
  (`make lint` is `py_compile src/main.py`). One `Any` widening noted at
  `runner.py:130` (`definition: Any` where `StudyDefinition` would do).
- New dependencies: none in these three commits (D15 is in the working tree,
  uncommitted).

## Unresolved questions

1. Is the presence-count denominator in `avg_share` (D1) a deliberate estimator
   choice? Nothing in the plan or the docstrings suggests so — both claim the
   opposite — but if it was, the invariant claims need to go and the choice needs
   a sentence.
2. Has VCI ever been observed returning a bucket twice in one frame? D3 is a
   defect regardless of the answer (the failure mode is disproportionate), but
   the answer decides whether it is urgent or merely required.
3. `latest_closed_session` and `sessions_available` have no callers. Are they for
   phase 04, or leftovers?

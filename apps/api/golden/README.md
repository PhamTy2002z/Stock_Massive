# Golden — the smallest measurement that lets C1 graduate on numbers

Three files. A corpus, a runner, a grader. That is the whole thing, and keeping
it that small is the design rather than a stage it will grow out of.

## What "cited" means here, and why it is not what it sounds like

**Written before the first grader, because the last two eval batteries died of
scoring a contract the runtime did not emit.**

The system prompt **forbids** citing sources inside the answer. Verbatim, from
`src/agent/prompt/sections.py`:

> *"Tra rồi thì nêu thời điểm, **đừng nêu nguồn**. Giao diện đã hiển thị các
> trang bạn vừa tra ngay cạnh câu trả lời […]"*
>
> *"**Không viết phần dẫn nguồn.** Không dòng bắt đầu bằng Nguồn, không đường
> dẫn dán vào văn bản, không chú thích đánh số […] Việc đó là của giao diện."*

So a grader looking for footnotes would score every well-behaved Turn as
uncited. The roadmap's *"every figure outside the store has a citation"* means
something else, and it means something already observable:

> A number in the answer is **cited** when it appears in a page this Turn read,
> in a search result this Turn received, or in a store result this Turn got —
> that is, when the source list drawn beside the answer covers the figure the
> answer used.

The chain that carries it exists today and nothing here invents it:

```
display_results()      →  ToolCall.results  →  SourceList
messages.py               types.ts             source-list.tsx
```

Two details of the comparison are deliberate:

- **Numbers are canonicalised, not string-matched.** `1.234,5` and `1,234.5` are
  one quantity; a string comparison would call an honest answer uncited purely
  because the supporting page writes numbers the other way round.
- **Rounding counts as covered, invention does not.** An answer saying `12,3`
  where the page says `12,34` has rounded. One saying `15,9` has not.

Years, and integers of twelve or less, are not treated as claims. They are
counts and dates far more often than figures, and charging them to the answer
would bury every real finding.

## Anti-repeat contract

`plans/260823-1744-investment-intelligence-eval-replay-harness/` is the full
post-mortem of a battery that was built, deleted, rebuilt and deleted again. It
names four causes. Each one has a rule here, in this file's own words:

| How the old one died | The rule here |
|---|---|
| It scored a contract the runtime had stopped emitting, so verdicts quietly became `unavailable` | **No grader for a field that is not in a real artifact.** All four read fields the runtime emits today. A grader that cannot fail leaves the file; it does not wait for a later phase |
| Fixtures ran to 160k–190k rows and bound the suite's identity to the store's schema | The corpus is **one JSON file of twenty questions**. No store snapshot, no frozen row, no digest chain |
| Eval state was threaded into production persistence and admission | **No table, no migration, no budget lane, no lifecycle hook.** The artifact is a local file. The runner's only footprint is one synthetic account, and every baseline query filters it out |
| Thresholds were tuned on an exam that had gone out of date | **No threshold before a distribution.** The grader reports spread and per-case findings; phase 08 sets the bars after looking at real numbers |

And one rule the old battery got right, kept unchanged: **a grader never
branches on a case id.** The case's data decides which checks apply; the logic
is the same for every case.

## Where it lives, and why not `src/eval/`

`apps/api/golden/`, outside `src/`. Production cannot import it — that is a
property of the layout rather than a promise somebody has to keep. The reverse
is allowed and is the point: the runner reads the public seams of `src.agent`.

The name `eval` is not reused. It has been deleted twice and it carries the
expectation of a much bigger machine than three files.

## Running it

```
make golden-run   CEILING_USD=1.50          # spends real money; ceiling required
make golden-run   CEILING_USD=1.50 GOLDEN_ARGS="--replay"
make golden-grade ARTIFACT=golden/artifacts/<file>.json
```

There is a fourth file, and it answers a question the other three cannot.

```
make golden-context-export ARTIFACT=golden/artifacts/<file>.json
make golden-context-replay OUT=/tmp/replay.json
```

`context_replay.py` rebuilds **every context a finished run constructed**, from
that run's own trace, through the same public context builder the loop uses. It
exists because a token measurement made by running the corpus again is three
measurements added together — the code changed, the Internet changed, and the
model sampled differently — and only the first of those belongs to a change in
how context is built. The tape removes the second; this removes the third.

`export` is the only half that touches a database. `replay` is pure: no network,
no model, no clock — the date in the prompt is pinned at `REPLAY_DATE` — so the
same corpus gives byte-identical output on any machine, today or in a month.
It decides nothing and enforces nothing; it prints where the tokens went.

What it cannot recover is one thing, named rather than hidden: the guardrail's
sentence about a call the harness **refused before dispatch** travels in the
message and is persisted nowhere. It is a fixed constant per reason, identical
in every replay, so it cancels in a delta — and the report carries
`refused_calls` so the size of the gap is readable. Measured against the ledger
on the corpus it was built from: 78 model calls in the replay against 78 rows in
`llm_call_usage`, and 797,722 tokens against 800,628 reserved — **0.36% apart**,
all of it those sentences.

- **`CEILING_USD` has no default.** A runner that can start without a ceiling
  eventually will, and the whole model envelope is $45 a month.
- **Grading never touches the network, the database or a model.** It is a pure
  function of the artifact, so re-grading a months-old run is free and gives the
  same answer it gave that day.
- **The web is taped, the model is not.** `WebLane` serves searches fresh for 30
  minutes and pages for 24 hours, so two artifacts weeks apart would otherwise
  differ by code *plus the Internet* plus sampling. Recording and replaying at
  `WebLane.read` removes the middle term. The model stays live because what it
  chooses to search and read is the thing being measured.
- **A half-green run is not a run.** Reaching the ceiling, losing a case, or
  missing a replay key all end as `incomplete`, never as a slightly worse pass.

**The runner runs on the host, and the host's environment is not the
container's.** `make` runs from `apps/api`, and `Settings` reads `.env` relative
to the working directory — so the repository's `.env`, which lives at the root,
is not loaded at all. Two of its values are the container's anyway:
`LLM_BASE_URL` names `host.docker.internal`, which does not resolve on the host,
and `DATABASE_URL` defaults to `localhost`, which on a machine running Homebrew
Postgres reaches *that* server rather than the one in Docker. A run started
without fixing both looks like a code failure — every case ends
`gateway_timeout` with zero spend — and is not one:

```
set -a && . ../../.env && set +a
export LLM_BASE_URL="http://127.0.0.1:8317/v1"
export DATABASE_URL="postgresql://postgres:postgres@<LAN-IP>:5432/stockmassive"
make golden-run CEILING_USD=2.5 GOLDEN_ARGS="--out golden/artifacts/<name>.json --tape golden/artifacts/<name>-tape.json"
```

Written down because the failure is silent in the direction that wastes a run:
the wrong `DATABASE_URL` still creates threads, still writes turns, and still
produces an artifact — of a different database.

## The thresholds

Set on 2026-08-29 from three real runs, after looking at the distribution and not
before — which is the rule this file opens with. They live here and nowhere else:
a bar written into a grader is a bar that gets tuned by whoever is failing it.

Full reasoning, and the numbers each bar was read off:
`plans/reports/phase-08-260829-c1-verification.md`.

| Grader | Bar | Denominator |
|---|---|---|
| `distinct_domains` | **≥ 18/20** cases meet their own declared bar | 20 |
| `read_depth` | **≥ 16/20** cases meet their own declared bar | 20 |
| `parallel_rate` | **≥ 50%** of rounds issue more than one search | rounds, not cases |
| `uncited_external_number` | **no bar — reported, never gating** | 16 |
| latency P50 | signal with a range; a rise over 20% is explained, not auto-failed | 20 |
| cost per Turn P50 | signal with a range, under `TURN_COST_MICRO_USD` | 20 |

Two of these need their denominator said out loud, because two thresholds written
before the corpus existed got it wrong:

- **`uncited_external_number` is out of 16, not 20.** Four cases deliberately do
  not require it (`wf-009`, `wf-013`, `wf-017`, `wf-019` — the families where a
  correct answer may carry no figure at all), and the grader returns `None` rather
  than a pass for them. A bar of "18/20" on this grader is arithmetically
  unreachable.
- **`distinct_domains` is per-case, not a flat three.** The corpus declares a bar
  of 2 for ten cases and 3 for ten. The grader scores each case against its own.
- **`read_depth` is per-case too, and that is its only authority.** The flat
  statement `fetch_url >= 2` is a **diagnostic** and never a gate. It cannot read
  a case's own bar, so it fails a case declaring `min_pages_read: 1` that met its
  contract exactly. Both numbers are reported; only the per-case one decides.

### Why `uncited_external_number` does not gate

It was read against every case it failed on the final run. **Four out of five were
honest, well-sourced answers**, and eight of the nine flagged figures were either a
unit conversion (a page writes `tỷ`, the answer writes `nghìn tỷ`) or arithmetic
over numbers that *are* covered — the difference between two sources, a percentage
of a position, a figure the question itself supplied.

The fifth, `wf-012`'s `100`, is a **real finding**: the answer states a foreign
ownership ceiling of `100%` for HPG and no page in that case's evidence says what
HPG's ceiling is — the nearest result is a headline about a *different* company
raising its own to 50%. It is a constant the model supplied, not one it read.

The grader asks *does this number appear verbatim in the evidence*. The criterion
asks *is this number supported by the evidence*. Those coincide for an answer that
only copies, and separate the moment an answer does arithmetic — which is exactly
what the `conflicting_or_missing` family asks for. The two best answers of the run
were failed for computing a subtraction.

So it stays in the file as a **count worth reading** and is never a verdict.

**And the "real fix" named here was tried, measured, and abandoned — do not
rebuild it.** A grader that searches for a derivation cannot work at this corpus's
scale, and the reason is arithmetic rather than effort. One case's premise set runs
to **109–310 numbers**, and tightening three ways at once — magnitude-word scales
only, operands of three significant digits or more, no ×100 — still leaves **38–221
operands**. A single `+ − × ÷` over that reaches **92.7–100% of the entire
three-significant-digit value space** on four of the five cases (`wf-012`, the
smallest pool, reaches 55.2%), so a fabricated number finds a "witness" just as
easily as an honest one: **39 of 40** fabricated mutations were accepted. Dropping the binary operation cut
false accepts but took recall down to **3 of 9**. Keeping false accepts under 5%
requires an operand pool of **eight numbers or fewer**; the real pools are an
order of magnitude past that. A third design, restricting operands to figures the
answer itself already grounded, cut the reachable space to 1.4–25.7% but recalled
only 6 of 9 and still accepted 28% — and it justified `wf-012`'s `100` with
`25 + 75`, where `75` is the figure the answer derived *from* `100`.

Measuring this criterion needs the runtime to **record what each claim was derived
from**. That is a claim-provenance contract, and it belongs to C4. Full numbers:
`plans/260829-1945-c1-evidence-graduation/reports/phase-01-260829-derivation-depth.md`.

## What the artifact carries beyond the four graders

Three things are recorded and **not** scored, on purpose.

- **`cost` and `turn.wall_ms`** are continuous distributions. A binomial gate on
  twenty cases is a valid gate; a threshold on a median of twenty latencies is a
  number that moves with the Internet. They are reported with a range and read
  as signals.
- **`cost` names four token counters, and `input_tokens` is not the prompt.**
  The transport splits what the provider reports so the cheap cached part is not
  billed at the full input price, which means that column holds the **fresh**
  prompt only. Beside it are `cached_read_tokens`, `cache_write_tokens` and
  their sum as `prompt_tokens`. The old name keeps the old column so an artifact
  written before this line stays comparable with one written after it — what
  changed is that the three counters beside it say what the name never did.
  Measured on `web-first-v1-final`: 489,106 fresh against **492,032 cached
  read**, so the route's automatic prefix cache was already serving **50.1%** of
  the prompt with `llm_prompt_cache_control_enabled` off.
- **`tool_calls[].scan`** is the advisory threat scan's verdict on each result,
  read straight off the persisted call payload. It is here so the rate at which
  the scan fires on *ordinary* market pages can be measured before anybody
  decides to show a warning to a reader — a warning light that cries wolf on a
  clean corpus is worse than none. No grader reads it yet, and that is the
  correct state: there is no threshold before a distribution.

## The runner's account

`golden-runner@stockmassive.local`, created on first run. It exists for two
reasons that pull the same way:

- The per-user ceilings are relaxed for it and must not be relaxed for anyone
  real. `turn_starts_per_day` defaults to **20**, which a twenty-case corpus
  hits exactly — one retry and the run dies. The run's own `--ceiling-usd`
  replaces the spend guard, and every call is still reserved and reconciled into
  `llm_call_usage`.
- The runner writes into the same tables the baseline is measured from, so every
  baseline query filters this address out. Measuring the system must not change
  what is being measured.

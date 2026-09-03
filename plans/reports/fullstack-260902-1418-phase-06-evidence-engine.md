# Phase 6 — Evidence engine: what was built and what the gates measured

Branch `feat/phase-06-evidence-engine`. Base `a10f470`. Plan:
[`plans/260902-0026-phase-06-evidence-engine/plan.md`](../260902-0026-phase-06-evidence-engine/plan.md).
Authority: [`docs/roadmap.md`](../../docs/roadmap.md) Phase 6, §2, §6, §9.

## What the deep lane does now

One Turn, one loop, one envelope, four stages:

```text
planning        four independent web_search facets in one batch
   ↓            price/movement · event · company/industry · counter-thesis
research        fetch the strongest pages → typed draft claims, or a question
   ↓
counterevidence attack the draft with deliberately disconfirming reads
   ↓
verification    tool-free strict-schema call over bounded typed evidence only
   ↓
deterministic validation → ledger-only renderer → terminal Turn
```

Each real transition emits one `pipeline_pass` progress part. The passes share
the Turn's owner, deadline, round count, external-call count and monetary
envelope; they do not reset any counter. The light lane is untouched.

Verification fails closed for the *label* and open for the *answer*: a provider
error, a timeout, a schema violation or an exhausted budget all settle a
`complete` Turn whose ledger says `unverified` with a concrete reason. There is
no path that renders an unchecked claim as checked, and no path that returns a
blank screen.

## Gates measured

| Gate | Result |
|---|---|
| `pytest tests/` | **1456 passed** (Phase 5 closed at 1401) |
| Focused Phase 6 suites | 45 passed (policy · store · pipeline · renderer · contract) |
| `tests/test_agent_evidence_elicitation.py` | 14 passed |
| `tests/golden/` | 131 passed |
| `alembic upgrade → downgrade -1 → upgrade` | clean round trip; `pg_dump` backup taken first |
| `compileall src golden tests` | OK |
| `git diff --check` | clean |
| Retired-path scan | 1 hit, and it is a sentence stating the capability does not exist |
| `pnpm lint · type-check · test · build` | green; 458 web tests |
| `make golden-release CEILING_USD=25 TRIALS=3` | **see "The paid run" below** |

## Three findings worth more than the code

### 1. Publication time exists now, and it exposed a real defect

Phase 1 measured `published_at` on **0 of 981** source observations and recorded
`temporal_validity` as `BLIND` — the §2 rule could not be checked because the
field did not exist anywhere in the pipeline.

The Phase 6 extractor was run against the **173 distinct pages the three
`as_of` cases actually cited**. Result: **112 dated, every one at high
confidence** — 98 from HTML metadata, 14 from JSON-LD. The remaining 61 are 48
pages that carry no date at all and 13 that no longer answer (403/401/404/
connect error).

Re-grading the frozen Phase 1 baseline against the curated corpus turns
`temporal_validity` from `BLIND` into **3 cases decided, 1 passed**. Two of the
three `as_of` cases cited sources published *after their own cutoff*. That
defect was always in the baseline; nothing could see it until the field existed.

An earlier attempt to curate the same dates off the recorded tape returned
**0 of 47** and the reason is a design decision holding rather than a gap: the
tape stores extracted page text, Vietnamese publishers put the date in
metadata, and the visible-text pattern is anchored to an explicit label. The
strings it refuses are real — VnExpress's site-wide `Thứ ba, 1/9/2026` header
and Vietnamnet's press-licence `cấp ngày 17/10/2025` both sit near the top of
the page, and neither is a publication time. A looser pattern would have dated
every VnExpress article with the day it was fetched.

### 2. Ground truth: three frozen, one deliberately refused

| Case | Frozen value | Source class |
|---|---|---|
| `rl-mc-001` VCB charter capital | 83.557 tỷ đồng | issuer |
| `rl-mc-002` HPG shares outstanding | 8.442.964.520 | aggregator + corroboration |
| `rl-mc-003` refinancing rate | 4,5%/năm (1123/QĐ-NHNN) | primary document |
| `rl-mc-004` HPG foreign-ownership ceiling | **not frozen** | — |

Each frozen value carries its source URL, source class, publication date and
tolerance. The traps are recorded beside them: VCB's 94.238 tỷ is a plan the
April 2026 AGM approved and not the registered capital; HPG's figure is a unit
trap, so an answer saying only "8,44 tỷ" has not stated it.

`rl-mc-004` is unfrozen on purpose. The issuer, HOSE and the aggregators were
searched and **no page states HPG's own published ceiling** — what they offer is
the general rule (49% / 50% / up to 100% by shareholder decision), which is
exactly the substitution this case was written to catch. Freezing one of those
would make the corpus assert a figure no source states, which is the failure the
whole phase exists to prevent. The grader scores it `None` rather than a pass.

**Handed to the golden owner:** if no public page states the ceiling, the
correct behaviour is refusal, and this case may belong to the refusal family
rather than to material-claim.

### 3. The router reaches 4 of 40 cases, and that limits what the gate can say

Routing the release corpus through `lanes.route_reason` offline:

```text
36 light / 4 deep
deep: rl-tc-001, rl-tc-002, rl-tc-004 (thesis_check), rl-fv-004 (fact_verification)
```

`event_memo` and `source_conflict` — two of the four jobs §1 built the deep
pipeline for — route **light**, because their questions never contain "memo" or
"kiểm chứng" and fall under the 240-character length rule.

This is the routing-quality question Phase 3 explicitly handed to Phase 6, and
lane config is a two-way door under §9. It was **not** changed here, and the
reason is measurement discipline: widening the keywords mid-run would produce a
baseline describing a system nobody ran.

The consequence has to be stated plainly rather than buried: **a Phase 6 gate
run in which 90% of the corpus never reaches the capability the phase built
cannot be read as a verdict on that capability.** The hard dimensions it
measures are real, but they are largely measuring the light lane.

## Two duplications removed rather than added to

`settle_with_question` no longer writes a question terminal of its own. It
builds an outcome and goes through `_finish`, so exactly one place orders the
three writes (message + `agent_question` row in one transaction → publish the
question → publish the terminal). A second copy of that ordering would have been
a second place to get it wrong.

The research-draft parser no longer truncates an over-long option list. Cutting
five options to four would hand the gate a legal card the model never proposed —
the same reasoning `parts.py` already applies to a prompt: refused rather than
truncated, because a cut question asks something else. The gate refuses it, and
a test holds that through the real parse path rather than on the gate alone.

## Elicitation: what a backend can enforce, enforced once

`evidence/pipeline.elicitation_part` is the only place that decides. It requires
a completed web read (scout-then-ask), a thread that has not asked before (one
round before a memo, read off the new `TranscriptTurn.asked`), a non-empty
prompt, 2–4 options each carrying an impact, and a stated default assumption.

Whether the unknown is genuinely non-discoverable and genuinely branch-changing
is planner judgement and is not mechanically checkable; everything that is
checkable is refused rather than trusted.

A refusal is never an error. It becomes a printed assumption on the draft, and
the Turn goes on to its memo. `test_a_thread_that_already_asked_writes_a_memo_and_says_why_it_did_not_ask`
holds exactly that: the Turn still produces a verified ledger, and the reason it
did not ask is in the assumptions the memo prints.

## One-way doors: none opened

Public HTTP/SSE envelope and endpoints unchanged; `part.progress` gains one
closed kind (`pipeline_pass`) with no new event type. Database additive only —
three new tables, no drop, no mutation of historical messages or traces; the
downgrade removes only Phase 6 data. Tool catalog still exactly five. Default
permissions unchanged. The research/advice boundary is preserved, not
reinterpreted. The truth contract is implemented as written.

## Rollback

The branch reverts as one unit; the light lane is the baseline and no capability
needs disabling. The migration downgrade drops only the three Phase 6 tables.
Cache and trajectory rows have no effect on old code and may be left to expire.
Prompt version and evidence-policy version move together, so a rollback cannot
mislabel a new-policy row as an old-policy result.

## The paid run, and the two defects it found

`make golden-release CEILING_USD=25 TRIALS=3` was authorized at a $25 ceiling
and started from the host with the root `.env` loaded, `LLM_BASE_URL` pointed at
`127.0.0.1:8317` (the stored value is the container's `host.docker.internal`)
and `DATABASE_URL` pointed at the LAN address, because a local Homebrew Postgres
shadows the container on `localhost`. Both configured models were probed as
reachable before anything was spent: `gpt-5.6-terra` and `gpt-5.6-luna` on a
route serving 27 models.

**The run was stopped deliberately after 8 of 120 Turns**, because the outcome
table said it was measuring nothing:

```text
incomplete · user_active_turn   112
complete   · —                    7
running    · —                    1
```

Four real defects in total, none of which 1,463 unit tests could see, and each
now fixed with a test that would have caught it. Three were found only because a
paid run was attempted; the fourth was introduced while fixing the others and
found by querying the live table.

### Defect 1 — the harness waited less than the Turn it started

`await_terminal` polled for a fixed **60 seconds**. That was correct while every
Turn was a light one. The deep lane is given **1,800 seconds** on purpose, so
the first deep Turn outlived the poll; the harness gave up, released its
concurrency slot and moved on — while the Turn it abandoned was **still
active**. Admission counts what the table says is active and allows one Turn per
user, so every case after it was refused with `user_active_turn`. One unfinished
deep Turn cost **112 of 120 case-trials**.

The wait is now read off the lane the question routes to, using the same
`route_intent` the service routes with, plus a 30-second margin for the terminal
write to become visible. `test_the_terminal_wait_covers_the_lane_the_question_routes_to`
holds the ordering that matters: the harness may never stop waiting before the
Turn's own clock runs out.

### Defect 2 — the research pass was asked for a shape, not held to one

The verifier call carries a strict schema. The research and counterevidence
passes did not: they were *asked* by a prompt note to return one JSON object.
On the live route the research pass wrote a memo instead, `parse_research_draft`
raised, and the whole pipeline settled `research_draft_schema_invalid` — a Turn
that had done 7 external reads and gathered 19 sources threw all of it away over
an envelope.

A strict format cannot simply be applied to the pass itself: it is holding a
tool conversation, and the format would bind every round of it. So the shape is
enforced on the one call that has stopped calling tools. On a parse failure the
pipeline now makes **one** bounded, tool-free, strict-schema retry that
transcribes the pass's own prose into the typed draft — the bounded-nudge
discipline §7 adopts from Hermes — and fails honestly if that also misses. It
spends the same owner, deadline and envelope, and costs nothing when the model
complies. Two tests hold both halves: the memo survives one miss, and a second
miss is still a failure rather than a loop.

### Defect 3 — a hard dimension held the deep lane to the light lane's budget

Found by grading the verified deep case rather than by reading code:

```text
[FAIL] rl-tc-001 budget   19 dispatched external calls over a cap of 7
```

The deep lane's cap is **20**. Seven is the light lane's. `runtime_constants`
recorded a single flat pair of ceilings — the module-level constants, which
since Phase 3 *are* the light lane's values — and `grade_budget` applied them to
every case. `budget` is a **hard** dimension, so every deep case in a release run
would have failed it for doing exactly what the lane was configured to do.

The grader's own docstring already had the principle right — "the ceilings are
lane configuration from Phase 3 onward and a number copied into a grader is a
number that goes stale where nobody looks" — but the artifact it read from had
not caught up. The artifact now records the ceilings **per lane**, and the
grader resolves them through the same `route_intent` the service routes with.
Artifacts recorded before the field existed fall back to the flat pair, so old
runs still grade. Two tests hold both directions: the same call count passes on
a deep question and still breaches on a light one, naming which lane's ceiling
it broke.

### Defect 4 — one I introduced, and it was invisible by design

Relabelling the planner's trajectory row from `research` to `planning` was
correct in intent and made things worse: the store validates the stage against a
hand-written allowlist that had drifted from `PipelineStage` and did not contain
`planning`. The loop treats a failed trajectory write as a lost trace rather
than a lost answer — correctly — so the row did not error anywhere a reader
would look. It simply stopped existing. Every deep Turn lost its planner's four
queries from the audit trail, and the only evidence was a log line:

```text
WARNING Could not persist planning evidence trajectory:
        unsupported evidence trajectory stage: planning
```

Found by querying the live table for stage counts and noticing `planning` was
absent, not by any test. The allowlist now contains it, and
`test_every_pass_the_loop_can_record_is_a_stage_the_store_accepts` holds the two
vocabularies together: every `PipelineStage` except `complete` must be a stage
the store accepts. Trajectory rows are private traces that no grader reads, so
this did not invalidate the run in flight.

The general lesson is worth more than the fix: a fail-open write is the right
design and it hides its own failures, so the allowlist behind one needs a test
rather than a reviewer.

### Live verification

The deep case `rl-tc-001` was then run on its own against the real route rather
than re-spending the ceiling blind. First run, before defect 2 was fixed:
`complete`, 7 external calls, 19 sources, $0.057 — and `verifier_failed` with
zero claims, which is the pipeline failing safe exactly as designed but not the
pipeline working. The re-run after the fix is the evidence that matters and is
recorded below.

**Release gate: not yet passed, and the phase stays Target.** The corpus-wide
paid run has to be re-taken now that the harness can wait for a deep Turn; unit,
replay and grade-only success is explicitly not evidence for the quality gate.
The two dimensions that need the re-run are `material_claim` — frozen ground
truth applies to the *next* run, because a graded artifact records the corpus as
it stood when the run happened — and the soft `judge_axes` threshold, which
cannot be locked from a single trial.

Cost note for the re-run: one deep case cost **$0.057**. Twelve deep case-trials
plus 108 light ones sit comfortably inside the authorized $25; the binding
constraint is wall-clock, not money, because deep Turns are now waited out
properly and the harness runs one Turn at a time.

## Unresolved questions

1. **Routing.** Should `event_memo` and `source_conflict` route deep, and does
   widening the keyword set require a re-baseline before Phase 6 closes? The
   number that forces the question: 4 of 40 cases reach the pipeline today.
2. **`rl-mc-004`.** Is a case whose answer no public page states a material-claim
   case at all, or does it belong to the refusal family?
3. **Harness concurrency.** The runner serialises Turns because admission allows
   one active Turn per user. With deep Turns waited out properly, a 120-Turn run
   is a multi-hour job. Raising `--concurrency` lifts both ceilings together and
   is supported — but it changes what the run measures, so it is a golden-owner
   call rather than a speed knob to reach for silently.
4. **Threshold locking.** `judge_axes` needs a lower bound justified by the
   Phase 1 and Phase 6 multi-trial distributions.
5. **`agent_tool_call` index on `thread_id`** — left out deliberately in Phase 4
   and handed to Phase 6 to measure on a real table. The new tables ship with
   their own indexes; this one still has no measurement behind it.

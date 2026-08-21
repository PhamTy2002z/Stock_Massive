# The Recommendation Validator fails open, and eight conditions still fail closed

A Gate condition that cannot prove a block no longer ends the Turn. The block is
withheld and replaced by a backend-authored sentence naming the kind of evidence
that was missing, the Turn goes on to release everything else it proved, and the
model is nudged once to fix its own reference before any of that happens. **Eight**
conditions are exempt and still end the Turn: `figure_mismatch`,
`trading_day_mismatch`, `missing_trading_day`, `symbol_not_in_universe`, and the four
`*_mismatch` codes raised when a served field's unit, claim, source or sanctioned
reading disagrees with its Signal Registry declaration — `unit_mismatch`,
`claim_mismatch`, `source_mismatch`, `interpretation_mismatch`.

This amends ADR-0015 and ADR-0018. Neither is weakened where it decides
something. ADR-0015's invariant holds exactly: there is no field the model can
set to make a failure degradable, and none to make a block pass. ADR-0018's rule
holds exactly: *a figure that conflicts with the cited Tool Call Trace remains a
hard failure in every block.* What changes is the default for everything that is
**not** that.

## Why the default was wrong

Measured on `docs/eval/2026-08-17-1.4.0.json` and a seven-day ops snapshot:

| Measurement | Value |
| --- | --- |
| Conditions `grounding.py` raises | 28 |
| Conditions that ended a Turn | 20 |
| Turns ending `grounding_failed` | 58% (100 of 171) |
| Category B — the simplest valid questions | 0 of 30, against a bar of 90% |

The 20 were not 20 integrity failures. Most were a marker written wrong
(`malformed_reference`, `incomplete_citation`, `unknown_tool_call`) or evidence
that was asked for and was not there (`missing_value`, `refused_field`,
`unfinished_tool_call`). Neither class is a false statement. Both cost the reader
the entire answer.

The boundary that matters is **integrity**, not severity:

- **Integrity** — the block says something its own evidence does not. A figure
  contradicting the trace it cites, a figure attributed to the wrong session, a
  recommendation with no session at all, a block about a symbol no tool in this
  Turn served, and a figure narrated under a unit, claim, source or reading its
  Signal Registry declaration does not sanction. Each is a confident false
  statement, which is the single output the whole design exists to stop.
- **Availability and form** — the evidence is not there, or the marker naming it
  was written wrong. These are facts about this Turn's data and about the model's
  punctuation.

## Considered options

- **Extend the degradable list from 8 to 20 by hand.** Rejected. The list is a membership
  test, so a condition added to `grounding.py` next month blocks by default —
  which is how 16 accumulated in the first place. The failure mode repeats
  itself.
- **Keep the default and widen the rewrite budget.** Rejected. A model that
  cannot reference a figure after two nudges will not after four, and each nudge
  is a whole model call spent to arrive at the same sentence.
- **Let the model declare a block unprovable.** Rejected outright. ADR-0015
  refuses to give the model a field that changes its own enforcement, and a
  sentence the model writes is a sentence the model can be talked out of.

## The decision, stated as code

`GroundingFailure.degradable` is `code not in INTEGRITY_GATE_CODES`. Written as
an exclusion, so a condition written later degrades until somebody decides it is
an integrity failure — the direction that fails towards an answer rather than
towards a blank screen. `DEGRADED_REASON_FALLBACK` exists for the same reason: a
downgrade with no sentence would be a block with no text, which is the blank
screen this decision removes, arriving through a new door.

The exclusion has one cost, and it was paid before this document was first written:
four of the codes are built as `f"{key}_mismatch"` from a loop variable, so they
appear nowhere as literals, and the first draft of this boundary left all four out of
`INTEGRITY_GATE_CODES` — silently moving registry disagreement from block to degrade.
The guard test now reads the codes off the module's syntax tree instead of grepping
for string literals, because a grep is what missed them.

The nudge has a ceiling of `MAX_GATE_ATTEMPTS` validations — two, so exactly one
nudge. A count rather than the flag it replaced, because if per-Turn spend in
`llm_call_usage` climbs after this change, lowering it to 1 removes every nudge
without touching another line. Both a refused block and a downgraded one earn
the nudge: before this, downgrades raised, so they came through the refusal
branch; after it they do not raise at all, and without the second branch the
model would never again be asked to fix a misplaced marker.

## Consequences

- A recommendation carrying a price zone or a reference price is still withheld
  when its evidence is missing. `missing_price_zone`, `missing_reference_price`,
  `unregistered_price_zone` and `news_only_basis` downgrade — they always did —
  and downgrading means the recommendation block never reaches the screen. The
  Gate keeps its teeth exactly where the financial consequence is.
- The downgrade notice has two frames. Most conditions fire while a marker is
  being resolved, before anything knows whether the block was going to carry a
  recommendation, so the frame is chosen from the raw draft. Telling a reader who
  asked about today's market that no *price zone* was recommended would answer a
  question they did not ask.
- `GateOutcome` gains `downgrades`, the full ordered list. `failure_code` reports
  one condition, which was enough while eight could downgrade and only a
  recommendation could be the block; twenty can now, on any block, so an answer
  routinely has several. The key is additive and the Manifest schema version is
  unchanged: an old reader parses this Manifest as it always did.
- A nudge that makes the answer worse does not cost the reader the answer. A
  downgrade-only failure means the draft was releasable, and the nudge presses the
  model to attach references — a reference attached to the wrong call is
  `figure_mismatch`, which ends the Turn. The pre-nudge draft is kept and proven
  again instead, so a nudge can only improve what the reader gets.
- `recommendation` in the Manifest counts only downgrades of drafts that actually
  carried a recommendation. Read off the full code list it would report a market
  summary with one misplaced bracket as a blocked recommendation, and that
  dimension is what Phase 8's baseline reads.
- Nothing about the nudge reaches the durable transcript. It is appended to the
  in-flight message list and what is stored is blocks, widgets, traces and the
  activity trail — so a later Turn in the thread cannot read an instruction about
  an answer it can no longer see.
- **This decision is provisional on measurement.** The claim it rests on is that
  the 20 conditions are availability and form failures rather than the model
  stating something false. If the Eval Battery's blind-scored rubric finds wrong
  figures reaching readers through any of them, that condition belongs in
  `INTEGRITY_GATE_CODES` and the boundary is redrawn from evidence rather than
  from reasoning. Rollback is one constant.

## What this does not change

- No free text enters the System Prompt Contract. Enforcement stays in the
  validator, where ADR-0015 put it.
- The model has no field that affects the Gate, in either direction.
- The Signal Registry, the Evidence Manifest, the Risk Notice and the Tool Call
  Trace are untouched.
- A Turn the Gate emptied still releases `BLOCKED_TURN_NOTICE` rather than
  nothing.

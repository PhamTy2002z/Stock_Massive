# The Contract carries the no-fabrication rule, and the Validator keeps the four integrity codes

The System Prompt Contract states, in its own prose, that a figure comes from a
tool call or is not stated, that a figure which cannot be referenced ends a
sentence rather than an answer, and that naming the missing lookup is a complete
answer at that point. It also states that the independent lookups of a round are
emitted together.

This amends ADR-0015. That decision refuses to let the Contract be an
**enforcement** mechanism, and the refusal holds unchanged: nothing added here is
checked in the prompt, nothing here is a field the model can set, and every
invariant is still proven at the narrowest layer that can prove it. What changes
is narrower and worth stating plainly — **the Contract is now also allowed to
carry a behavioural rule whose violation the backend detects but cannot repair.**

## Why the prose has to say it

The Recommendation Validator is 1,302 lines and gates every block. It is a
detector: it can prove that a figure contradicts the trace it cites, and it can
withhold the block that carries it. What it cannot do is produce the answer the
reader wanted. ADR-0021 measured the consequence — 58% of Turns ended
`grounding_failed`, category B scored 0 of 30 — and inverted the default so a
failure withholds a block instead of a Turn.

That fixed what happens *after* the model writes an unreferenced figure. It does
nothing about the model writing one. The two decisions meet here: a validator
that fails open needs the prose to reduce how often it has to.

The evidence that prose reduces it comes from a survey of
`nousresearch/hermes-agent` (`plans/reports/hermes-synthesis-260821-0030.md`).
Nine lines in their cached system prefix address the same failure class, and the
comment beside them names the observation that produced them: a model *"pushed
through a PEP-668 wall, then returned fabricated listings."* Their block began as
guidance for one model family and lost that fence when eval traces showed others
failing identically — one of the listed failures being *"doing financial math in
prose"*, which is exactly the class `grounding.py` exists to catch.

The cost argument is theirs too, and it applies here without change: the block
ships in the cached prefix, so its tokens are paid once and amortised across
every Turn.

## The boundary

| Concern | Where it is decided |
| --- | --- |
| Whether a figure may be stated without a reference | the Contract's prose |
| Whether a block whose figure contradicts its trace is released | the Validator, `INTEGRITY_GATE_CODES` |
| Whether a recommendation has a session, a registered zone and a Universe symbol | the Validator |
| Whether the model complied with any of the above | never the model |

The four integrity codes ADR-0021 keeps fail-closed are untouched. Prose carries
the common case — a figure nobody asked the model to invent, a hedge where an
answer was possible — and the Validator keeps every case with a financial
consequence. If Phase 8's gate run shows unreferenced figures rising rather than
falling, the answer is not to weaken the prose but to widen the integrity group,
and this ADR is what records that the assumption was tested rather than assumed.

## Considered options

- **Leave enforcement wholly with the Validator.** Rejected on measurement. The
  Validator sees the sentence after it exists; by then the choice between an
  answer and a blank screen has already been made by the model.
- **Add a field the model sets to declare a figure unverifiable.** Rejected
  outright, for ADR-0015's own reason: a field the model can set to change its
  own enforcement is not enforcement. It also duplicates what the reference
  markers already say by their absence.
- **Put the rule in a per-Turn system message instead of the Contract.** Rejected.
  A message appended per Turn is outside the cacheable prefix, so its tokens are
  paid on every call, and it is invisible to `contract_hash` — a behavioural rule
  no version records is a rule no Eval Report can be attributed to.

## The batching block, and why it is here rather than in the loop

`loop.py` already dispatches a round's calls through `asyncio.gather`, so
independent calls have always executed concurrently. What was missing was any
sentence telling the model to emit them in the same turn. With `MAX_TOOL_ROUNDS`
fixed at 4 (`docs/specs/0003` §6, reaffirmed in this plan's gate G3), a round
spent on a lookup that could have travelled beside three others is a quarter of
the Turn's evidence budget, and the loop cannot recover it — by the time the
round is dispatched the model has already decided what it contains.

The block is bounded on the other side too: serialize where a later call
genuinely depends on an earlier one's result. A model that emits every lookup it
can imagine in round one spends the round on arguments it had to guess.

## Consequences

- `PROMPT_VERSION` moves to **1.8.0** and `contract_hash` changes with it, which
  voids the cached prefix and requires an Eval Report on any pull request
  carrying this change (ADR-0015, `CLAUDE.md`).
- The fixed section list of ADR-0015 gains two entries, *figures and the gaps in
  them* after the invariants and *batching lookups* after the tool-use policy.
  Trusted runtime context stays last, so the cacheable prefix keeps its shape.
- The Eval Fixture is **not** re-frozen. A fixture holds market data and a
  `fixture_version` derived from it; nothing in it depends on `prompt_version`,
  so the previous baseline stays comparable as a cross-version comparison and
  says so (`docs/agents/eval-battery.md`).
- Contract 1.6.0's rule against provenance caveats in prose stands and is
  load-bearing for the new block: naming a gap belongs **inside the sentence it
  affects**, never in a closing note about sources or reliability.

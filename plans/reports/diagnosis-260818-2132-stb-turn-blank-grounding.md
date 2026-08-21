# Diagnosis — "Phân tích giá STB hôm nay" returns an empty answer

Date: 2026-08-18 · Branch: `develop` · Turn: `6633e8f5-e861-49c9-b563-0b24966071bf` (log id 1442)

## Contract

- **Outcome:** an in-Universe price question answered with released prose, or — when the
  Gate legitimately blocks — a Turn that still tells the reader something. Never a Turn
  with zero blocks behind a search trail.
- **Constraints:** ADR-0015 stands — the Gate is a runtime block and `figure_mismatch`
  stays non-degradable; the model may not certify its own grounding. No relaxation of
  attribution strictness. Contract is at 1.6.0; a prompt-section change bumps it and
  drags the Eval gate along.
- **Non-goals:** model/route swap, Collector or trading-day policy, UI redesign.
- **Acceptance:** the same question on the same fixture releases blocks; a citation into
  a registered field can no longer carry another leaf's number under that field's unit;
  `indicator_pack` never dies from an optional Kelly scenario; ops `grounding_failed`
  rate on a real session drops off ~100%.

## What actually happened (evidence)

Turn state: `incomplete/grounding_failed`, `draft_content = {blocks: [], widgets: [],
tool_calls: 9, rounds_used: 1}` — no block ever reached the reader, which is exactly the
"search trail + withheld sentence, no answer" the user saw.

1. **Gate blocked the first block — figure pointed at the wrong leaf of the right field.**
   ```
   Turn 1442 blocked a content block: figure_mismatch: the block states '1,82' but
   registered_fields.price_zone.ordinary_range_pct.details.anchor_close in tool call
   'call-4b58091a-…' holds 74200.0
   ```
   `price_zone` (tool call 135) served
   `registered_fields["price_zone.ordinary_range_pct"] = {value: 1.8241…, unit: percent,
   details: {anchor_close: 74200.0, lower_price: 72858.7, upper_price: 75566.0,
   standard_error: 0.288, …}}`. The model narrated `value` (1,82) but wrote the marker path
   into `details.anchor_close`. `figure_mismatch` is non-degradable by design
   (`DEGRADABLE_GATE_CODES`), so `_release` raised on block #1 and the Turn ended with
   nothing released.

2. **`grounding._registered` lets a `details.*` leaf be cited as the registered figure.**
   `apps/api/src/agent/grounding.py:620` — `inside = remainder[len(name):]`, then
   `value = leaf`, while `unit`, `claim` and `interpretation` are taken from the *field*.
   A marker into `details.lower_price` would therefore have produced a citation reading
   "72858.73 percent — this symbol's ordinary daily range…". The mismatch check caught it
   this time; it does not catch the case where the narrated number equals the wrong leaf.

3. **Nothing in the trace tells the model the citable path.** `serialize_registered_field`
   (`apps/api/src/agent/tools/fields.py:55`) emits `value` next to a `details` map of other
   numbers, and the field key is itself dotted (`"price_zone.ordinary_range_pct"`). The
   Contract's only guidance is prose: *"A computed value lives under registered fields,
   then the field's own name, then value."* The model must reconstruct a dotted path over a
   dotted key by hand, with sibling numbers one level deeper.

4. **`indicator_pack` died on an optional scenario.** Call 138 arguments
   `{"symbol":"STB","edge_decimal":"0","variance_decimal_squared":"0"}` →
   `fractional_kelly_sizing` raised `variance must be a finite positive caller estimate`
   (`apps/api/src/stocks/signals/position_sizing.py:34`) → whole call `tool_error`, so RSI,
   MACD and Bollinger vocabulary were lost for the Turn. Two independent faults: `_kelly`
   raises instead of refusing, and the schema advertises two caller-owned numbers a model
   with no user input will fill with zeros. Also note the arguments arrived as *strings*,
   so the `exclusiveMinimum: 0` in the schema was never enforced.

5. **Not an isolated Turn.** Every recent Turn carrying figures ended `grounding_failed`
   (HPG ×3 on 2026-08-16, STB today); the only `complete` Turns are the two that asked for
   an explanation with no numbers at all. ADR-0016's own reading of a `grounding_failed`
   rate over 5% is "the Gate is blocking wrongly rather than the model fabricating".

Side observation, not a cause: runtime trading day is 2026-08-17 while the user asked
about "hôm nay" (2026-08-18). The answer would have been about the previous session.

## Options

**A — Make the trace self-describing, and narrow what a registered citation may point at.**
Emit the exact citable path per served field (e.g. `"ev": "registered_fields.<name>.value"`)
and reject a registered marker that resolves anywhere other than the field object or its
`value`. Assumption it leans on: the model copies a path it is handed rather than composing
one. Fails first if a model ignores the supplied path — but then it fails with
`unknown_field_path` rather than with a wrong-unit citation. Also closes fault (2) as a
correctness bug, independent of any model behaviour. Touches tool serialization + Gate →
Eval gate applies.

**B — Add one repair round when the Gate blocks a non-degradable block.**
`MAX_TOOL_ROUNDS` is 8 and this Turn used 1, so the budget exists. Feed back the stable
code and the legal paths (never the expected number) and let the model rewrite once.
Assumption: the failure is a marker slip, not a fabricated figure. Fails first when the
model "fixes" the prose by restating the number it was told about, which is Gate-shopping —
so the feedback must carry no values, and a second failure must still end the Turn.
Rescues every code, not just this one; costs one extra LLM call on a failing Turn.

**C — Prompt-only: teach the dotted-key path with an example.**
Cheapest, but ADR-0015 refuses to let the prompt enforce the invariant, and prose is what
already failed here. Bumps the contract and pulls the Eval gate for the weakest fix.

## Recommendation

**A, then B; C only as the wording that accompanies A.** A removes the class of error
(nothing to reconstruct, and a wrong-unit citation becomes unrepresentable); B stops the
remaining slips from producing a blank Turn. Both keep `figure_mismatch` non-degradable.
Fix (4) — `_kelly` refusing instead of raising, and arguments coerced/validated before
dispatch — is a separate, small, non-Gate change that can ship immediately.

## Open questions

- Should `details.*` remain citable at all for non-registered paths (Widget descriptors use
  `resolve_descriptor`, which is unaffected), or is `value`-only the invariant?
- Is a Turn whose every block is blocked allowed to release a backend-authored sentence
  ("chưa chứng minh được số liệu nào…"), or must it stay silent as today?

---

## Implemented (2026-08-18, branch `fix/grounding-citation-path`, commit d699345)

Decisions taken: A + B + the `indicator_pack` fix; `value`-only citation; a
backend sentence under an emptied Turn.

One deviation from option A as written. Emitting `"ev": "<path>"` on every served
field pushed `cross_sectional` to 4182 bytes against the catalog's 4096-byte cap,
and the path restated the key it sat beside. Same goal, cheaper mechanism: a
computed field is now referenced **by the key it is served under** — `[ev:CALL#
price_zone.ordinary_range_pct]` — with the long `registered_fields.<key>.value`
form still accepted. Nothing to compose, nothing repeated into the result.

- `grounding._registered` refuses a reference into a field's `details` as
  `uncitable_field_path` (non-degradable, like every mismatch class), and
  `_registered_name` is now shared by both spellings.
- `loop`: `_prove` / `_publish_blocks` split proof from publication; `_repair`
  spends one lookup round on a rewrite carrying the failed condition and no
  figure; `REPAIR_NOTE_TOKENS` prices it into the same budget and context ceiling
  the rounds-exhausted note uses.
- `grounding.BLOCKED_TURN_NOTICE` released only when no block passed.
- `computations._kelly` returns
  `{"status": "refused", "reason": "edge_and_variance_must_be_supplied_estimates"}`
  instead of raising, so the pack's registered fields survive; both schema
  descriptions now say to omit rather than estimate.
- Contract 1.7.0; ADR-0018 records all three Gate decisions.

Verification: `2412 passed, 1 skipped` (`pytest tests/`), including 7 new tests.
Replayed the real trace of tool call 135 from turn 1442 through the new Gate —
the marker the model actually wrote is now refused with the path it should have
used, and both accepted spellings release the block citing 1.8241698194005722
percent. No frontend change: the notice is an ordinary prose block.

**Not done, and blocking merge:** the Eval Report. This touches the Contract, the
Recommendation Validator, the agent loop and a tool schema, so `develop` will not
take it without a `make eval` gate run attached.

### Cost of the `value`-only decision

A recommendation can no longer narrate its zone in dong: `lower_price`,
`upper_price` and `anchor_close` are method details of a percent field and are
now uncitable. Zones read as "±1,82%", and a reference price must come from a
stored quote (`quote.close_price`), which is what Gate condition 2 has always
accepted. Registering the zone bounds as fields of their own is the way back to
prices, and it is not in this change.

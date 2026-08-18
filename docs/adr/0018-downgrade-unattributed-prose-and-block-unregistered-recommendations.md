# Unattributed prose is downgraded while unregistered recommendations remain blocked

The Recommendation Validator classifies evidence instead of treating every missing
reference as a reason to end the Turn. An ordinary prose block with an unattributed
figure is released with the literal in `unverified_figures`, which the backend keeps
and counts. A recommendation with the same defect remains blocked and ends
the Turn as `incomplete/grounding_failed`.

This decision amends ADR-0015 without weakening its narrow-enforcement rule. A figure
that conflicts with the cited Tool Call Trace remains a hard failure in every block.
Evidence from news, the open web, MCP, the Knowledge Store, and ad-hoc execution is
classified separately from registered evidence and cannot independently establish a
recommendation, reference price, or price zone.

## Considered options

The alternatives explain why the sanction differs by output type.

- Blocking every unattributed figure preserved a simple invariant but suppressed
  useful answers when the closed Tool Catalog could not reach the requested fact.
- Releasing every block with a warning would let an unsupported price or action reach
  a reader at the point where the product carries the greatest financial consequence.
- Rechecking figures with another model would add cost without creating evidence.

## Consequences

The downgrade becomes an observable product outcome rather than a hidden exception.

- `content.block` carries `unverified_figures`, and stored messages preserve the same
  additive field.
- `TurnOutcome` counts downgraded blocks, and the ops snapshot reports their rate over
  released blocks alongside the rarer `grounding_failed` Turn rate.
- Prompt contract 1.4 states that the downgrade is not permission to omit references;
  1.6 restates it without promising the reader a label.
- The client no longer renders the literals. Shown as a row of bare numbers under an
  answer, the record read as a defect in that answer rather than as provenance, and a
  reader cannot act on a literal stripped of the sentence it came from. The downgrade
  stays where it decides something: it still withholds a recommendation block and is
  still counted in the ops snapshot.
- Widgets are emitted only from content that survives validation.

## A blocked block earns one rewrite, and a blocked Turn still says something

Contract 1.7 amends how a hard failure is served, not what counts as one. A figure
conflicting with its citation is still a hard failure in every block.

- A computed field is referenced by the key it is served under, or by that key's
  `value`. The method details beside it are refused with `uncitable_field_path`.
  They were citable before, and the citation carried the *field's* unit and
  sanctioned reading whatever leaf it resolved: a percentage narrated beside an
  anchor price cited was one figure-agreement check away from reaching a reader as
  a price in percent.
- A non-degradable failure buys one rewrite, funded from the Turn's eight lookup
  rounds. The model is told the condition it broke and never the figure the trace
  holds — feedback carrying the value would let a block pass by restating the
  number it was told about. A second failure ends the Turn as before.
- A Turn the Gate emptied releases a backend-authored, figure-free sentence
  instead of nothing. Blocks that passed are still released, and the notice
  appears only when none did.

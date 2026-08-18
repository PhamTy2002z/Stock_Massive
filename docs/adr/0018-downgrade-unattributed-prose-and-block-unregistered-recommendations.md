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

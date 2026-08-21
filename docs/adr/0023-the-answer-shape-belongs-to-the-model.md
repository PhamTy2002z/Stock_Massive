# The answer's shape belongs to the model, three visuals may carry it, and a block names the pages behind it

The Contract no longer prescribes the sections of an answer. It keeps the rule
that facts, interpretation, reference actions and risks are never blended into
one sentence, and drops the reading of that rule as a list of four headings to
fill. It also says plainly that a message asking for nothing factual — a
greeting, a thank-you, a question about what the assistant can do — is answered
directly, with no lookup at all.

Three things move with it. The Widget ceiling goes from **one per answer to
three**, with a fourth only where the user asked for more in their own words.
The registry gains `quarterly_financials`, a table of the stored statement
figures across the reporting periods a lookup returned. And a released block now
carries `source_ids`: the public pages its own evidence stood on, so the chip
under a passage can name the page rather than only the kind of evidence.

This amends **ADR-0012**, which set the ceiling at one and listed four Widgets.
It follows `docs/specs/0004` D11, where the product owner closed both decisions.
Nothing in ADR-0015 is weakened: no rule below is checked in the prompt, no field
here is one the model can set, and every invariant is still proven at the layer
that can prove it.

## Why the fixed shape had to go

The mold the Contract described was written for one question — a full analysis of
one symbol — and every other question was answered in its shape. Measured on
`docs/eval/2026-08-17-1.4.0.json` and the sessions behind
`docs/specs/0004` §1: `answer_kinds.analysis` was **0**, category B scored **0 of
30**, and the two answers the owner flagged were a hedged sentence and a refusal
where the store held the figures. An answer to *how is the market today* arriving
as the same four labelled sections as an answer to *should I buy STB* is not a
consistent product, it is one product answering one question and approximating
every other.

The reference bar the owner captured (`docs/specs/0004` §3) is explicit that the
sections vary by question: a factual question gets a direct answer, bullets and
source chips; a market question gets sections, figures with dates and at least
one data block. What those sections *are* is a property of the question, and the
only party that has read the question when the answer is written is the model.

The risk of handing it over is real and named: an answer with no structure reads
like a blog post. The prose therefore says when a section earns its place rather
than replacing one fixed mold with another, and Phase 8's rubric blind-score is
what tests whether that was enough. If structure scores worse than 1.8.0's, the
answer is more guidance about *when*, not a return to headings.

## Why three visuals, and why a table

One visual per answer made the moat unreachable. `docs/specs/0004` D2 puts the
product's advantage in answers presented **as data** — tables, charts, widgets —
and a question about several things at once needs several shapes: a comparison, a
trend and the quarters behind them are three answers to three sub-questions, not
three drawings of one. Three is the ceiling the owner set; the anti-spam rule
that ADR-0012 wrote it for still exists, one number higher, and the fourth still
requires the user's own words (`user_requested_multiple`), which is the one
signal the backend owns.

`quarterly_financials` is the shape W1 made possible and nothing drew.
`get_financials` now serves up to twelve periods of stored statement figures, and
the only way to read them was prose — a table read out as sentences, which is the
form the owner's flagged question asked for and did not get. It is registered as
a **periods** binding rather than as a series: a period row is a stored provider
figure with no Signal Registry declaration, so it carries no unit and no
sanctioned interpretation and cannot go through the citation path a chart binding
uses.

Two properties of that binding are worth stating because getting either wrong is
silent:

- **The periods are named, never counted.** The descriptor pins the exact period
  ends the answer was written about. Asking for "the last four" a year later is
  how a historical record turns into a fresh query wearing an old date.
- **The read boundary is the Turn's session, not the newest period shown.** A
  filing for June is written to the store in August, so replaying the slice
  against June would drop the row the table exists to show. The descriptor
  carries both dates for that reason.

It is also the one carve-out in the Stock 360 refusal list. `get_financials`'s
periods are listed there because the deep-dive screen draws the valuation
*history* from them; a table of filed figures is not that line, and refusing it
would send a reader who asked for the numbers to a screen that shows them as a
chart.

## Why the lanes are not a router

The plan behind this change describes three lanes — a conversational reply, a
lookup, and a recommendation. **None of them is a field, a classifier, or a
branch in the loop.** What decides whether the Recommendation Gate applies is
what it has always been: the shape of the block the model wrote. A block naming a
price zone or telling a reader to buy, sell, wait or avoid is a recommendation
block and is checked as one, whatever the question looked like.

That is the whole defence against the failure this change could have introduced —
a light lane as a back door around the Gate. There is no lane for a block to be
in. The Contract now says so in prose as well, which reduces how often the
Validator has to withhold a block, exactly as ADR-0022 argued for the
no-fabrication rule.

The conversational case needed prose for a different reason: the tool-use policy
said to call a tool before answering anything factual, and said nothing about a
message that asks for nothing factual. A greeting answered through a lookup
spends a quarter of the Turn's evidence budget (`MAX_TOOL_ROUNDS` is 4) on a
question nobody asked.

## The boundary

| Concern | Where it is decided |
| --- | --- |
| Which sections an answer has | the model, per question |
| Whether facts, interpretation, actions and risks are blended | the Contract's prose |
| Whether a block is a recommendation | the Validator, from the block's own markers |
| How many visuals an answer may carry | `WIDGET_CEILING`, server-side, before persistence |
| Whether the user asked for more visuals | `user_requested_multiple`, from the user's own words |
| Which columns a quarterly table shows | `QUARTERLY_COLUMNS`, server-side |
| Which pages a block rests on | `progress.block_source_ids`, from citations the model already wrote |

`source_ids` is display metadata and **never** a gate. It is derived by joining
two facts the system already holds — which call each claim cited, and which pages
each call returned — so it cannot invent a third. The single check is membership
in the Turn's own source set, and a page that fails it is dropped from the chips
while the block is released exactly as it was validated. A reference to one
result of a search names that result's page rather than every page the search
returned: twelve pages listed under a sentence citing one of them would tell a
reader that eleven sources agreed with something they were never asked about.

## Considered options

- **A `[src:...]` marker the model writes.** Rejected. Markers are positional:
  `_match_figures` attributes a figure to the next marker after it, so a source
  marker between a figure and its evidence reference would leave the figure
  unattributed. Paying for that with a display detail is the wrong trade, and the
  citations the model already writes carry the same information.
- **Keeping the ceiling at one and adding the table as a fifth name.** Rejected
  on the owner's decision (D11) and on the measurement behind it: the table is
  most useful in an answer that also compares or trends something, which is
  exactly the answer a ceiling of one forbids.
- **A lane classifier before the lookup.** Rejected. It is a second model call
  whose accuracy cannot be measured before Phase 8, it would put a routing
  decision where ADR-0015 refuses to put enforcement, and the shape of the block
  already answers the only question that has a consequence.
- **Letting the model choose the table's columns.** Rejected. ADR-0012 gives the
  server every presentation default, and a margin the model asked for is a
  division this system did not compute — an untraceable figure by ADR-0010's
  standard.

## Consequences

- `PROMPT_VERSION` moves to **1.9.0** and `contract_hash` changes with it, which
  voids the cached prefix and owes an Eval Report (ADR-0015, `CLAUDE.md`). The
  section list of ADR-0015 is **unchanged** — no section arrived or left. What
  this decision moved is the prose inside *tool-use policy*, *output protocol*
  and *visual evidence*; the cacheable prefix keeps its shape.
- `tool_catalog_version` does **not** move. The table binds to `get_financials`,
  which is unchanged; the selection rides the output contract, as ADR-0012's
  first argument requires. The Eval Fixture is therefore **not** re-frozen and
  the previous baseline stays comparable as a cross-version comparison.
- The Eval Report for this change is owed to the same gate run as Contract
  1.8.0's, which the plan for this work rolls into its final phase. This is
  recorded rather than left to be discovered, exactly as `docs/specs/0004` did
  for the W1 + W4 merge.
- `content.block` gains one additive key. A message stored before this build
  carries no `source_ids`, and the renderer reads its absence as "no pages",
  never as an error.
- The browser keeps a hard bound of four Widgets per message. It sits *above* the
  server's default rather than at it, because dropping a Widget in the renderer
  is indistinguishable from the server never having produced one.

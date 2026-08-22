# Memory travels by tool, and untrusted prose is labelled rather than blocked

Two capabilities land together because they are the same argument seen from two
sides: **what the model is allowed to carry between sessions, and what it is
allowed to believe about text it did not fetch from the store.**

Memory arrives as tools — a widened `remember_fact` / `recall_facts` and a new
`session_search` — and **never** as prompt content. Untrusted prose gains a
fifth defence, a pure pattern library that **names** what it recognised and
labels the evidence block; it does not withhold the block, does not end the
Turn, and cannot raise.

The Contract moves to **1.10.0** to teach both. It gains no enforcement: every
rule below is checked where it can be proven, which is what `ADR-0015` requires
and what `ADR-0022` re-stated when the Contract took on the no-fabrication rule.

## Why memory could not be a prompt snapshot

The obvious design is the one the reference implementation uses: read the user's
notes at Turn start, freeze them into the volatile tail of the system prompt,
and rewrite the file between sessions. It is cheap, it needs no tool, and the
model never has to decide to look.

It is closed to us, and closed by a mechanism rather than by preference.
`prompt/contract.py::_assert_no_formatting_hole` refuses any section body
containing a brace, and `render()` accepts five typed values and nothing else.
The docstring states the property that buys: *there is no string field, so there
is no hole a figure, a Watchlist entry, a tool result or user prose could be
poured into.*

That is a stronger anti-injection guarantee than the design it rules out — which
is visible in the reference implementation itself, where a snapshot of arbitrary
file content entering the prompt forces a scan of every context file it loads.
We would be adding the hole and then paying for the scan that the hole makes
necessary. So memory goes where every other piece of retrieved evidence already
goes: through the Tool Catalog, into the transcript, wrapped as a claim, subject
to the Recommendation Gate.

The cost is real and is accepted: the model must **decide** to recall, and a
model that does not decide to recall will ask the reader to repeat themselves.
That is what the Contract paragraph is for, and it is guidance rather than a
guarantee — the same standing the batching rule has.

## What the memory tools now carry

`agent_knowledge` gains three columns and loosens one constraint.

| Column | Why it exists |
| --- | --- |
| `kind` | `preference`, `conclusion`, `observation` — a stated risk appetite and a figure read off a page are recalled for different reasons and filtered apart |
| `origin` | `user_stated`, `system_derived`, `external_source` — the difference between *the reader told me* and *a page said* |
| `expires_at` | a horizon a reader stated last quarter is not a fact about this quarter; an expired row is not recalled |

`source_url` and `source_name` become nullable, because a preference the reader
stated in their own words has no URL and inventing one would be a lie about
provenance. The pairing is held by a **CHECK constraint** rather than by the
tool: `origin = 'external_source'` still requires a URL, and the rule is in the
database because the tool is not the only thing that will ever write this table.

Nothing here promotes evidence. A recalled row is still `external_claim`
(`grounding.py::EvidenceSource`), so it still cannot on its own support a
verdict or a price zone. Persistence is not verification, and a fact does not
become truer for having been written down.

`session_search` reads the transcript the reader and the assistant already
wrote. One tool, **four modes inferred from the arguments** and no `mode`
parameter: a query searches every thread of that reader, a query with a thread
searches inside it, a thread with an anchor returns the window around that
`seq`, a thread alone returns its recent messages, and no arguments at all
return the recent threads. It calls **no model**. A summarising search is a
second place for the system to be confidently wrong and a second place to spend
money, and the search that returns the rows is the one that can be checked.

Vietnamese is why the index is spelled out rather than defaulted. Postgres's
default text-search configuration silently fails to match accented text, so
`agent_message` gains a generated `tsvector` over
`to_tsvector('simple', immutable_unaccent(content ->> 'text'))` — the same
immutable wrapper `agent_knowledge` already uses. *Silently* is the operative
word: the wrong configuration does not error, it returns nothing, which is why
an accented-query test is an acceptance condition and not a nicety.

Authorisation is a join, not a column. `AgentMessage` deliberately carries no
`user_id`; a thread belongs to one user, so every mode filters through
`agent_thread`. A thread that is not the caller's answers `no_matching_messages`
— the same refusal as a thread that exists and matched nothing, so the refusal
does not disclose which.

## Why the injection scan does not block

Four defences already stand between a hostile page and the model: the
`external_claim` label on the result, the cleared-publisher list in the news
lane, capped visible-text extraction in `_html.py`, and the Contract's statement
that retrieved text is data. `threat_patterns.py` is the fifth and the weakest
by construction: it reads text and returns names for what it recognised —
`invisible_characters`, `instruction_override`, `credential_probe`,
`impersonated_system` — and decides nothing.

Two properties make it safe to call on the retrieval path. It is **pure**: the
standard library only, no session, no settings, no application import. And it
**fails open without exception**: every path is wrapped and any error returns an
empty tuple. A scan that raised would convert a page the reader asked for into a
dead Turn, which is strictly worse than an unlabelled page, because the content
was already going to be treated as data.

Blocking was considered and rejected on evidence rather than on taste. Blocking
untrusted content is the same move that `ADR-0021` reversed after measuring what
it cost: sixteen of twenty-four gate codes ended a Turn, 58% of Turns died
`grounding_failed`, and category B scored 0 of 30. *Bỏ qua khuyến nghị trước đó*
is an ordinary sentence in a Vietnamese market wire. A scanner that withheld on
it would blank the screen for a correct answer, and blanking the screen is the
failure this whole line of work exists to end.

So a false positive costs one JSON key and one log line. That is the trade, and
`ops.py` tallies the labels by name precisely so the cost is measured rather
than assumed: a label firing on ordinary traffic is a reason to tighten a
pattern, and the tally is where that becomes visible. The count is read off
`agent_tool_call.result`, which the product already writes — no new table, per
`ADR-0016`.

## Consequences

**`tool_catalog_version` moves.** `session_search` is a new schema in the
versioned surface, so the pin no longer matches and the Eval Fixture is refused
until it is re-frozen. That was already true before this change for an unrelated
reason, and the re-freeze is the first step of the gate run that follows.

**`PROMPT_VERSION` moves to 1.10.0** and `contract_hash` with it, so the
cacheable prefix is rebuilt once. Prose only — no section arrived or left, and
the section list is unchanged. Three things are taught: that the reader has a
past worth looking up before asking them to repeat it; that saving a sourced
fact and saving one the reader stated are different acts with different
provenance; and that a block the system marked as carrying an instruction is
still evidence to read, because the mark is a warning and not a verdict.

**A recalled figure is still not a citable figure.** The Contract says to look
it up again before quoting it. Nothing enforces that beyond the Recommendation
Validator already refusing a figure whose reference is not a trace from this
Turn — which is the enforcement, and it was already there.

**The migration is additive and reversible.** Three nullable-or-defaulted
columns, one loosened NOT NULL, one CHECK, one generated column and its GIN
index. `downgrade()` restores all of it.

## What this does not change

No prompt hole is opened: `_assert_no_formatting_hole` still runs at import and
`render()` still accepts five typed values. No evidence is promoted: recalled
rows and transcript excerpts remain `external_claim`. No content is withheld by
the scan, in any code path. No new observability table exists. And the SSRF
defences in `web.py` — pinned DNS resolution, `is_global` on every resolved
address, re-validation of every redirect hop — are untouched; they were already
stronger than the implementation this work learned from.

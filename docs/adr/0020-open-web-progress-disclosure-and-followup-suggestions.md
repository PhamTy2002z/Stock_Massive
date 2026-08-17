# The open-web lane discloses its queries and its sources, and a Turn ends with follow-up suggestions

ADR-0013 gives `turn.activity` a closed vocabulary of four generic phases and forbids
it from carrying a tool name, symbol, argument, raw result, prompt, or reasoning.
`docs/specs/0002` §6 and §9 say the same thing from the product side: the Tool Call
Trace is the audit surface, and the activity line is not a verbose tool history.

This decision **narrows that rule to the lanes it was written for** and adds one
event-carried detail payload for the lane it was not.

## What changes

`turn.activity` may now carry a `detail` object alongside its `phase`, and the phase
vocabulary gains a fifth member, `found_sources`. Only the **open-web lane** —
`web_search` and `fetch_url` — may populate `detail`:

```json
{"phase": "searching",      "detail": {"queries": ["chủ tịch Masan Group"]}}
{"phase": "found_sources",  "detail": {"result_count": 15, "sources": [
  {"title": "Ban lãnh đạo của Công ty CP Tập đoàn Masan",
   "url": "https://masangroup.com/...", "domain": "masangroup.com",
   "snippet": "Hiện nay, Ban Điều hành gồm có năm thành viên…",
   "published_at": "2025-11-20", "retrieved_at": "2026-06-19T08:00:00+00:00"}]}}
```

A source may also carry `snippet`, `published_at` and `retrieved_at` — the
excerpt and timestamps the search result itself returned, capped server-side.
All three are optional and omitted rather than sent empty: they exist so the
source drawer can say what a page claims and when, and they disclose nothing the
search engine did not already show.

Every other tool keeps the behaviour ADR-0013 specified: a bare phase, no detail, no
way to learn the catalog by watching a Turn run. The store lane, the analysis lane and
the widget lane are unchanged, and a Turn that never touches the open web publishes
exactly the events it published before.

`search_news` is external too and is still excluded. Its argument is a Universe symbol
rather than a sentence the system composed, and its items carry an allowlisted source
name with no URL — there is nothing to link to and no query worth showing, so it keeps
the bare phase.

The progress trail is also **persisted**, in two places for two readers: on the
checkpoint, so a reconnecting browser rebuilds the trail it was watching, and on the
canonical assistant message as `search_progress`, so reopening a Thread months later
shows what the answer was built from.

## Why the open web is different from the tool catalog

The argument in ADR-0013 is about *disclosure of the system*: a reader who watches
enough activity lines learns which tools exist, what they are called and what they
take, and the catalog is not something a product surface should teach. That argument
holds for every tool that reads the store, because the tool name, the field id and the
arguments are internal vocabulary the reader did not supply and cannot act on.

It does not hold for an open-web search. The query is a sentence the system composed
*about the user's own question*, and the results are public pages with public URLs.
Hiding them protects nothing: a reader can run the same search. And withholding them
costs something real — an answer built on `masangroup.com` and an answer built on an
anonymous aggregator deserve different amounts of trust, and a reader given only
"Searching…" cannot tell which one they are holding.

`domain` is carried beside `url` rather than parsed in the browser, so the label under
a source is the host the backend actually fetched rather than one a renderer derived
from a string it was handed.

## Why the phase enum grew instead of the detail carrying the meaning

`found_sources` could have been `searching` with a `sources` key, leaving four phases.
It is a fifth phase because the two are different moments with different truth: one is
"a search is running, here is what was asked", the other is "the search returned, here
is what came back". A renderer distinguishing them by key presence would be reading
absence as meaning, and a subscriber that arrived between the two would have no way to
know which it was looking at.

The enum stays closed. Five members, validated on the way out, and a phase the backend
cannot name is a phase it cannot publish.

## Follow-up suggestions are generated, and they are batch work

A completed Turn now ends with up to five follow-up questions, stored on the message as
`suggestions` and rendered under the answer.

They are produced by **one additional provider call on the batch workload** — the cheap
model, `Workload.BATCH` under ADR-0014, charged to the same owner as the Turn that
produced them. Batch rather than session because nothing waits on them interactively:
they are assembled into the terminal transaction, so they arrive with the canonical
message rather than racing it.

The call is best-effort by construction. A budget refusal, a timeout, a malformed
response or a route error yields no suggestions and changes nothing else about the
Turn: the answer is the product, and a Turn that succeeded must never be reported as
having failed because a garnish did not render.

Suggestions are **not** generated for a refusal, for an `incomplete` Turn, or for a
Turn with no released blocks. Offering "what else would you like to know" under an
answer that could not be given reads as the system not having noticed.

## What this does not change

- The Tool Call Trace remains the audit surface, and it remains the only place a tool
  name, an argument or a raw result appears.
- No store-lane tool name, field id or symbol reaches `turn.activity`.
- The Evidence Manifest, the Risk Notice, the Recommendation Gate and the grounding
  rules are untouched. `search_progress` and `suggestions` are additive keys on the
  message; a message written before this decision renders without either.
- The envelope version is unchanged: `detail` is an additive key inside an existing
  event's `data`, and a client that ignores it reads exactly what it read before.

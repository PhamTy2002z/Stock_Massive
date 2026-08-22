# The agent is a general assistant on a Hermes-shaped harness, and it reads none of our data

The interactive agent no longer reads this project's data. Every tool that served
the store, the Signal Registry, or a market provider is gone, and with them the
mechanism that decided what an answer was allowed to say: the Recommendation
Validator, the Evidence Manifest, the typed Widget protocol, the five-phase
activity trail, and the labelled analysis blocks. What replaces them is the tool
architecture of [nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent):
a registry, composable toolsets, one place that builds the schema list, a
dispatcher with a parallel/sequential segment planner, a four-rung guardrail
ladder, and a three-tier output budget that previews instead of refusing.

The provider data — vnstock, FiinQuant — keeps flowing. It serves the price
board and the deterministic Analysis lane, which are untouched. The change is
that the agent is no longer a reader of it.

## Status

Accepted 2026-08-22, by the product owner, as a product decision rather than as
a conclusion drawn from measurement. This record says so plainly because the
measurement pointed the other way and should not be quietly lost.

`plans/reports/brainstorm-260820-2323-hermes-harness-swap.md` recommended
against this swap on evidence: the only numbers that existed (category B 0/30,
58% of Turns ending `grounding_failed`) were measured on contract 1.4.0, *before*
the three landed fixes aimed at exactly those numbers — the `price_zone` tool,
the availability-vs-integrity split of ADR-0021, and ~15 grounding
false-positive repairs that carried the contract to 1.7.1. No gate run has been
made since. Two cheaper suspects were also unexcluded: `LLM_MODEL_SESSION` set
to the cheapest batch model, and 36% of a seven-day Turn sample dying on the
free-tier route rather than in agent logic.

That objection was put to the product owner and reaffirmed against four times.
The decision is theirs to make, and this ADR implements it in full. What the
report establishes is not that the swap is wrong, but that the swap is being
made without knowing what the patched harness scored — so nothing here should
later be read as *evidence* that the old harness could not answer.

## What this replaces

Superseded outright, because the mechanism each one decides no longer exists:

| ADR | What it decided |
| --- | --- |
| 0009 | The agent tool catalog contract |
| 0011 | No sandboxed code execution in v1 |
| 0012 | The typed Widget registry as the visualization protocol |
| 0015 | The System Prompt Contract as the versioned behavioural core |
| 0018 | Downgrade unattributed prose, block unregistered recommendations |
| 0019 | The networkless container executor for derived evidence |
| 0020 | Open-web progress disclosure and follow-up suggestions |
| 0021 | Fail-open grounding |
| 0022 | The contract carries the no-fabrication rule |
| 0023 | The answer shape belongs to the model |
| 0024 | A round has a context ceiling and a repetition ladder |

Amended in their agent-facing half only; the rest stands:

| ADR | What survives |
| --- | --- |
| 0007 | Two layers stay, but only the deterministic one reads data now |
| 0008 | The loop stays hand-rolled over `src/core/llm`; its contents change |
| 0013 | SSE with backend-owned turns stays as transport; the payload is new |
| 0016 | The Eval Battery's *method* stays; its subject was the old harness |

Untouched, and load-bearing for the price board: 0001–0006, 0010, 0017.

## The new tool boundary

Five tools, in two toolsets, and none of them can reach our data:

| Tool | Toolset | Reads |
| --- | --- | --- |
| `web_search` | `web` | Tavily |
| `fetch_url` | `web` | An arbitrary URL, under the SSRF rules the old tool already enforced |
| `session_search` | `memory` | `agent_message.tsv` — the user's own transcript |
| `remember_fact` | `memory` | `agent_knowledge`, write |
| `recall_facts` | `memory` | `agent_knowledge`, read |

The memory pair and `session_search` survive the deletion because what they hold
is the user's own conversation, not market data. `agent_message` already carried
a generated `tsv` column with the diacritic handling a Vietnamese reader needs,
which is the session-search capability Hermes builds itself — so this is a tool
over a store we already had, not a new one.

## What the harness borrows, and what it refuses

Ported, because each answers a failure this project has or would have had:

- **Three-tier output budget.** The old catalog raised `ToolResultTooLarge` at a
  hard 4KB, which gave the model no way forward. A budget that previews and
  leaves a pointer degrades instead of refusing, and the per-turn aggregate
  catches what no single result triggers.
- **The guardrail ladder.** `warn` appends guidance to a tool result, `block`
  stops the next identical failing call before it costs a round, `halt` ends the
  turn. Three intervention points, because they are three different moments.
- **The untrusted-result envelope.** Web content is wrapped and the delimiter is
  defanged inside the content, at the message-building layer rather than in the
  prompt — a prompt cannot enforce it and an attacker can forge a closing tag.
- **A segment planner** rather than an unconditional `asyncio.gather`, so an
  unknown tool in a batch serialises only itself.

Refused, and the reasons are the same ones the tool report gave:

- Hermes' seven terminal backends, its file and shell tools, and Programmatic
  Tool Calling. This is not a coding agent.
- Per-backend schema sanitisers (Gemini, Moonshot, llama.cpp). One
  OpenAI-compatible route, strict schemas — sanitising is a fix for a problem
  that does not exist here.
- Tool Search progressive disclosure. Five tools do not need deferral.
- `clarify` and `todo`. A turn is request/response, and there is no interactive
  channel mid-turn to ask a question down.

## Consequences, including the unpleasant ones

**The eval gate loses its subject.** `CLAUDE.md` requires an Eval Report for any
change touching the System Prompt Contract, tool schemas, the Signal Registry,
the agent loop, or the Recommendation Validator. This change touches all five
and deletes three of them, and the Eval Battery scored precisely the properties
that are gone — groundedness, citation integrity, recommendation validity. The
gate cannot be satisfied as written and must not be quietly dropped: a new bar
for a general assistant has to be defined before this reaches `develop`.

**Nothing checks a figure any more.** The old design's one claim was that a
number in an answer was either traced to a registered field or withheld. A
general assistant on web search has no such property. Answers about Vietnamese
equities will now be as good as the open web is, and there is no backend check
standing between a plausible number and the reader. That is the trade this
decision makes, stated once, here.

**Seven tables outlive their harness.** `agent_thread`, `agent_message`,
`agent_tool_call`, `agent_turn` stay — the last two because
`src/core/llm/admission.py` counts active turns across *all* lanes and
`src/stocks/jobs.py` prunes tool-call rows on a schedule. `agent_knowledge`
stays for the memory tools. Their columns describing the old contract become
dead weight to clean up later, not now.

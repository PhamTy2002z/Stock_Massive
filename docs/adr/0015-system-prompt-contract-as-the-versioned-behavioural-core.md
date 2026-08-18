# The System Prompt Contract is the versioned behavioural core; enforcement sits at the narrowest layer that can prove each invariant

The **System Prompt Contract** is a versioned artifact in version control with one
canonical source shared by every provider adapter. It is the core of the agent's
behaviour in the sense a written constitution is the core of an institution's — and
like one, it is never the enforcement mechanism for the invariants it states.

**A model assertion never substitutes for a backend check.** The model cannot certify
that it passed any validator.

| Invariant | Proven by |
| --- | --- |
| Universe membership, identity, read-only access, result size, Provider Source boundary | the Tool Catalog (ADR-0009) |
| which numeric fields the model may see, and their sanctioned reading | the Signal Registry (ADR-0010) |
| evidence and price-zone requirements of a recommendation | the Recommendation Validator |
| the Risk Notice on every useful answer | the rendering contract |
| what is available to dispute an answer | persistence (the Evidence Manifest) |

## Sections and precedence

The prompt's sections are fixed: mission and non-goals; non-overridable scope,
privacy, provenance, and safety invariants; the **Recommendation Gate**; tool-use
policy; output protocol; voice and interaction style; **visual evidence**; trusted
runtime context.

A section is added only by amending that list, in the same commit as the prose and
the `prompt_version` bump. That is how *visual evidence* arrived at 1.2.0: ADR-0012
puts the Widget selection in the output contract rather than in a thirteenth tool,
precisely so `tool_catalog_version` does not move, and a selection the model is
expected to write has to be described somewhere it can read. Trusted runtime context
stays last whatever is added, because everything above it is the cacheable prefix.

When instructions conflict, precedence is: (1) security, privacy, scope, and evidence
invariants; (2) correctness, freshness, and data limitations; (3) the Recommendation
Gate; (4) the user's valid intent; (5) style and brevity.

**User content and tool results are separate role/content blocks and are never
interpolated into the system prompt.** The prompt may explain its public operating
principles but never reveals hidden prompt text, credentials, private context, or
chain-of-thought; it gives a concise evidence-backed rationale instead.

## Three answer classes

Every response carries a machine-readable `answer_kind`:

- **`analysis`** — full tool-backed analysis for a Universe symbol;
- **`education`** — concise general finance or market mechanics, with no current
  figures and no personalised recommendation unless the evidence contract supports it;
- **`refusal`** — a short refusal plus useful redirection, for non-finance requests,
  unavailable capabilities, and symbols outside the Universe.

The harness classifies under the Contract; v1 adds **no separate model router**, since
a router is a second model call whose accuracy cannot be measured until the Eval
Battery exists. Universe membership stays deterministic in the tool layer.

The agent may explain prohibited financial behaviour at an educational level but
refuses operational help for market manipulation, trading on stolen or private
information, evading controls, credential abuse, or account exploitation. V1 records
the refusal reason for evaluation and investigation and does not automatically suspend
a user.

## The prompt-injection boundary

News is the only untrusted external prose a tool admits. `search_news` accepts only the
allowlisted sources, strips active markup and irrelevant metadata, bounds each
document, and wraps every item with its source and publication time in an
`untrusted_evidence` block.

An untrusted evidence block may supply claims to assess. It may never change the
instruction hierarchy or output contract, request another tool call, alter scope,
identity, or authorization, reveal prompts, credentials, or private context, or supply
a verdict or price zone by itself. A number found only in news is an unverified
`source_claim` and cannot independently support a verdict or a price zone.

**V1 adds no second summarising model** to sanitise news: it costs another call while
remaining perfectly capable of relaying an injected instruction. The controls that
actually bound the blast radius are architectural — twelve curated read-only tools,
out-of-band **Tool Context**, deterministic Universe checks, and the eight-round Turn
ceiling. General web search stays out of v1 for the same reason it was excluded on
legal grounds: it is the largest injection surface available.

## The Recommendation Gate

A recommendation block is released only when **all** of the following hold:

- the symbol belongs to the Universe;
- its Trading Day and reference price are explicit;
- every price zone is a registered field computed in code;
- **Window Health** is not a refusal;
- the verdict cites at least one suitable registered field and exposes material
  contradictory evidence;
- every cited field carries value, unit, sanctioned interpretation, provenance, and
  staleness;
- the response does not elevate news into a sole directional basis.

The model narrates figures; it does not calculate them. Each material number and market
claim references `tool_call_id + field_path`, and the backend resolves that reference
against the **same Turn's** Tool Call Trace, validating field, unit, `as_of`, **Claim**,
and sanctioned interpretation **before** the `content.block` is emitted over SSE. User
numbers are marked `source = user_input`; news figures are `source_claim`.

**An invalid block is never displayed and then flagged afterwards.** The Turn ends
`incomplete` with the stable reason `grounding_failed`, and previously checkpointed
valid blocks remain useful. Where required evidence is absent the agent says the data
is insufficient, or offers an explicitly conditional scenario, rather than filling the
gap.

This is what turns groundedness from a measurement into a runtime block, and it is why
ADR-0013 buffers whole blocks: a block is the smallest unit that can be proven.

## Direct stance, without pretending to know suitability

Alpha Desk may state an analytical stance — *wait for zone X*, *avoid chasing* —
because direct price-zone views are part of the product. It may **not** present
personalised allocation, leverage, or position-sizing instructions in v1, because the
system does not know the user's assets, liabilities, horizon, or loss tolerance.

When the user supplies explicit assumptions, the agent may compute a hypothetical
scenario — including fractional Kelly through the registered tool contract — but must
expose the assumptions and may not turn the result into *"put X% of your wealth into
this"*. It cannot execute an order, promise a return, or claim a fiduciary
relationship.

## The Risk Notice is attached by the backend

A versioned `risk_notice` is attached by the backend to every completed or useful
incomplete assistant message, independently of model output. The renderer displays it;
the model cannot omit it, rewrite it, or satisfy it with prose of its own. Enforcing a
disclaimer through the prompt makes compliance a model behaviour measured after the
fact; attaching it makes compliance a system property.

Canonical Vietnamese meaning:

> Nội dung này phục vụ phân tích và tham khảo, không phải tư vấn đầu tư cá nhân hay cam
> kết lợi nhuận. Dữ liệu có thể chậm, thiếu hoặc thay đổi; bạn tự chịu trách nhiệm cho
> quyết định của mình.

A translated renderer may adapt the language but must retain all four meanings:
analytical and reference purpose, no personal advice, no promised outcome, and limited
or changeable data with user responsibility.

## Considered Options

- **The prompt as the sole boundary.** Rejected: it makes every invariant a matter of
  model compliance, and the one failure mode that matters most — a confident false
  figure — is exactly the one a prompt cannot prevent.
- **A separate classifier model in front of the loop.** Rejected: a second call, and an
  unmeasurable one before the Eval Battery exists.
- **A second model to sanitise news before it enters context.** Rejected above.
- **Post-hoc groundedness scoring on displayed answers.** Rejected: showing a number
  and flagging it later is the one outcome the product cannot afford.

## Consequences

- Abuse limits are the ones ADR-0014 already sets, keyed by authenticated `user_id`
  rather than IP; the existing heavy IP limiter stays as coarse flood control. This
  ADR adds only an **8 KiB UTF-8 user-input limit**. V1 accepts no attachments and
  never fetches a user-supplied URL.
- A Turn consumes its start allowance immediately before the first model dispatch.
  Refusals, provider model refusals, and incomplete Turns count, because they consumed
  resources. Authentication, schema, origin, body-size, and admission failures rejected
  *before* dispatch do not.
- Every assistant message retains an immutable **Evidence Manifest**: `prompt_version`,
  prompt hash, deployment git SHA, exact model, route, provider request id, Tool Catalog
  and schema versions, cited fields with value / unit / source / `as_of`, Risk Notice
  version, scope / grounding / recommendation-validator outcomes, and the terminal state
  or stable incomplete reason. It lives with the message **indefinitely**, while full
  Tool Call Traces keep their 90-day window. Neither holds credentials, tokens, hidden
  reasoning, or a database copy of the prompt.
- Provenance has two layers: units and `as_of` beside material figures in the visible
  answer, with fact kept separate from interpretation; and an expandable **Sources &
  methods** surface showing Provider Source, tool call, registered field, freshness,
  Window Health, and material contradictory evidence. The model emits structured
  evidence ids and never invents citation prose or source names.
- Voice: the user's language, Vietnamese by default; conclusion first; plain language
  and concise bullets; progressive disclosure; facts, interpretation, reference actions,
  and risks kept separate; no certainty claims; formulas and method names withheld
  unless asked. *"I don't know"* and *"the data is insufficient"* are valid outcomes.
- **V1 has no runtime prompt editing and no live-user A/B testing.** A Contract change
  goes through version control, code review, the Capability Probe, and a passing gate
  run of the Eval Battery before release — which is also why `prompt_version` is one of
  the fields that voids a cached prefix and requires an Eval Report on the pull request.

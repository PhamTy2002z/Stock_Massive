# The Tool Catalog is twelve semantic tools, store-only, returning registered fields under 4KB

The agent reaches `apps/api` through a **Tool Catalog** of exactly twelve semantic
tools in a new `src/agent/tools/` package: six data tools, five computation
clusters, and one identity-scoped tool. They are not thin wrappers over the
existing REST endpoints — an endpoint is shaped for a React page, a tool is shaped
so a model picks it correctly.

| Kind | Tools |
| --- | --- |
| Data (6) | `get_analysis`, `get_price_series`, `get_financials`, `get_company_profile`, `search_news`, `screen_universe` |
| Computation (5) | `risk_metrics`, `market_behavior`, `cross_sectional`, `foreign_flow`, `indicator_pack` |
| Identity-scoped (1) | `get_watchlist()` |

The five computation clusters carry all fourteen methods of the ranked shortlist
in `docs/research/quant-methods-eod-vn.md`. Clustering is a selection-accuracy
decision: a model chooses correctly among twelve names far more reliably than
among twenty-six, and each cluster returns an object whose fields belong together
the way an analyst reads them.

## The four contract rules

**Store-only, with one named exception.** Numeric tools read Postgres and Redis
only. This preserves the boundary of ADR-0001 for the reason that ADR gave it: a
user hammering the agent must never be able to spend the Collector's vnstock
quota. `search_news` is the sole cache-aside exception, because news value decays
intraday, and it is bounded by its own lane in the quota arbiter (ADR-0014) rather
than by good intentions. That exception also narrows the *user requests never call a
Provider Source* sentence of ADR-0004 and ADR-0005; ADR-0001's amendment names all
three rather than overriding them silently.

**Return discipline: ≤ ~4KB of JSON, and never a raw series.** A series comes back
as summary statistics plus a decimated sample, alongside a **Data Reference**
(`data_ref`: symbol, range, field) that the visualization layer resolves
(ADR-0012). The model gets digested figures, widgets get references, nobody gets
raw bars. This is not only a context-window economy — it is the mechanism behind
*all numbers are computed in code and the model only narrates them*.

**Registered fields only.** The tool layer serializes exclusively fields present in
the **Signal Registry** (ADR-0010). A computation that fails the statistical bar
may exist as an internal diagnostic; it simply is not registered, so there is no
route from it to the model and nothing needs to be forbidden.

**The Universe boundary is enforced in the tool layer, not the prompt.** A
non-Universe symbol yields a **Structured Refusal** —
`{reason: "not_in_universe", suggestions: [...]}` — carrying up to three
same-ICB-industry Universe symbols ordered by descending ADTV. That is a pure
query with no model involved, which is what makes it dependable.

## Identity is out of band

User identity is never a model-visible parameter. The harness injects a
**Tool Context** carrying `user_id`; `get_watchlist()` is the only tool that reads
it. The model cannot ask for another user's Watchlist because there is nowhere in
the schema to put the question. An `owner`-style parameter would make the refusal
a prompt rule, and prompt rules are not authorization.

## Considered Options

- **Thin wrappers over the ~25 existing REST endpoints.** Rejected. Endpoint
  names and parameter shapes were designed for a page's data needs; several are
  frozen paths that still call a provider in-request (`docs/serving-path.md`), so
  wrapping them would smuggle provider calls into the agent path.
- **Many narrow tools — one per computation, ~26 total.** Rejected on selection
  accuracy. It also fragments the hazard reporting: **Window Health** belongs to
  the window, and one cluster returning it once is honest where twenty-six copies
  invite drift.
- **A single fat `query(...)` tool with a mode parameter.** Rejected: the mode
  parameter becomes an untyped dispatch surface, and per-field schema metadata
  (`unit`, `interpretation`, `null_fpr`) has nowhere to live.
- **Adopting an external quant-tool library.** Assessed and rejected: the
  candidate normalised z-scores against a full-sample median/MAD (lookahead), fired
  on 8–15% of pure iid Gaussian noise, and handed an LLM a kurtosis z-score —
  whose sign is meaningless — as a directional figure, which was then narrated
  backwards. Two ideas were kept and appear in ADR-0010: Garman-Klass variance
  with a robust median/MAD screen, and windows expressed as durations with the
  unit in the parameter name.

## Consequences

- The Collector must be extended to persist what the tools read. The money-flow
  adapters exist but are unwired, technical indicators are not stored, and news is
  not persisted at all (`docs/research/data-coverage-audit.md`). Store-only is a
  constraint on ingestion, not a licence to read live.
- Every catalog-wide rule from §10 of the quant-methods research is adopted:
  trailing windows only with unit-named parameters, explicit `insufficient_history`
  refusal, a unit and sign convention on every field, limit-lock days counted and
  excluded and reported, band regime dated per bar, and sub-3-session horizons
  flagged as not round-trip actionable under T+2.
- `data_ref` is also the authenticated data-in seam for ADR-0019's networkless
  executor. The API resolves it before passing explicit JSON across the queue.
- A stable core tool is a catalog change, not an implementation detail: it changes
  `tool_catalog_version`, which invalidates the cacheable prompt prefix and, under
  ADR-0016, requires a gate run. Discovered MCP schemas are the named exception:
  they move `mcp_servers_version` instead so a server outage cannot rewrite the
  frozen core contract.
- A model reaching for a tool that does not exist is recorded as
  `status = 'unknown_tool'` in `agent_tool_call`. It remains a free capability-gap
  signal even though ADR-0019 superseded the fixed twelve-tool ceiling.

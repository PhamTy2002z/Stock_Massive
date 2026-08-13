# MindSearch for Alpha Desk search and analysis

**BLUF:** Treat MindSearch as reference architecture, not as a runtime
dependency or deployable service for Alpha Desk v1. Its planner/searcher split,
atomic-query decomposition, bounded page selection, parallel fan-out, and
citation-ID remapping are useful patterns. Its implementation conflicts with
Alpha Desk's locked product boundary and safety model: it performs unrestricted
general-web search, executes model-generated Python with `exec`, fetches
arbitrary URLs without an SSRF boundary, passes raw page text into an agent,
relies on prompt-generated citations, keeps session state in memory, and has no
integration with Alpha Desk's Turn persistence, evidence validators, or spend
admission. Revisit a hardened, deterministic version only after general-web
research becomes an explicit product capability.

This review covers MindSearch commit
[`7952c5f`](https://github.com/InternLM/MindSearch/commit/7952c5f8a956fe6a44228a6a7d528a35340e7c87),
the repository's `main` head on August 13, 2026, and its pinned Lagent
`0.5.0rc2` source at commit
[`4db8ea8`](https://github.com/InternLM/lagent/commit/4db8ea842491226b16a13e9221143e02d8d3bb84).
It also checks the five Alpha Desk decisions that define the relevant boundary:
[per-symbol news](https://github.com/PhamTy2002z/Stock_Massive/issues/17#issuecomment-5239809838),
[orchestration and budgets](https://github.com/PhamTy2002z/Stock_Massive/issues/25#issuecomment-5269770932),
[the Tool Catalog](https://github.com/PhamTy2002z/Stock_Massive/issues/31#issuecomment-5267500711),
[the agent loop](https://github.com/PhamTy2002z/Stock_Massive/issues/32#issuecomment-5268065545),
and
[guardrails](https://github.com/PhamTy2002z/Stock_Massive/issues/36#issuecomment-5270312927).

## What MindSearch provides

MindSearch is an AI search application built around a multi-agent retrieval
pattern. It is not a stock-analysis engine, financial data source, or validated
evidence layer. Its paper names two roles: a `WebPlanner` constructs a search
DAG, and one `WebSearcher` handles each atomic sub-question through hierarchical
web retrieval. The paper reports more than 300 candidate pages processed in
under three minutes and an average of 3.2 search queries on its evaluated tasks,
but it also states that citation quality was not evaluated comprehensively
([architecture](https://arxiv.org/html/2407.20183v2#S2),
[query-count analysis](https://arxiv.org/html/2407.20183v2#A3.SS2), and
[limitations](https://arxiv.org/html/2407.20183v2#S5)).

The current implementation turns that design into the following execution path:

1. The planner LLM emits Python that constructs a `WebSearchGraph`, adds atomic
   search nodes and dependencies, and later adds a response node. The outer
   agent permits up to ten planner turns
   ([agent loop](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/mindsearch_agent.py#L55-L124)).
2. Each graph node starts a separate searcher agent. The synchronous path uses a
   ten-worker thread pool. The asynchronous path schedules work across up to 32
   daemon threads, each running an event loop
   ([graph concurrency](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/graph.py#L71-L190),
   [event-loop pool](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/graph.py#L222-L245)).
3. A searcher can generate several similar queries, merge results by URL, select
   pages, read page text, and summarize the sub-question. This is the paper's
   coarse-to-fine retrieval stage
   ([WebSearcher design](https://arxiv.org/html/2407.20183v2#S2.SS2)).
4. The planner receives searcher summaries rather than every raw page. It can
   add more graph nodes, then asks the shared LLM for a final synthesis after it
   adds the response node
   ([reference aggregation](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/mindsearch_agent.py#L35-L52),
   [final synthesis](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/mindsearch_agent.py#L102-L124)).
5. A FastAPI `/solve` route emits intermediate graph and answer states over SSE.
   The repository also includes React, Gradio, and Streamlit clients
   ([backend and frontend instructions](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/README.md#L29-L142)).

This structure solves a different context problem from Alpha Desk. MindSearch
distributes a broad web corpus across agents, while Alpha Desk deliberately
gives one analyst a small, typed catalog over bounded store data and permits
only one allowlisted news exception.

## Search backends and runtime requirements

MindSearch delegates searching and page retrieval to Lagent. The application
selects one backend at process start and configures every searcher with
`topk=6`. Except for Tencent, it passes the same `WEB_SEARCH_API_KEY` setting to
the selected backend
([agent initialization](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/__init__.py#L25-L81)).

The advertised backends have materially different operational and contractual
properties:

- `DuckDuckGoSearch` uses the pinned third-party `duckduckgo_search==5.3.1b1`
  client. That client calls DuckDuckGo web endpoints directly and documents rate
  limit exceptions; it is not a contracted search API
  ([MindSearch dependency](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/requirements.txt#L1),
  [pinned client behavior](https://github.com/deedy5/duckduckgo_search/blob/36b971a6a17639d2cc3a10a1017c9a68a1edeced/README.md#duckduckgo_search),
  [direct endpoint use](https://github.com/deedy5/duckduckgo_search/blob/36b971a6a17639d2cc3a10a1017c9a68a1edeced/duckduckgo_search/duckduckgo_search_async.py#L133-L175)).
- `BingSearch` calls the Bing Web Search v7 endpoint in the pinned Lagent code
  ([implementation](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L128-L217)).
  Microsoft retired Bing Search APIs on August 11, 2025, so this advertised
  option is no longer viable
  ([Microsoft retirement notice](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)).
- `BraveSearch` calls Brave's web or news endpoint with a subscription token
  ([implementation](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L219-L354)).
  Brave currently advertises $5 per 1,000 Search requests, 50 queries per
  second, and separate plans for storage rights
  ([official plans](https://brave.com/search/api/)).
- `GoogleSearch` is not Google's first-party search API. It calls Serper's
  Google Search proxy at `google.serper.dev`
  ([implementation](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L356-L503)).
- `TencentSearch` signs calls to Tencent's `SearchCommon` API with a secret ID
  and key
  ([implementation](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L506-L693)).

The hosted-model path supports Lagent adapters for GPT-style endpoints, Qwen,
and SiliconFlow. The local path starts InternLM2.5-7B through LMDeploy. The
project's Docker guide says only `internlm_silicon` was known to work for cloud
deployment and only `internlm_server` had passed local testing; it recommends at
least 12 GB of GPU memory and estimates more than 30 GB for the local backend
and model
([model configurations](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/models.py#L12-L95),
[deployment constraints](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/docker/README.md#L38-L92)).

The install is application-oriented and not reproducible enough for a production
library dependency. MindSearch has one tagged release, `v0.1.0`, published on
November 5, 2024
([release](https://github.com/InternLM/MindSearch/releases/tag/v0.1.0)). Its
requirements pin Lagent, Gradio, Pydantic, Transformers, and DuckDuckGo Search
but leave most direct dependencies unbounded, and the repository has no Python
lockfile or root package metadata
([requirements](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/requirements.txt)).
The Docker launcher also installs Lagent `0.5.0rc1`, while the main requirements
specify `0.5.0rc2`, creating two documented environments with different
framework versions
([launcher image](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/docker/msdl/templates/backend/cloud_llm.dockerfile#L12-L25)).

## License and external-content rights

MindSearch's code is usable under Apache License 2.0, including its copyright
and patent grants, subject to the license's notice, attribution,
modification-marking, and redistribution conditions
([MindSearch license](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/LICENSE#L1-L128)).
Its pinned Lagent framework is also Apache 2.0
([Lagent license](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/LICENSE)).
Those licenses cover code, not search-result or publisher content rights.

A production adoption would still require three independent reviews:

- Review every resolved direct and transitive dependency because MindSearch does
  not ship a lockfile or a dependency-license bill of materials. The pinned
  DuckDuckGo client itself is MIT licensed
  ([client metadata](https://github.com/deedy5/duckduckgo_search/blob/36b971a6a17639d2cc3a10a1017c9a68a1edeced/pyproject.toml#L1-L31)).
- Contract with the selected search backend under terms that cover commercial
  search, display, caching, and any persisted evidence. For example, Brave says
  storing API results requires a plan that explicitly grants storage rights
  ([official provider guidance](https://brave.com/search/api/)).
- Review each fetched publisher's terms separately. A search-provider right to
  return a URL or snippet does not automatically grant a right to fetch, retain,
  republish, or feed the full page into a model.

This is stricter than the narrow v1 news decision, which already evaluated
specific Vietnamese sources and selected VCI news through `vnstock`, with CafeF
as a later fallback. MindSearch does not improve that legal posture merely by
placing a search API in front of arbitrary publishers.

## Provenance, streaming, concurrency, and cost

MindSearch provides visible source links and useful retrieval progress, but its
contracts are weaker than Alpha Desk's evidence and budget contracts. Its
behavior is suitable for exploratory web answers, not for releasing price-zone
guidance.

### Citation and provenance behavior

The search result schema carries a URL, title, and snippet. Selected pages add
raw text. It does not carry Provider Source, publication time, observation time,
content hash, claim span, or evidence classification
([result shape](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L20-L48),
[page selection](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L787-L817)).

The searcher prompt tells the model to write `[[int]]` citations. MindSearch
then uses regular expressions to renumber those IDs and associate them with
URLs. Its only completeness check is an `assert` inside a `try` block that logs
an invalid reference and continues; there is no claim-to-source verifier
([citation prompt](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/mindsearch_prompt.py#L1-L34),
[citation remapping](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/mindsearch_agent.py#L14-L52)).
This is link attribution generated by the model, not Alpha Desk's validated
`tool_call_id + field_path` evidence.

### Streaming and lifecycle behavior

The API streams incremental model and graph state over SSE. Both route variants
stop emitting when the request disconnects, then remove the session from the
agent's in-memory `memory_map`. The asynchronous route breaks out of agent
iteration. The synchronous adapter stops consuming the stream but waits for its
wrapped generator in `finally`, so disconnect is not a reliable computation
cancellation mechanism
([SSE lifecycle](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/app.py#L81-L168)).
Neither path persists a detached, resumable Turn. There is no durable job
record, replay cursor, idempotent resume, Tool Call Trace, or terminal state
that survives process loss.

That lifecycle is the inverse of Alpha Desk's locked model: an admitted Turn
belongs to the backend, persists independently of an SSE connection, survives a
reload or closed tab, and stops only on an explicit cancellation. An isolated
MindSearch service would therefore require a new persistence and reconciliation
layer even before its search results could enter a Turn.

### Concurrency and cost behavior

MindSearch has execution ceilings but no spend admission. The planner has a
ten-turn default, each searcher runs its own multi-turn Lagent loop, search
nodes fan out concurrently, and each searcher can issue multiple search queries
and page fetches. The code starts up to 32 event-loop threads for asynchronous
searchers and also defines a ten-worker executor per graph. It does not reserve
model or search cost, record token usage, enforce a per-user allowance, or
integrate retries into a monetary ceiling.

Those properties conflict with Alpha Desk's one-active-Turn-per-user rule, three
active Turns system-wide, eight tool-call rounds, `$0.50` maximum per Turn, and
atomic `llm_call_usage` reservation. The paper's 3.2-query average is an
evaluation observation, not a hard upper bound, and it excludes the
deployment-specific LLM price and page-fetch risk.

## Security and prompt-injection properties

The upstream implementation has two source-level boundaries that rule out direct
production use. Isolation around the service would reduce infrastructure impact,
but it would not make its output safe evidence for an investment recommendation.

### Model-generated Python execution

The planner is prompted to emit Python code for graph operations.
`ExecutionAction` extracts the model-generated code block and calls
`exec(command, global_dict, local_dict)` with the module globals. There is no
AST allowlist, restricted builtins set, subprocess sandbox, or capability
boundary
([prompted code interface](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/mindsearch_prompt.py#L101-L277),
[execution](https://github.com/InternLM/MindSearch/blob/7952c5f8a956fe6a44228a6a7d528a35340e7c87/mindsearch/agent/graph.py#L248-L267)).

This is arbitrary code execution by design, not merely a conventional function
call. Because web-derived summaries can influence later planner turns, a
successful prompt injection could become part of the planner's code-generation
context. The Alpha Desk harness deliberately exposes twelve read-only typed
tools and must not replace that boundary with `exec`.

### Arbitrary URL fetching and untrusted page text

Lagent's `ContentFetcher` sends `requests.get(url)` or `session.get(url)`,
strips HTML tags with Beautiful Soup, and returns the remaining text. `select`
inserts up to 8,192 characters into the searcher context. `open_url` accepts a
model-supplied URL directly and returns the full fetched text
([fetcher](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L696-L727),
[selection and open URL](https://github.com/InternLM/lagent/blob/4db8ea842491226b16a13e9221143e02d8d3bb84/lagent/actions/web_browser.py#L787-L826)).

The inspected source has no scheme allowlist, DNS or resolved-IP check, private
or link-local address denial, redirect revalidation, response MIME allowlist, or
total response-byte limit before parsing. This creates SSRF exposure when the
service can reach internal addresses. HTML stripping removes active markup but
does not remove instruction-like prose, so it is not a prompt-injection defense.
MindSearch also does not wrap page text in Alpha Desk's `untrusted_evidence`
contract or prevent news text from influencing a verdict.

## Fit with the locked Alpha Desk architecture

MindSearch is tightly coupled to its own application stack and conflicts with
most of the decisions already made for Alpha Desk. The useful overlap is
conceptual, not at the library or API-contract level.

- **Hand-rolled `LLMClient` loop:** MindSearch replaces the loop with Lagent
  agents, InternLM-specific parsers, shared class-level searcher configuration,
  in-memory memory, and its own stream status protocol. Adopting it would reopen
  the decision to keep provider translation and tool-call assertions visible in
  Alpha Desk.
- **Twelve-tool catalog:** MindSearch exposes a web browser and an unrestricted
  Python graph interpreter. It neither consumes nor preserves the twelve
  semantic stock tools, their structured refusals, `ToolContext`, or the
  Universe boundary.
- **Results at or below about 4 KB:** MindSearch inserts as many as 8,192
  characters per selected page before JSON and prompt overhead, can select
  several pages per searcher, and combines many searcher summaries. It has no
  catalog-wide result budget or `data_ref` contract.
- **Store-only numeric tools:** MindSearch's value is live external retrieval.
  It cannot improve numeric analysis without violating the rule that numeric
  tools read Postgres or Redis only. Web numbers would remain unverified
  `source_claim` values and could not satisfy the Recommendation Gate.
- **Allowlisted per-symbol news:** MindSearch searches the general web and
  fetches publisher pages. It does not constrain results to VCI and CafeF,
  enforce a ticker match, share the `vnstock` quota arbiter, or preserve the
  six-hour news cache.
- **System Prompt Contract:** MindSearch has detailed planner, searcher, and
  final synthesis prompts, but they do not implement Alpha Desk's mission
  hierarchy, scope classes, Recommendation Gate, Risk Notice, privacy boundary,
  or trusted runtime context. Importing its prompts would create a competing
  constitution.
- **Runtime evidence validation:** MindSearch asks the model for citation
  markers and maps them to URLs. Alpha Desk requires the backend to validate
  every material numeric field and recommendation block before emission. The two
  mechanisms are not substitutes.
- **No general web in v1:** This is the decisive product conflict. MindSearch's
  core capability is precisely the capability v1 excludes. Adding it behind the
  name `search_news` would silently redraw the product scope and legal boundary.
- **Backend-owned Turns and budgets:** MindSearch ties generation to `/solve`
  SSE state and does not persist usage or reserve cost. Alpha Desk owns the Turn
  after admission and accounts for every provider call, including unknown usage.

MindSearch is therefore best classified as a tightly coupled reference
application. Its `mindsearch` modules can technically be imported from a
checkout, but the project does not present a stable library package or a narrow
search API whose contracts match Alpha Desk.

## Adoption options

Four adoption paths are possible, but only one fits the current destination.

### Full dependency

Do not add MindSearch or Lagent to `apps/api`. This option brings a second agent
harness, several heavy UI and model dependencies, unrestricted network access,
arbitrary code execution, in-memory lifecycle semantics, and a prompt-based
citation system. It also expands v1 into general-web search without a product
decision.

### Isolated service or tool

Do not deploy the upstream service unmodified. A network-isolated experiment
could be useful for offline evaluation, but its answer must be treated as
untrusted prose and must never directly support a verdict or price zone.
Production use would still require replacing `exec`, hardening all outbound
fetches, persisting jobs, adding cost admission, and translating output into
Alpha Desk evidence objects. At that point, the integration is a new
implementation, not simple isolation of MindSearch.

### Pattern extraction

Keep MindSearch as prior art and extract only four ideas into Alpha Desk-owned
code if a future research capability needs them:

- Decompose a complex qualitative question into atomic search questions with an
  explicit dependency graph.
- Execute independent nodes concurrently under a small, configured semaphore.
- Use coarse-to-fine retrieval: rank snippets first, then fetch only a bounded
  set of approved pages.
- Preserve machine-owned source IDs through node summaries and final synthesis.

Implement the graph as validated data, not model-generated Python. Compile a
strict plan schema into deterministic Python calls, use the existing
`LLMClient`, persist each node under the owning Turn, and validate citations
against captured source objects before rendering.

### Reject or defer

Defer runtime adoption for v1. Continue with the already-approved `search_news`
tool over VCI, with CafeF considered only under its earlier source decision.
That tool is enough for recent per-symbol context and preserves the deliberate
exclusion of general-web answers.

## Recommendation and revisit conditions

The concrete recommendation is **pattern extraction later; reject all MindSearch
runtime options now**. Record no new dependency and expose no new tool in v1.
The MindSearch patterns become relevant only for a distinct post-v1 capability
such as deep qualitative research into regulation, management, supply chains, or
sector events.

Revisit the decision only when all of these conditions hold:

1. Approve general-web research as an explicit destination and version the Tool
   Catalog and System Prompt Contract for that new scope.
2. Select a commercial search contract that covers Vietnamese retrieval quality,
   display, caching, and evidence retention. Benchmark it against the approved
   Vietnamese sources rather than assuming global-web ranking is sufficient.
3. Replace planner `exec` with a strict graph schema and deterministic executor.
4. Put page fetching behind an egress proxy or hardened fetcher that validates
   schemes, DNS results, resolved IPs, every redirect, MIME type, compressed and
   decompressed size, and timeouts. Prefer a domain allowlist where the use case
   permits one.
5. Persist backend-owned research nodes and source objects under the Turn so SSE
   disconnects do not cancel or erase work.
6. Enforce query, page, concurrency, token, and monetary ceilings through the
   existing admission and `llm_call_usage` mechanisms.
7. Convert every fetched page into bounded `untrusted_evidence` with source,
   publication time where available, observation time, content hash, and stable
   evidence ID. Keep external numbers as `source_claim` and prohibit them from
   independently satisfying the Recommendation Gate.
8. Pass guardrail evaluation for prompt injection, SSRF, citation precision and
   recall, stale or contradictory sources, cancellation, cost exhaustion, and
   Vietnamese finance retrieval before enabling live users.

Meeting these conditions would preserve MindSearch's strongest idea, parallel
graph-shaped research, without importing the parts that conflict with Alpha
Desk's core contract.

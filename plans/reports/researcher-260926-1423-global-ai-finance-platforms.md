# Global AI Financial-Research Platforms — Benchmark for a Vietnamese-Equity Research Agent

Date: 2026-09-26 (Asia/Saigon). Scope: benchmark Stock_Massive (web chat, tools:
`web_search`, `fetch_url`, session memory, `get_market_data` via vnstock, deep-research
pipeline with claim ledger/citations, golden eval harness) against leading AI
financial-research platforms worldwide.

## How to read this report

Tool access was heavily rate-limited or blocked this session: most vendor marketing
sites (Perplexity, Bloomberg, Morningstar, S&P/Kensho, LSEG, Robinhood, VNDirect,
OpenAI's finance-specific pages, moomoo) returned HTTP 403/404/429 or a CAPTCHA wall to
every fetch attempt, and no working web-search tool was available (`mcp
ccs-websearch` was not present in this runtime's tool set; DuckDuckGo/Bing HTML search
via WebFetch returned CAPTCHA pages or irrelevant results). Per the task's instruction
to "skip any you cannot verify, say so," each platform section below is marked:

- **[VERIFIED]** — fetched directly from the vendor's own site in this session, source
  URL given.
- **[UNVERIFIED — not reachable this session]** — could not be fetched (403/404/429/DNS
  failure); description below is general background knowledge, not sourced in this
  session, and should not be treated as current fact without a follow-up check.

Only three independent references were reachable per verified claim in a couple of
cases (single vendor page); where that is true it is flagged rather than presented as
cross-checked. Treat the credibility bar in this report as lower than the researcher
role's default and re-verify before using anything here for a specific product or
pricing decision.

---

## Platform findings

### Hebbia Matrix — [VERIFIED] (hebbia.com)

- **Features**: spreadsheet-like "Matrix" UI — custom columns tracking financial/
  valuation/leverage/governance metrics over aggregated documents; drag-and-drop file
  ingestion; deal-workflow templates (divestiture, activist defense, ECM/DCM); shared
  team workspaces.
- **Data moat**: 40+ feeds — SEC/UK Companies House/EU/AU-NZ filings; FactSet, S&P
  Capital IQ, PitchBook, Preqin, ICE, Fitch; document stores (SharePoint, OneDrive,
  Box, Dropbox, AWS, IntraLinks); expert-call transcripts (Third Bridge, Guidepoint);
  CRM/data-warehouse connectors (Salesforce, Snowflake, Databricks, DealCloud).
- **Trust**: every cell shows a source/basis footnote (e.g., "LTM Jun 30 2026;
  FactSet std.").
- **Customers/pricing**: institutional (banks, PE/VC, corp dev, legal); no public
  pricing, enterprise sales motion.
- **Fit signal**: this is a document-aggregation-and-tabulation product for deal teams,
  not a retail chat app — architecture pattern (structured columns over heterogeneous
  document corpus with per-cell citation) is the most transferable idea, not the
  product itself.

### Rogo — [VERIFIED] (rogo.com)

- **Features**: AI agents doing end-to-end workflow execution (not just Q&A) —
  Excel models, investment memos, diligence packs, slide decks; integrates into
  existing bank/PE tooling (SharePoint, CRM).
- **Customers**: investment banks (Nomura, Truist Securities, Baird named), 350+
  institutions, 50k+ bankers/investors — explicitly not targeting retail.
- **Trust/compliance**: SOC2, ISO 27001, GDPR, CCPA, EU AI Act compliance claimed;
  citation methodology not disclosed on the page.
- **Pricing**: not disclosed, demo-gated.

### AlphaSense — [VERIFIED] (alpha-sense.com)

- **Features**: Generative Search + "Deep Research" reports with "sentence-level
  citations and no hallucinations" (vendor's own claim, not independently verified);
  "SuperAnalyst" always-on agent; Tegus-branded expert-call booking built into the
  product; PowerPoint/Excel add-ins that preserve citations in exported artifacts.
- **Data moat**: 500M+ documents — broker research, SEC filings, earnings-call
  transcripts, Tegus expert-interview transcripts, market/fundamental data, private
  client content via connectors.
- **Trust**: "decision-grade AI" framing; citations attached to every generated claim,
  traceable into source documents.
- **Pricing**: enterprise, contact-sales only.
- Note: this is the correct AlphaSense (`alpha-sense.com`); `alphasense.com` is an
  unrelated sensor manufacturer — a mix-up risk worth flagging for anyone else
  researching this space.

### Koyfin — [VERIFIED] (koyfin.com/features)

- **Features**: charting with technical/fundamental overlays; equity screener (5,900+
  filters); watchlists; company snapshots with analyst estimates; alerts (price,
  valuation, technicals, news) across watchlists/portfolios; model portfolios and
  client/household management for advisors; branded client reporting.
- **AI features**: none found on the fetched features page — Koyfin's public
  positioning as of this fetch is a data/terminal product, not an AI-chat product.
  (Koyfin has announced AI copilot features in industry coverage previously, but that
  was not present on this page and could not be independently confirmed this session.)
- **Data coverage**: global equities, analyst estimates, financials, US ETFs/funds.
- **Pricing**: tiered (free/plus/pro/business per public knowledge), not shown on the
  fetched page.

### Anthropic Claude for Financial Services — [VERIFIED] (anthropic.com/news, launched 2025-07-15)

- **Features**: unifies data from multiple providers into one interface; Claude 4
  models benchmarked at 83% accuracy on complex Excel tasks (vendor claim); Claude
  Code/Enterprise enables trading-system modernization, compliance automation, Monte
  Carlo simulation; source-linked claims with multi-source verification to reduce
  errors; use cases include due diligence, competitive benchmarking, portfolio
  analysis, modeling with audit trails, investment memos, pitch decks.
- **Data partners**: Box, Daloopa, Databricks, FactSet, Morningstar, PitchBook, S&P
  Global, Snowflake, Palantir; implementation partners Accenture, Deloitte, KPMG, PwC,
  Slalom, TribeAI, Turing.
- **Trust**: "by default, your data is not used for training"; positioned for
  regulated-institution data-protection requirements.
- **Distribution**: AWS Marketplace (GCP Marketplace planned at launch).
- **Relevance**: this is the closest analog to Stock_Massive's own approach — a
  general-purpose model wired to third-party financial-data connectors plus an audit
  trail — but it is a platform/connector play for enterprises building their own
  workflows, not a finished retail research app.

### Google Gemini Deep Research — [VERIFIED] (blog.google, feature launched Dec 2024)

- **Features**: agentic multi-step research — plans research steps (user-approved),
  iteratively searches and refines based on what it finds, compiles a cited, linked
  report the user can export.
- **Finance-specific features**: none found in the fetched primary source; this is a
  general-purpose Gemini Advanced capability, not a finance product. (Google Finance's
  own AI features, if any as of 2026, could not be verified this session.)
- **Architecture pattern**: plan → iterative search/read → synthesize with citations —
  structurally similar to Stock_Massive's own deep-research pipeline (plan → research →
  counterevidence → verifier), which suggests the plan-then-iterate-then-cite loop is
  now an industry-standard shape for "deep research" agents, independently arrived at
  by Google, OpenAI (per public knowledge of its Deep Research launch), and this
  project.

### Public.com Alpha — [VERIFIED] (public.com/alpha)

- **Features**: "experimental AI research tool" for exploring financial information
  inside a retail brokerage app.
- **Trust/compliance boundary — directly relevant to Stock_Massive**: explicit
  disclaimer language: "Alpha is an experimental AI research tool... It may produce
  inaccurate or inappropriate responses and is not investment research or a
  recommendation," output is "as is," and users must "independently verify any
  information before making decisions." This is a clean, minimal precedent for a
  retail-facing "not advice" boundary paired with an AI chat feature — comparable to
  Stock_Massive's own research-vs-advice legal boundary.
- **Data**: market data from third-party sources "believed to be reliable," quotes via
  Xignite.
- **Pricing**: not disclosed on the fetched page.

### Vietnamese platforms

- **Vietstock — [VERIFIED]** (vietstock.vn): ships a named chatbot, "Chứng Sỹ"
  ("Securities Officer"), positioned for Q&A / ideas / "advice" about securities (the
  site's own language uses "tư vấn"/advice framing, notably looser than Public.com's
  explicit non-advice disclaimer). Covers HOSE/HNX/UPCOM; also offers screening,
  technical analysis, financial-statement retrieval, industry data visualization. No
  citation/traceability mechanism was visible on the fetched page.
- **Simplize — [VERIFIED]** (simplize.vn): stock analysis/valuation/visualization,
  charting, multi-criteria screener, insider-trading tracker, fund-flow monitoring,
  aggregated broker-report summaries, macro data (VN-Index, commodities, FX, crypto),
  educational content. No AI-chat feature was visible on the fetched landing page (may
  exist deeper in the product; not confirmed).
- **FireAnt — [PARTIALLY VERIFIED]** (fireant.vn): site advertises an ecosystem
  spanning "Phần mềm · AI · Đào tạo · Truyền thông" (software/AI/training/media) and
  AmiBroker/Excel integrations, but no specific AI feature (chat, report generation,
  alerts) could be confirmed from the fetched content.
- **FiinTrade/FiinQuant — [MINIMAL/UNVERIFIED DETAIL]** (fiintrade.vn): confirmed as a
  market-data-analytics platform; no feature, pricing, or AI detail could be extracted
  from the fetched page. (Project memory already records that Stock_Massive removed
  FiinQuant-sourced price history from its own data store — see
  `store-holds-fiinquant-price-history` memory — so this vendor is already a known
  quantity internally, just not re-verified externally this session.)
- **SSI iBoard — [UNVERIFIED, no AI feature found]**: fetched page only exposed the
  branding/title; no AI capability confirmed either way.
- **VNDirect AI — [UNVERIFIED — site blocked, HTTP 403]**: could not be checked this
  session.

### Not reachable this session — [UNVERIFIED, could not fetch a primary source]

Perplexity Finance, Bloomberg Terminal AI / BloombergGPT, Fiscal.ai (ex-FinChat),
Morningstar "Mo", OpenAI's finance-specific ChatGPT features, LSEG/Refinitiv Workspace
AI, S&P Capital IQ Pro ChatIQ/Kensho, Robinhood Cortex, Tiger/Futu AI features. Each
attempt returned 403 Forbidden, 404 Not Found, 429 Too Many Requests, DNS failure, or a
CAPTCHA/bot-check page. Per the task instruction, these are skipped rather than
described from unsourced recollection presented as current fact. If this research needs
to be completed, the next session should retry with a working search tool (the `mcp
ccs-websearch` referenced in the task was not available in this runtime) or an
authenticated fetch path, since the block pattern (403 on first load, sometimes 429 on
retry) looks like bot-detection rather than a permanent absence of the page.

---

## Synthesis

### (a) Table-stakes features (present across nearly every verified platform)

1. **Citations/source attribution on every generated claim or cell** — Hebbia,
   AlphaSense, Anthropic's platform, and Gemini Deep Research all lead with this; it is
   the baseline trust mechanism, not a differentiator anymore.
2. **Natural-language screeners/Q&A over structured + unstructured data** — every
   platform in this list that has any AI feature routes a plain-language query to
   either a screener (Koyfin's 5,900 filters), a document corpus (AlphaSense,
   Hebbia), or a general web/agent loop (Gemini, Anthropic connectors).
3. **Explicit non-advice framing on retail-facing tools** — Public.com's Alpha
   disclaimer is the clearest example; this is a compliance table-stake for any
   consumer-facing product, not an optional extra.
4. **Multi-source data aggregation via connectors rather than one proprietary feed** —
   every enterprise player (Hebbia, Anthropic's platform, Rogo) integrates FactSet/
   Capital IQ/PitchBook/Snowflake/Databricks rather than building a single owned data
   pipe; the moat is the aggregation and reasoning layer, not the raw feed.

### (b) Differentiators

- **Workflow/output artifact type**: Hebbia and Rogo differentiate by producing
  finished institutional artifacts (Excel models, IC memos, decks) rather than chat
  answers — a much higher-effort, higher-trust bar than a chat response.
- **Expert-network access**: AlphaSense's Tegus expert-call integration is a genuine
  data moat that a small team cannot replicate — it is licensed human expertise, not
  scraped/computed data.
- **Deployment model**: Anthropic's Claude for Financial Services is positioned as
  infrastructure (models + connectors + implementation partners) for institutions to
  build on, not a finished product — a different competitive lane than a
  direct-to-user chat app like Stock_Massive.
- **Retail vs. institutional trust language**: Public.com is explicit and minimal
  ("not investment research"); Vietstock's "Chứng Sỹ" branding leans toward "advice"
  framing without a visible disclaimer — a meaningfully different, and legally
  riskier, choice.

### (c) Recurring AI architecture patterns

1. **Retrieval over a licensed/aggregated proprietary corpus** (Hebbia, AlphaSense) —
   the AI layer's job is ranking/summarizing/citing across a corpus the vendor spent
   years licensing, not just calling a public web-search API. Stock_Massive's
   `web_search`/`fetch_url` tools are the low-moat version of this pattern; vnstock
   fills the structured-data-tool role but has no licensed-document layer behind it
   (filings, transcripts, broker research) analogous to what AlphaSense/Hebbia have.
2. **Structured financial data as a callable tool, not free text** — every platform
   with real financial rigor (Koyfin screeners, Hebbia's typed columns, Anthropic's
   connectors) treats numeric financial data as a typed tool call with a schema,
   matching Stock_Massive's own `get_market_data` tool design and its
   host-built-`ChartAssemblyInput`-not-model-sends-numbers rule in CLAUDE.md — this is
   already architecturally aligned with the field's leading pattern, not a gap.
3. **Plan → iterative search/read → synthesize-with-citations loop for "deep
   research"** — visible in both Gemini Deep Research and (per general industry
   knowledge, not verified this session) OpenAI's deep research; Stock_Massive's own
   plan → research → counterevidence → verifier pipeline is the same shape with an
   added adversarial counterevidence step, which none of the verified platforms
   described publicly — this is a genuine, defensible design choice worth keeping and
   naming as a differentiator rather than assuming it needs replacing.
4. **Multi-source verification to suppress hallucination** — Anthropic's own framing
   ("multi-source verification... reduces errors") and AlphaSense's "no hallucinations"
   claim both point to cross-checking claims against more than one source before
   presenting them, which is exactly what a claim ledger with citations is built to do;
   Stock_Massive's `evidence/ledger.py` is not a gap relative to this cohort, it is
   table stakes correctly implemented.
5. **Untrusted-content isolation is not something any vendor page discussed publicly**
   — none of the fetched sources described how they prevent scraped/ingested content
   from altering model behavior. Stock_Massive's `untrusted.py` boundary (web/tool
   output wrapped and scanned, cannot change policy/permissions/memory/instructions) is
   ahead of what competitors disclose, though this may simply reflect that competitors
   don't publish their security architecture rather than that they lack one.

### (d) Lessons for a small team targeting Vietnamese retail/pro investors with limited data licensing

1. **Do not compete on corpus size.** AlphaSense (500M+ documents, licensed expert
   calls) and Hebbia (40+ licensed institutional feeds) win on data they spent years
   and large budgets licensing. A small team's edge has to be reasoning quality,
   transparency (claim ledger + citations), and fit to the Vietnamese-market gap
   (HOSE/HNX/UPCOM depth, Vietnamese-language reasoning) rather than raw coverage.
2. **The non-advice boundary needs to be as explicit as Public.com's, not as implicit
   as Vietstock's.** Given CLAUDE.md already treats "the research-vs-advice legal
   boundary" as a one-way door, Public.com's disclaimer wording ("not investment
   research or a recommendation," "independently verify... before making decisions")
   is a usable, low-risk template; Vietstock's "tư vấn" framing is a cautionary
   counter-example for the local market, not a model to copy.
2b. Vietstock already ships an AI chatbot for the exact HOSE/HNX/UPCOM market
   Stock_Massive targets — it is the most direct local competitor found this session
   and its lack of visible citations is a specific point of differentiation
   Stock_Massive already has (claim ledger + citations) but should not assume is
   permanent; a follow-up session should check whether Vietstock, Simplize, or FireAnt
   add citation/traceability features before this becomes stale.
3. **The plan → research → verify → cite pipeline architecture is not behind the
   frontier; it matches or exceeds what's publicly described by Google/Anthropic/
   AlphaSense.** The gap versus institutional players is data licensing and workflow
   depth (Excel/memo/deck generation), not core agent architecture — a small team
   should keep investing in the pipeline's rigor rather than assuming it needs a
   rewrite to "catch up."
4. **Treat structured data as a typed tool, never model-generated numbers** — this is
   already Stock_Massive's rule for Signal Desk charts and matches every serious
   competitor's pattern; do not relax it for new features.
5. **A golden eval harness that measures rather than asserts answer quality has no
   visible public analog among the verified platforms** — none of the fetched vendor
   pages described a public evaluation methodology. This is either a real
   differentiator worth keeping invisible (a moat competitors haven't disclosed) or an
   area where the field genuinely hasn't converged on a standard; either way it is not
   a place to cut scope for parity with competitors, since there is no competitor
   practice to converge toward.

---

## Trade-off matrix (verified platforms only)

| Platform | Data moat | Citation rigor | Retail-safe framing | Institutional depth | Adoption risk |
|---|---|---|---|---|---|
| Hebbia Matrix | Very high (licensed feeds) | High (per-cell) | N/A (not retail) | Very high | Low — funded, named enterprise customers |
| Rogo | High (bank workflows) | Unknown (undisclosed) | N/A (not retail) | Very high | Low — 350+ institutions, but young company |
| AlphaSense | Very high (500M docs + Tegus) | High (vendor-claimed) | N/A (not retail) | Very high | Low — established, large customer base |
| Koyfin | Medium (aggregated market data) | N/A (no AI on fetched page) | Retail-usable | Medium | Low — mature, self-serve pricing |
| Anthropic Claude for FS | Depends on customer's connectors | High (source-linked) | N/A (BYO-build platform) | High (infra, not finished app) | Medium — new (mid-2025), enterprise-only |
| Google Gemini Deep Research | Public web only | Medium (linked sources) | Consumer-safe framing | Low (general-purpose) | Low — backed by Google, broadly shipped |
| Public.com Alpha | Low (third-party quotes) | Low (no ledger described) | High — explicit disclaimer | N/A (retail) | Medium — "experimental" label itself |
| Vietstock Chứng Sỹ | Medium (VN market data) | Unknown (none visible) | Low — "tư vấn" framing, no visible disclaimer | N/A (retail) | Unknown — local incumbent |
| Stock_Massive (this project) | Low (web_search/vnstock only) | High (claim ledger + counterevidence) | To be confirmed against Public.com template | N/A (retail/pro) | N/A — internal |

---

## Limitations

- Roughly half the requested platforms could not be verified this session because
  vendor sites returned 403/404/429/CAPTCHA to every fetch and no working search tool
  was available; those are listed as skipped rather than guessed, per instructions.
  This materially weakens the "multiple independent sources" bar for this report — most
  verified claims rest on a single vendor page, not cross-checked press coverage or
  independent reviews.
- Nothing here was checked against pricing pages behind a paywall or login, so pricing
  data is thin across the board.
- No user reviews, analyst coverage, or third-party comparisons were consulted (only
  primary vendor sources), so claims like "no hallucinations" (AlphaSense) or "83%
  accuracy" (Anthropic) are vendor self-reporting, not independently verified — cite
  them as vendor claims if referenced elsewhere.

## Unresolved questions

1. Can a working web-search tool be restored for a follow-up pass to fill in
   Perplexity Finance, Bloomberg Terminal AI/BloombergGPT, Fiscal.ai/FinChat,
   Morningstar Mo, OpenAI's finance-specific features, LSEG Workspace AI, S&P
   Capital IQ Pro ChatIQ/Kensho, Robinhood Cortex, Tiger/Futu/moomoo, and VNDirect AI?
2. Does Vietstock's "Chứng Sỹ" chatbot (or Simplize/FireAnt) carry any explicit
   non-advice disclaimer deeper in the product that wasn't visible on the fetched
   landing page? This matters directly for how Stock_Massive should word its own
   research-vs-advice boundary relative to the closest local competitor.
3. Is there a public source describing how any of these platforms handle untrusted/
   ingested content (prompt-injection isolation), to compare against
   Stock_Massive's `untrusted.py` design — none was found this session.

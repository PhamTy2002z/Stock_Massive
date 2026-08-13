# 9router as the dev LLM gateway — research findings

- **Date:** 2026-08-10
- **Ticket:** [#18](https://github.com/PhamTy2002z/Stock_Massive/issues/18)
- **Research question:** What is 9router and how should we build an LLM layer around it so the app can use "codex" in dev without coupling to the gateway?
- **Method:** Primary sources only — 9router.com homepage, the `decolua/9router` GitHub repo (README, docs in `gitbook/content/en/`, source tree, `.env.example`, issue tracker) and the npm registry. No secondary blog posts are cited.

## What 9router is

9Router is an open-source (MIT), **self-hosted** AI routing proxy: "a smart gateway between your tools (Cursor, Claude Code, Codex, Cline, Copilot…) and 60+ AI providers", exposing everything "through one OpenAI-compatible endpoint" [1][2]. It is a Node.js/Next.js app by GitHub user **decolua**, installed via `npm install -g 9router` and run locally with the `9router` command; the server plus a management dashboard come up on `localhost:20128` [1][8]. It can also run on a VPS, in Docker (`decolua/9router`), or behind a Cloudflare tunnel [2].

Its core value proposition is **3-tier smart fallback**: Tier 1 = OAuth subscription bridges (Claude Code, OpenAI Codex, GitHub Copilot, Cursor), Tier 2 = cheap API-key providers (GLM, MiniMax, Kimi), Tier 3 = free providers (iFlow, Qwen, Kiro, OpenCode) — with automatic switching when a quota runs out, plus built-in token-compression features (RTK, Caveman mode) [1]. The project is young and fast-moving: first npm publish 2026-01-03, latest `0.5.50` on 2026-08-05, **214 versions in ~7 months**, pre-1.0 [8]. The repo has ~25k stars and a very active issue tracker [2][11].

The docs mention a "cloud" endpoint at `https://9router.com/v1` [4][5], but the `.env.example` treats `https://9router.com` as a **config cloud-sync** target for self-hosted instances [9]; whether a public hosted inference gateway exists, and under what terms, **could not be verified** from primary sources. Treat 9router as self-hosted-only for planning purposes.

## API compatibility (verdict + evidence)

**Verdict: yes, OpenAI-compatible, and that is the intended integration path.**

- Homepage: "Every endpoint is OpenAI-compatible. Point your tool to one URL" — `http://localhost:20128/v1` [1].
- Docs show a standard `POST /v1/chat/completions` curl with an OpenAI-shaped body (`model`, `messages`), and state it "works with OpenAI SDK (Python, Node.js)", LangChain and LlamaIndex [4].
- The source tree confirms the routes actually implemented: `src/app/api/v1/chat/completions/route.js`, plus `/v1/models`, `/v1/embeddings`, `/v1/responses` (OpenAI Responses API), and an **Anthropic-compatible** `/v1/messages` (+ `/v1/messages/count_tokens`) [10]. A "Format Translator" converts between OpenAI / Anthropic / Gemini request formats internally [1].
- **Auth:** `Authorization: Bearer <api-key>` with keys generated in the dashboard [2][4]. Note the default is `REQUIRE_API_KEY=false` — a bare local instance accepts unauthenticated requests unless you flip it on [9]. There is also a `/health` endpoint [4].

So the client-side contract is: OpenAI request/response schema, base URL `http://localhost:20128/v1`, Bearer auth.

## Models (incl. what "codex" maps to)

Model IDs are namespaced `<provider-prefix>/<model-name>` [2]:

- **"Codex" = the OpenAI Codex subscription bridge** (prefix `cx/`). You connect a ChatGPT Plus ($20/mo) or Pro ($200/mo) account via OAuth in the dashboard (`Connect Codex` → browser login on `localhost:1455`); 9router then auto-refreshes the token [3]. Model IDs documented: `cx/gpt-5.2-codex`, `cx/gpt-5.1-codex-max`, `cx/gpt-5.2`, `cx/gpt-5.1-codex` [3]; the README additionally lists newer `cx/` GPT-5.x variants [2]. So "using codex through 9router" means: your app sends `model: "cx/gpt-5.2-codex"` (or similar) to the OpenAI-compatible endpoint, and 9router fulfils it through the user's ChatGPT subscription — **not** through a metered OpenAI API key.
- Other subscription bridges: Claude Code `cc/*` (e.g. `cc/claude-sonnet-4-20250514`), Copilot `gh/*`, Cursor `cu/*` [2][4].
- Cheap/free providers: `glm/*`, `minimax/*`, `kimi/*`, Kiro `kr/*`, OpenCode, Vertex, etc. — 40–60+ providers total [1][2].
- **Combos:** the dashboard lets you define a custom name (e.g. `premium-coding`) that expands to an ordered fallback chain of models; you use the combo name as the `model` value and 9router "automatically tries each model in sequence until one succeeds" [6]. Model names are case-sensitive [4].

## Rate limits

9router itself imposes **no rate limits of its own** — the limits are the upstream providers', which 9router tracks per model/account and works around via fallback [2][6]. For Codex specifically: the underlying ChatGPT subscription has a **5-hour rolling quota plus weekly resets**, with Pro getting ~10× the Plus quota; exact token numbers are not published [3]. The dashboard shows live quota and reset countdowns per provider [1][2]. When everything in a chain is exhausted, requests fail (docs list "quota exhaustion" as the top cause of failed responses) [7].

## Pricing

- 9router the software is **free** (MIT, open source); you pay only the providers you connect [1][2].
- The intended "codex" setup is **BYO subscription**: an existing ChatGPT Plus/Pro account bridged via OAuth [3]. Similar bridging exists for Claude Code / Copilot / Cursor subscriptions [1][2].
- Free tiers (Kiro, OpenCode, iFlow, Qwen…) and cheap API-key providers (GLM ~$0.6/1M, MiniMax ~$0.2/1M, Kimi $9/mo) are available as fallbacks [1][2].
- Pricing/terms for the mentioned `https://9router.com/v1` cloud endpoint **could not be verified** [5].

## Streaming

Supported. Docs confirm `stream: true` on chat completions via the OpenAI SDK, delivered as SSE [2][4]; the entire proxy core lives in an `open-sse/` module (stream helpers, per-format SSE translators) [10]. Caveat: streaming interruption handling is still being fixed as of v0.5.50 (e.g. issue "finalize interrupted streaming request details") [11].

## Structured output & tool use

- **Tool use / function calling: supported.** The translation layer has dedicated tool-call handling (`open-sse/translator/concerns/toolCall.js`, OpenAI/Responses-API/Claude format translators, tool-call ID normalization tests) [10]. Recent fixes touch tool-call edge cases ("replayed tool-call IDs" for Codex, "Luna function tools on Chat Completions"), so expect occasional rough edges [11].
- **JSON mode / `response_format`: present but thinner.** `response_format`/`json_schema` appears in the request translators (e.g. `openai-to-claude.js`) and unit tests [10], but the user docs never document JSON mode or strict structured outputs [2][4]. Whether `json_schema` strict mode survives the round-trip for every backend (especially the Codex bridge, which speaks the Responses API upstream) **could not be verified** — treat it as best-effort.

## Reliability caveats (dev-time gateway; not production)

- **Pre-1.0, extremely fast churn:** 214 releases in 7 months [8]; the open issue tracker (3,200+ issues/PRs) shows active correctness bugs in exactly the paths we'd use — e.g. "Non-streaming `/v1/messages` returns OpenAI format instead of Anthropic format", "Codex request hardening", "quarantine invalidated \[Codex\] OAuth profiles" [11].
- **Subscription bridging is a policy gray zone.** 9router's own homepage says of its interception features: "mind each tool's policy" [1]; the docs contain **no explicit ToS analysis** [3][5]. Using a ChatGPT subscription's Codex quota from arbitrary API clients is plausibly outside OpenAI's intended use — **could not be verified either way from primary sources**; do not build production traffic on it.
- **No SLA of any kind:** self-hosted local process; availability depends on the daemon running and upstream providers/OAuth tokens staying valid. Token auto-refresh can fail and require manual reconnection [7].
- **Security defaults are dev-grade:** `REQUIRE_API_KEY=false`, `AUTH_COOKIE_SECURE=false` by default; docs insist on changing `JWT_SECRET` and enabling API-key auth before exposing it anywhere [5][9].
- **Fallback can silently change models** (combos), so outputs are not reproducible across requests unless you pin a single concrete model ID [6].

Conclusion: 9router is a **developer-workstation gateway** for stretching subscriptions/free tiers. Fine as the dev-time LLM backend; production must point at a real provider API.

## Provider-agnostic LLM layer sketch

Design for `apps/api` (FastAPI): the app must not know 9router exists — only an OpenAI-compatible endpoint whose location comes from config.

**Interface boundary** — one small service in `src/core/llm.py`, next to the other shared infra (config, cache, vnstock client):

```python
class LLMClient(Protocol):
    async def complete(
        self, messages: list[Message], *,
        tools: list[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
        stream: bool = False,
        temperature: float | None = None,
    ) -> Completion | AsyncIterator[CompletionChunk]: ...
```

Domain code in `src/stocks/**` depends only on this protocol; nothing outside `src/core/llm.py` imports the transport SDK.

**Config-driven** — extend the existing pydantic-settings config with:

```
LLM_BASE_URL=http://localhost:20128/v1   # dev: 9router
LLM_API_KEY=...                          # dev: dashboard key (enable REQUIRE_API_KEY)
LLM_MODEL=cx/gpt-5.2-codex               # dev: Codex via subscription bridge
LLM_TIMEOUT_SECONDS=60
```

Prod flips these to the real provider (`https://api.openai.com/v1` + real key + `gpt-5.x`) with zero code changes. Never hardcode the `cx/` prefix outside config — it is a 9router-ism [2][3].

**Transport** — since 9router is OpenAI-compatible and explicitly tested against the OpenAI SDK [4], use the official `openai` Python package as the single transport: `AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)`, wrapped by an `OpenAICompatibleLLMClient` implementing the protocol. One code path for dev and prod.

**Lowest-common-denominator features** (based on what was actually verified above):

| Safe to rely on | Use with care / avoid |
|---|---|
| `POST /v1/chat/completions`, `messages`, `temperature`, `max_tokens` [1][4] | Strict `json_schema` structured outputs — undocumented in 9router; validate + repair-retry app-side instead |
| SSE streaming (`stream: true`) [2][4] | Parallel / replayed tool calls — active bug surface in 9router [11] |
| Basic tool calling (single tool, sequential) [10] | `logprobs`, seeds, prompt caching, `store` — not documented for 9router; assume absent in dev |
| `/v1/models` listing, `/health` for readiness checks [4][10] | Anthropic `/v1/messages` route — has known format bugs [11]; stick to the OpenAI surface |

Rule of thumb: constrain the internal `LLMClient` API to the left column; anything in the right column must degrade gracefully (e.g. `response_format` requested but response validated with Pydantic and retried once on parse failure).

**Failure handling** — treat the dev gateway as flaky by design:

- Per-request timeout (`LLM_TIMEOUT_SECONDS`, generous for streaming first-token).
- Retries with exponential backoff + jitter on 429/5xx/connection errors, small cap (2–3 attempts) — 9router already does provider fallback internally [6], so aggressive client retries just burn quota.
- Surface a single typed `LLMUnavailableError` to callers; LLM features must be optional decorations on the stock-data pipeline, never on the critical path (quota exhaustion mid-day is an expected dev event [3][7]).
- Log the resolved model from the response (`response.model`) — with combos/fallback the served model can differ from the requested one [6].

## Sources

All primary (9router's own site, repo, docs, registry data). Accessed 2026-08-10.

1. https://9router.com/ — homepage (rendered text: product description, tiers, endpoints, features, MITM policy note)
2. https://github.com/decolua/9router — repo + README (license, install, endpoint, model prefixes, providers, streaming, security env vars)
3. https://raw.githubusercontent.com/decolua/9router/master/gitbook/content/en/providers/subscription.md — Codex/subscription provider docs (cx/ model IDs, OAuth flow, 5-hour/weekly quotas, Plus vs Pro)
4. https://raw.githubusercontent.com/decolua/9router/master/gitbook/content/en/integration/other-tools.md — API integration docs (base URLs, `/v1/chat/completions`, Bearer auth, OpenAI SDK, streaming, `/health`)
5. https://raw.githubusercontent.com/decolua/9router/master/gitbook/content/en/faq.md — FAQ (cloud endpoint mention, JWT_SECRET warning, local data storage)
6. https://raw.githubusercontent.com/decolua/9router/master/gitbook/content/en/features/combos.md — combo fallback chains
7. https://raw.githubusercontent.com/decolua/9router/master/gitbook/content/en/troubleshooting.md — failure modes (quota exhaustion, token refresh, ECONNREFUSED)
8. https://registry.npmjs.org/9router — npm metadata (v0.5.50 on 2026-08-05, first publish 2026-01-03, 214 versions, MIT, `9router` bin)
9. https://raw.githubusercontent.com/decolua/9router/master/.env.example — runtime env contract (`PORT=20128`, `REQUIRE_API_KEY=false`, `CLOUD_URL`)
10. GitHub code search in `decolua/9router` — route files under `src/app/api/v1/` (`chat/completions`, `messages`, `responses`, `models`, `embeddings`) and `open-sse/translator/` (toolCall.js, json_schema handling, format translators)
11. https://github.com/decolua/9router/issues — open issues as of 2026-08-10 (e.g. #3199 `/v1/messages` format bug, #3194 Codex OAuth quarantine, #3186/#3174 tool-call fixes, #3175 interrupted streaming)

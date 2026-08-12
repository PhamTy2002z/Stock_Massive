# Tool calling, streaming, and structured output through 9router — research findings

- **Date:** 2026-08-12
- **Ticket:** [#28](https://github.com/PhamTy2002z/Stock_Massive/issues/28) (part of [#16](https://github.com/PhamTy2002z/Stock_Massive/issues/16); blocks [#32](https://github.com/PhamTy2002z/Stock_Massive/issues/32))
- **Prior art:** [#18](https://github.com/PhamTy2002z/Stock_Massive/issues/18) / `research/9router-llm-gateway` established that 9router is an OpenAI-compatible routing proxy. This ticket asks the harder question: can it carry an *agent*?
- **Research question:** Does the dev LLM path support what a tool-calling agent harness needs — faithful `tools`/`tool_choice`/`tool_calls`, streamed tool-call argument deltas, mid-stream cancellation, JSON-schema structured output, per-request token usage — and if not, what is the dev fallback?
- **Method:** Primary sources only. 9router: the `decolua/9router` source at **v0.5.50** (shallow clone, read directly), its gitbook docs, and its GitHub issue tracker. OpenAI: the official OpenAPI spec (`openai/openai-openapi`, v2.3.0), the official API reference and guides, and the shipped `openai-python` / `openai-node` source. Codex: OpenAI's own model/deprecation/changelog pages and the `openai/codex` source. **Two claims are demonstrated by executing 9router's own translator code** rather than argued from reading — see [Reproducing the probes](#reproducing-the-probes). No blog posts or secondary summaries are cited.
- **Access constraints, recorded for reproducibility:** `platform.openai.com/docs/*` now returns HTTP 403 behind a Cloudflare bot challenge and 301-redirects to `developers.openai.com`, which OpenAI's own `llms.txt` designates as the Markdown docs source — all OpenAI doc citations use that host. `openai.com/policies/*` and `help.openai.com/*` return HTTP 403 and **could not be read**, so the ToS question below is answered "unverified" rather than guessed.

---

## Verdict

**No. 9router cannot carry a real tool-calling agent loop on the `cx/` (codex) route, and the failure is silent.** Three independent defects, all verified in v0.5.50 source:

1. **`tool_choice` and `response_format` are silently dropped** before the request leaves 9router. Not rejected — dropped. You cannot force a tool, and you cannot get schema-enforced JSON. [§Tool calling](#tool-calling-request-direction), [§Structured output](#structured-output)
2. **Streamed parallel tool calls collapse into one corrupted call.** 9router ignores the upstream `output_index` and demultiplexes on a counter that only advances at item close, so two concurrent tool calls get their `arguments` concatenated into a single invalid-JSON blob and one call is lost — with the wrong `id` and `name` on the survivor. Demonstrated by running 9router's own code. And this is the **default** path, not an edge case: OpenAI's `parallel_tool_calls` defaults to `true`, and the one parameter that would disable it is itself among the dropped fields. [§The parallel tool-call collapse](#the-parallel-tool-call-collapse)
3. **The model target named in #18 no longer exists.** `gpt-5.2-codex` and the whole `gpt-5.x-codex` family were **shut down on 2026-07-23**; 9router's own docs still recommend `cx/gpt-5.2-codex` while its code has already moved to `cx/gpt-5.6-sol`. [§Where codex falls short](#where-codex-specifically-falls-short)

**Single tool calls, streamed, do work correctly on the codex route** — so a naive smoke test passes and the defect surfaces only under parallel calls or forced tool choice. That is the dangerous part.

**The fallback is not "a different model behind 9router" — it is a different route through it.** Point the gateway at a provider whose *native wire format is already OpenAI Chat Completions*, which makes 9router a byte-level passthrough and removes the entire translation layer that causes 1–3. [§The dev fallback](#the-dev-fallback)

---

## Why the codex route is special: the pipeline

Everything below follows from one architectural fact. 9router's `/v1/chat/completions` is not a proxy for the codex provider — it is a **format translator**, and it translates twice:

```
our client                9router                                   upstream
Chat Completions  ──►  openaiToOpenAIResponsesRequest()   ──►  Responses API
                       (request translation)                  chatgpt.com/backend-api/codex/responses
Chat Completions  ◄──  openaiResponsesToOpenAIResponse()  ◄──  Responses SSE events
                       (response translation, per chunk)
```

The codex provider declares this in the registry — `transport.baseUrl = "https://chatgpt.com/backend-api/codex/responses"`, `format: "openai-responses"`, `forceStream: true` [1]. `forceStream: true` matters: **9router always streams upstream, even when our client asked for `stream: false`**, then reassembles JSON [2]. The two reassembly paths behave differently, which is why streaming and non-streaming disagree on parallel tool calls.

By contrast a provider with no `format` override inherits the schema default `format: "openai"` [48] — e.g. `openai`, whose `transport.baseUrl` is `https://api.openai.com/v1/chat/completions` [3]. For those, **format translation is skipped on both directions**:

- Request side, `translateRequest` guards the entire conversion behind `if (sourceFormat !== targetFormat)` under the comment "If same format, skip translation steps" [4].
- Response side, `needsTranslation` is literally `sourceFormat !== targetFormat` [4], so the stream takes `createPassthroughStreamWithLogger` [5].

`tools`, `tool_choice`, `parallel_tool_calls`, and `response_format` are therefore never touched on that route. **That distinction is the whole fallback story.** The one caveat: two helpers run unconditionally on *every* route, same-format included — `ensureToolCallIds` and `fixMissingToolResponses` [4][13], described below.

A note on trusting sources here: 9router's user docs never mention tool calling, function calling, JSON mode, or structured output **anywhere** — a grep for those terms across `gitbook/content/en/` returns nothing [6]. Worse, the docs actively recommend model IDs that its own code no longer defines (`cx/gpt-5.2-codex` [7], and `cx/deepseek-chat` [8] — `cx` is the Codex prefix, DeepSeek is a different provider entirely). **The source is the only authority; the docs are stale and internally inconsistent.** #18's statement that "tool calling is supported per the docs" does not hold — it is supported *in code*, undocumented, and partly broken.

---

## The contract 9router claims to implement

9router advertises OpenAI compatibility, so the OpenAI Chat Completions spec is the yardstick. The relevant clauses, from the official OpenAPI spec (v2.3.0) and OpenAI's own reference:

- **`tool_choice`** accepts `"none" | "auto" | "required"` or a named tool. In Chat Completions the named form is **nested**: `{"type":"function","function":{"name":"..."}}` — *not* the flat Responses-style `{"type":"function","name":"..."}` [50]. Default is `"auto"` when tools are present [50].
- **`parallel_tool_calls` defaults to `true`** [50]. The guide is explicit that disabling it is how you get at-most-one call: *"The model may choose to call multiple functions in a single turn. You can prevent this by setting `parallel_tool_calls` to `false`, which ensures exactly zero or one tool is called."* [51]
- **Streamed tool-call deltas**: `delta.tool_calls[]` items are `ChatCompletionMessageToolCallChunk`, whose **only required field is `index`** — `id`, `type`, `function.name`, `function.arguments` are all optional per fragment [52]. `index` is the slot in the assistant message's `tool_calls` array, and `function.arguments` arrives as **partial string fragments the client concatenates**. OpenAI's own shipped accumulators encode exactly this: openai-node does `tool_call.function!.arguments += fn.arguments` into `choice.message.tool_calls[index] ??= {}` [53], and openai-python's `_deltas.py` carries the comment *"the `index` property is used in arrays of objects so it should not be accumulated like other values"* and raises if a list delta entry lacks `index` [54].
- **`finish_reason: "tool_calls"`** signals a tool turn, streaming and non-streaming alike [50][52].
- **`arguments` is a JSON-encoded string**, and the spec warns *"the model does not always generate valid JSON… Validate the arguments in your code before calling your function."* [50]
- **Usage in streaming** requires `stream_options: {include_usage: true}`, which adds *"an additional chunk … streamed before the `data: [DONE]` message"* whose `choices` *"will always be an empty array"*; without it, chunks carry no `usage` [50]. And the spec's own caveat: *"If the stream is interrupted or cancelled, you may not receive the final usage chunk."* [50]
- **`response_format: {"type":"json_schema", json_schema:{name, strict, schema}}`** with `strict: true` requires every field `required`, `additionalProperties: false` on every object, an object at the root, and a restricted JSON-Schema subset (no `allOf`/`not`/`if`/`then`/`else`); an unsupported schema under `strict: true` is an error [55]. A `refusal` field on the assistant message signals a refusal that does not follow the schema [55].
- **Cancellation** is undocumented server-side: there is no cancel endpoint for chat completions, and **billing behavior on mid-stream abort is not stated** [50][56]. Officially, aborting is a client concern — openai-node's `ChatCompletionStream` documents *"stopping iteration early aborts the underlying request"* [57], and openai-python's `.stream()` requires a context manager so the response is closed on exit [58].

**Conformance check on the codex route.** 9router's *shape* is compliant: the opening tool-call delta carries `index`, `id`, `type:"function"` and `function.name`; argument fragments carry `index` + `function.arguments`; the terminal chunk sets `finish_reason: "tool_calls"` [14], all confirmed in probe 1. Three deviations matter:

1. **`parallel_tool_calls` is dropped, and its spec default is `true`** [50][9]. So parallel calls are *on* by default upstream, and **the single mitigation OpenAI provides — setting it to `false` — is precisely the parameter 9router discards.** The collapse in the next section is therefore the default configuration, not an exotic edge case.
2. **`tool_choice` is dropped twice, and the second drop is a shape mismatch.** Besides the translator never forwarding it, 9router's inbound normalizer emits the correct nested Chat Completions form `{type:"function", function:{name}}` [59], while the codex executor validates the **flat** Responses form, reading `body.tool_choice.name` [10]. A nested value has no top-level `.name`, so the guard computes an empty name and executes `delete body.tool_choice`. Even if the translator were fixed, the executor would still strip it.
3. **Usage placement deviates.** 9router deletes `stream_options` on codex [10] yet attaches `usage` to the finish chunk anyway [14] — more generous than the spec when `include_usage` is absent, but a client that *does* request it gets usage on a chunk that still has a populated `choices` array, rather than the spec's separate empty-`choices` chunk before `[DONE]`. Harmless for the OpenAI SDKs, but do not build on the exact chunk layout.

---

## Tool calling: request direction

**`tools` translate faithfully. `tool_choice`, `parallel_tool_calls`, and `response_format` do not survive.**

`openaiToOpenAIResponsesRequest` builds the upstream body field by field, and the pass-through list at the end of the function is explicit [9]:

```js
if (body.temperature !== undefined) result.temperature = body.temperature;
if (body.max_tokens !== undefined) result.max_tokens = body.max_tokens;
if (body.top_p !== undefined) result.top_p = body.top_p;
if (body.reasoning !== undefined) result.reasoning = body.reasoning;
if (body.reasoning_effort !== undefined) result.reasoning = { effort: body.reasoning_effort, summary: "auto" };
if (body.service_tier !== undefined) result.service_tier = body.service_tier;
```

`tool_choice` is absent. `parallel_tool_calls` is absent. `response_format` is absent. Nothing else in the function references them.

Then the codex executor applies a hard allowlist and a deletion list [10]:

```js
const RESPONSES_API_ALLOWLIST = new Set([
  "model", "input", "instructions", "tools", "tool_choice", "stream", "store",
  "reasoning", "service_tier", "include", "prompt_cache_key", "client_metadata",
  "text"
]);
```
```js
delete body.temperature;  delete body.top_p;    delete body.max_tokens;
delete body.max_completion_tokens;  delete body.max_output_tokens;
delete body.seed;  delete body.n;  delete body.stream_options;
// ...then: for (const k of Object.keys(body)) if (!RESPONSES_API_ALLOWLIST.has(k)) delete body[k];
```

Note the trap: `tool_choice` **is** allowlisted, so reading the executor alone suggests it works — but the request translator never populated it, so the allowlist entry is dead for chat-completions clients. Equally, `text` (the Responses API's structured-output field) is allowlisted, but **nothing anywhere in the codebase ever populates `text.format`** — a repo-wide grep finds no writer [11].

I confirmed this end-to-end by executing the real translator plus the real allowlist against a representative agent request ([probe 2](#reproducing-the-probes)). A request carrying `tool_choice`, `response_format: json_schema`, `parallel_tool_calls`, `temperature`, `max_tokens`, `seed`, and `stream_options` produces this upstream body:

```
keys: input, instructions, model, store, stream, tools
tool_choice present?      false
response_format present?  false
text present?             false
```

`stream` came out `true` despite `stream: false` on the request; `store` is forced `false`.

**What does translate correctly:**

- `tools[].function.{name,description,parameters}` → Responses flat `{type:"function", name, description, parameters}`, with `strict` preserved [9]. Object schemas missing `properties` get `properties: {}` injected, because Codex rejects them otherwise [9].
- The **assistant-message round-trip is correct**, including parallel calls: `assistant.tool_calls[]` → one `function_call` item per call (`call_id`, `name`, `arguments`), and each `{role:"tool", tool_call_id, content}` → a `function_call_output` item [9]. Probe 2 shows the expected item sequence: `message | function_call(get_price) | function_call(get_volume) | function_call_output | function_call_output`.
- `call_id` is clamped to 64 chars, because the Responses API enforces that limit [9].

**Two further request-side behaviors worth knowing:**

- **Only the first system/developer message survives.** The loop sets `instructions` from the first instruction-bearing message and then `continue`s past *every* system message, so a second `system` message is silently discarded [9].
- **Sampling is not controllable on codex.** `temperature`, `top_p`, `max_tokens`, `max_completion_tokens`, `max_output_tokens`, `seed`, and `n` are all deleted [10]. You cannot cap output length. This mirrors OpenAI's own client, whose `ResponsesApiRequest` struct carries no sampling fields at all [12] — so it is upstream-correct, but it means the cost controls in #25 cannot use `max_tokens`.

### Tool-call ID handling and synthetic results

Two shared helpers rewrite tool-call bookkeeping for *all* routes, not just codex [13]:

- `ensureToolCallIds` sanitizes IDs to Anthropic's `^[a-zA-Z0-9_-]+$`. Normal OpenAI IDs (`call_abc123`) pass untouched. Edge case: if an ID is *entirely* invalid characters, sanitizing returns null and the assistant call and its matching tool result are regenerated by **different** formulas — `generateToolCallId(i, j, name)` vs `generateToolCallId(i, 0)` — so a matched pair can be split apart. Only reachable with pathological IDs; avoid non-alphanumeric tool-call IDs and it cannot fire.
- `fixMissingToolResponses` **injects synthetic empty tool results** (`{role:"tool", tool_call_id, content:""}`) when an assistant message with `tool_calls` is not followed by a matching result. This silently repairs a malformed history rather than erroring — convenient for CLI clients, but it means a bug in our loop shows up as the model reasoning over empty tool output instead of a 400.

---

## Tool calling: streaming response direction

**Single tool call: correct. Parallel tool calls: corrupted.**

For a single call, `openaiResponsesToOpenAIResponse` emits exactly the OpenAI contract [14]: on `response.output_item.added` a first delta carrying `index`, `id`, `type:"function"`, `function.name` and `arguments:""`; then one delta per `response.function_call_arguments.delta` carrying `index` and an `arguments` fragment; then `finish_reason: "tool_calls"`. Probe 1 confirms a clean round trip with valid reassembled JSON.

### The parallel tool-call collapse

The translator tracks the current call in **two scalars**, not a map [14]:

```js
// on response.output_item.added (function_call):
state.currentToolCallId = item.call_id || fallbackToolCallId();
return buildChunk(..., { tool_calls: [{ index: state.toolCallIndex, id: state.currentToolCallId, ... }] });

// on response.function_call_arguments.delta:
return buildChunk(..., { tool_calls: [{ index: state.toolCallIndex, function: { arguments: argsDelta } }] });

// on response.output_item.done (function_call):
state.toolCallIndex++;
```

`state.toolCallIndex` advances **only when an item closes**, and `data.output_index` — the field the Responses API provides precisely to disambiguate concurrent output items — **is never read on this path**. A repo grep for `data.output_index` in `open-sse/` returns nothing [15]; the sibling non-streaming converter *does* read it (`state.items.set(parsed.output_index ?? 0, parsed.item)` [16]), which shows the omission here is an oversight rather than a design choice.

Consequence: the translator is only correct if upstream emits function-call items **strictly sequentially** (each `added → deltas → done` fully closed before the next opens). If two items are open at once, every argument fragment is attributed to whichever index happens to be current.

Running 9router's own translator over three event orderings ([probe 1](#reproducing-the-probes)) gives:

| Upstream event ordering | Result |
|---|---|
| Strictly sequential (`addA … doneA`, then `addB … doneB`) | ✅ 2 calls, both valid JSON |
| Both items announced, then deltas interleaved | ❌ **1 call**; `args = {"t":{"t":"VNM"}"FPT"}` → invalid JSON |
| Both items announced, deltas grouped per call | ❌ **1 call**; `args = {"t":"VNM"}{"t":"FPT"}` → invalid JSON |

In both failure cases the surviving call also inherits the **wrong** `id` and `name` (`call_B`/`get_volume`), because the later `added` event overwrites the scalars. The first tool call is silently destroyed.

Honest boundary on this finding: **whether the live Codex backend interleaves function-call items is unverified** — I could not exercise the ChatGPT backend, and the Responses API reference does not state an ordering guarantee for concurrent output items. So this is not proof that parallel calls fail in production today. It *is* proof that 9router has **no defense** against the ordering the protocol permits: correctness rests entirely on an upstream emission order that is neither documented nor enforced, and any upstream change silently corrupts tool arguments. For an agent loop that is an unacceptable foundation.

### Non-streaming is *better* here

A client asking for `stream: false` on codex takes a different reassembly path, and that path is correct. `convertResponsesStreamToJson` keys completed items into a `Map` by `output_index` and reads the **complete** `arguments` string from each `response.output_item.done` item [16]; `handleForcedSSEToJson` then maps *every* `function_call` item in the resulting `output` array into `tool_calls[]` [2]. Parallel tool calls survive intact.

So on the codex route: **non-streaming preserves parallel tool calls, streaming corrupts them.** That inversion of the usual expectation is worth writing down.

---

## Streaming

SSE streaming works and is the default. Mechanics that matter for an agent:

- Every route ends in `pipeWithDisconnect`, which pipes the upstream body through a byte tap and the transform stream, with a **stall watchdog rearmed on every upstream chunk** [17].
- `[DONE]` and the `onStreamComplete` usage callback are both emitted from the transform stream's `flush()` [18] — i.e. only on *normal* completion. See cancellation below.
- `stream_options: {include_usage: true}` is **deleted** on the codex route (`delete body.stream_options; // Cursor sends this but Codex doesn't support it` [10]) and on grok-cli [19]. It is not needed there: usage is attached to the final chunk unconditionally when upstream reports it [14]. The `iflow` executor conversely *injects* it to obtain usage [20]. Net: do not rely on `include_usage`; read `usage` off the final chunk if present.

---

## Cancellation mid-stream

**Upstream is cancelled, but the client sees a truncated stream with no terminator, and the request's usage is never recorded.**

Client disconnect flows into `createStreamController().handleDisconnect`, which logs, then **aborts the upstream fetch after a 500 ms delay** [21]:

```js
abortTimeout = setTimeout(() => { abortController.abort(); }, 500);
```

Quota is therefore released promptly — good. What the client sees is less clean:

- The stream is closed via `controller.close()` in `createDisconnectAwareStream` [21]. A synthesized terminal event is only emitted when `onAbortTerminal` is set, and `streamingHandler` sets it **only for the Responses→Responses passthrough** (`isResponsesPassthrough`) [22]. **For a Chat Completions client the stream just ends** — no final chunk with `finish_reason`, no `data: [DONE]`. An OpenAI SDK consuming it sees the iterator end mid-tool-call; partial `arguments` must be discarded by our code.
- Because `[DONE]`/`flush()` never run, **`onStreamComplete` never fires**, so the cancelled request contributes **no usage record** [18]. Tokens were still spent upstream. A cost budget (#25) that sums 9router-reported usage will under-count every cancelled request. In fairness this matches OpenAI's own documented caveat — *"If the stream is interrupted or cancelled, you may not receive the final usage chunk"* [50] — so it is spec-consistent rather than a 9router defect. The missing `[DONE]` is the part that is not.
- The placeholder row written at stream start (`"[Streaming in progress...]"` [22]) is never updated, so the dashboard keeps a stuck record.
- A separate hard stop exists: `STREAM_STALL_TIMEOUT_MS` (default **360 000 ms**) with no upstream bytes triggers `handleError` + `abort` [17]. Non-stream aborts surface as HTTP **499 "Request aborted"** [23].

---

## Structured output

**Unavailable on codex. Prompt-injected (not enforced) on Claude and generic OpenAI-compatible routes. Native only where 9router passes the body through untouched.** This directly threatens the nightly pipeline in #23.

Behavior by route:

| Route | `response_format: json_schema` behavior |
|---|---|
| `cx/*` (codex) | **Dropped entirely.** Never translated into the Responses `text.format` field, and stripped by the allowlist [9][10][11]. Probe 2 confirms. |
| `cc/*` (Claude) | **Prompt injection.** Converted into a system-prompt paragraph — "You must respond with valid JSON that strictly follows this JSON schema… Respond ONLY with the JSON object" — and Anthropic's real structured-output mechanism is not used [24]. |
| `openai-compatible-*` | **Downgraded.** `applyJsonSchemaFallback` prompt-injects the schema and rewrites the request to `response_format: {type:"json_object"}` [25]. Applies *only* to providers whose id starts with `openai-compatible-`. |
| Native OpenAI-format providers (e.g. `openai`) | **Passthrough** — `response_format` is forwarded intact; the only body mutations are `applyJsonSchemaFallback` (not applicable), `stripUnsupportedParams` (no rule matches), and reasoning injection [5][26]. |

There is also **no capability flag for structured output anywhere** in 9router's model metadata: `capabilities.js` derives flags from models.dev and tracks `tools`, `vision`, `reasoning`, `search`, etc., but nothing for JSON schema [27]. So 9router cannot route a structured-output request to a model that supports it, and `detectRequiredCapabilities` — which decides capacity-adapter routing — only inspects **modalities** (image/pdf/audio/video) and **never `tools`** [28]. A tools-requiring request can therefore be auto-routed to a model that cannot call tools.

9router's tracker corroborates all of this with open bugs: **#2896 "Codex route breaks Chat Completions json_schema and non-streaming response reconstruction"**, **#1343 "[Bug] json_schema response_format rejected with 400 Invalid JSON body"**, and **#2003** requesting structured-output support for Gemini routes [29].

---

## Token usage reporting

Usage *is* reported per request, but **the numbers a client reads are deliberately not the upstream numbers.** This matters directly for #25.

- On streaming finish chunks, 9router applies `addBufferToUsage`, which adds a flat **`BUFFER_TOKENS = 2000`** to `prompt_tokens` (and `input_tokens`, and `total_tokens`) [30]. This happens **even when upstream reported exact usage** — the buffered copy goes to the client while the unbuffered original is kept for the DB/dashboard [18]. So the API client over-reports prompt tokens by exactly 2000 per streamed request, while the dashboard shows the true figure.
- When upstream reports **no** usage, 9router **estimates**: `prompt_tokens = ceil(JSON.stringify(body).length / 4)` and `completion_tokens = floor(contentLength / 4)` [31] — then adds the same 2000 buffer, since `formatUsage` also calls `addBufferToUsage` [31]. Estimated payloads carry an **`estimated: true`** marker that survives field filtering [31], so a client *can* detect them. Our cost accounting should check for it.
- Cancelled streams report nothing at all (above).
- Codex-route shape: on streaming, usage is taken from the `response.completed` event and mapped to `prompt_tokens`/`completion_tokens`/`total_tokens` plus `prompt_tokens_details.cached_tokens` from `input_tokens_details.cached_tokens` [14][32]. Verified in probe 1: `{"prompt_tokens":100,"completion_tokens":20,"total_tokens":120,"prompt_tokens_details":{"cached_tokens":64}}`.
- **Streaming and non-streaming report different cache detail for the same request.** `convertResponsesStreamToJson` accumulates only `input_tokens`/`output_tokens`/`total_tokens` and never copies `input_tokens_details` [16], so the cache-folding logic downstream (`cacheRead = usage.cache_read_input_tokens || usage.cached_tokens || 0` [2]) always sees 0. `prompt_tokens` agrees between the two paths; **`cached_tokens` visibility does not.** Upstream `total_tokens` is discarded in favour of `input + output` on both paths.

---

## Limits: request size, timeouts, concurrency

| Limit | Value | Source |
|---|---|---|
| Client request body | **128 MB** default, env `NINEROUTER_PROXY_CLIENT_MAX_BODY_SIZE` | [33] |
| Stream stall (no upstream bytes) | **360 000 ms**, env `STREAM_STALL_TIMEOUT_MS` | [34] |
| Time to first token | **200 000 ms**, env `STREAM_FIRST_CHUNK_TIMEOUT_MS` | [34] |
| Upstream connect | **60 000 ms**, env `FETCH_CONNECT_TIMEOUT_MS` | [34] |
| Default max tokens | 64 000 (`DEFAULT_MAX_TOKENS`) — not applied on codex, which deletes it | [34][10] |
| 9router-side rate limit | **None.** All limits are upstream's | [35] |
| 9router-side concurrency cap | **None.** No semaphore/queue/limiter exists in the request path | [35] |

The size and timeout budgets are generous — a multi-turn tool loop will not hit them. **Concurrency is the real hazard, and not because of a cap.** Open bug **#3164 "Responses swapped between concurrent requests to the same model"** (filed 2026-08-08 against v0.5.50, still open) reports that two concurrent same-model requests received **each other's responses** [36]. The reporter's own diagnosis:

> "Response stream is attached to the wrong request when two requests with the same model id are in flight concurrently (connection/stream bookkeeping bug)"

Critically, they could not reproduce it with independent connections, only through a client that **multiplexes over keep-alive** — which is exactly what a pooled `AsyncOpenAI`/httpx client does. For the nightly pipeline (#23) this means: **serialize requests, or use a distinct model alias per concurrent worker,** until #3164 closes. Also relevant: fusion-strategy combos **strip `tools` and `tool_choice`** from panel calls by design [37], so a fusion combo can never do tool calling. Plain `fallback`/round-robin combos preserve them.

---

## Where codex specifically falls short

Beyond the translation defects, the codex target itself has moved out from under #18's recommendation.

**1. The models are shut down.** OpenAI's deprecation page lists `gpt-5-codex`, `gpt-5.1-codex`, `gpt-5.1-codex-max`, and `gpt-5.2-codex` under "Legacy GPT model snapshots (July 2026 shutdown)", **shutdown date 2026-07-23**, all four replaced by `gpt-5.6-sol`; the page defines shutdown as "no longer accessible" [38]. **`LLM_MODEL=cx/gpt-5.2-codex` as recommended in #18 is dead.** 9router's code has already moved on — the `cx/` registry now lists `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex-spark` [1] — while its **docs still recommend the shut-down ID** [7].

**2. The capability gap was never the model.** While live, `gpt-5.2-codex`, `gpt-5.1-codex-max`, and `gpt-5.1-codex` all listed **streaming, structured outputs, and function calling** as supported [39][40][41]. The shortfall is the **endpoint surface**: every codex model page lists **only `v1/responses`** as supported and explicitly excludes Chat Completions [39][40][41]. So the mangling documented above is 9router's translation layer, not a model limitation.

**3. Codex has abandoned Chat Completions outright.** `WireApi` in `openai/codex` now has a single variant, `Responses`, and `wire_api = "chat"` is a hard deserialization error [42]; the linked announcement (Discussion #7782, "Deprecating `chat/completions` support in Codex") states full removal was slated for early February 2026 and warns: "If your organization uses an LLM proxy or gateway, please coordinate with your IT or platform team to ensure your proxy supports the `responses` API" [43]. We are on the wrong side of that migration by construction.

**4. The subscription bridge is a different, unsanctioned contract — and 9router says so.** The `cx/` route targets `https://chatgpt.com/backend-api/codex/responses` [1], the ChatGPT backend, not `api.openai.com`. 9router authenticates it by **impersonating the Codex CLI**: the registry hardcodes OAuth client id `app_EMoamEEZ73f0CkXaXp7hrann` with `originator: "codex_cli_rs"` and `User-Agent: "codex_cli_rs/0.136.0"` [1] — byte-identical to the client id in Codex's own source [12]. 9router marks the provider **`deprecated: true`** with a first-party risk notice [44]:

> "⚠️ Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk."

Whether OpenAI's terms specifically prohibit backing programmatic API traffic with a ChatGPT subscription is **unverified** — `openai.com/policies/*` and `help.openai.com/*` return HTTP 403 to this environment, so the exact clause text could not be read. 9router's own warning is sufficient grounds regardless.

**5. One 9router-side note in codex's favour.** The **`/v1/responses`** endpoint forces `sourceFormat = "openai-responses"` [45], which for a `cx/` model matches the provider's own format — so no request translation runs, and `text.format` and `tool_choice` would reach Codex intact. Speaking the Responses API natively is therefore structurally sounder than the chat-completions surface. This is **inferred from code and not verified end-to-end**, and it means giving up OpenAI-Chat-Completions portability — the one property that makes our LLM layer provider-agnostic. Not recommended, but recorded.

---

## Model matrix: what actually works where

Derived from the translator registrations and executors, for the features an agent loop needs.

| Route | Streamed tool calls | Parallel (streamed) | `tool_choice` | `json_schema` | Notes |
|---|---|---|---|---|---|
| `openai` and other **native OpenAI-format** providers | ✅ passthrough | ✅ passthrough | ✅ | ✅ native | No translation runs at all [4][5] |
| `cx/*` codex | ⚠️ single only | ❌ collapses | ❌ dropped | ❌ dropped | Also: no sampling params; subscription risk [9][10][14] |
| `cc/*` Claude | ✅ translated | ✅ translated | ✅ translated | ⚠️ prompt-injected | Tool names get an OAuth prefix and are mapped back; a Claude Code system prompt is prepended to every request [24]. `temperature` is stripped [26] |
| `openai-compatible-*` | ✅ | ✅ | ✅ | ⚠️ downgraded to `json_object` + prompt | [25] |
| Gemini / `gemini-*` | ✅ translated | ✅ translated | ✅ translated | ❌ | Some JSON Schema keywords are dropped (`uniqueItems`, `contains`, `multipleOf`, …) [46] |
| **Fusion** combos | ❌ | ❌ | ❌ | — | `tools`/`tool_choice` stripped by design [37] |
| `fallback` / round-robin combos | ✅ | inherits member | ✅ | inherits member | Served model may differ from requested |

Two cross-cutting caveats: tool support is *not* considered when the capacity adapter reroutes a request [28], and the `tools: true` capability flag comes from models.dev rather than first-hand testing [27].

---

## The dev fallback

**Keep 9router if it is useful for quota juggling, but stop using the `cx/` route for anything agentic, and stop treating "codex" as the dev model.** In order of preference:

1. **Preferred — a real metered OpenAI API key through 9router's `openai` provider.** This is the *only* configuration that gives correct tool calling and native structured output with zero code change, because 9router does no translation: format matches, so the request is forwarded and the SSE stream is passed through [3][4][5]. Set `LLM_BASE_URL=http://localhost:20128/v1` and `LLM_MODEL=openai/gpt-5.6-sol` (current frontier; `gpt-5.6` aliases to `sol` [47]). Still subtract the 2000-token usage buffer [30] and serialize concurrent calls until #3164 closes [36].
2. **Equally correct and cheaper — bypass 9router in dev.** Point `LLM_BASE_URL` straight at `https://api.openai.com/v1`. The provider-agnostic `LLMClient` from #18 makes this a config flip, and it removes the translation layer, the 2000-token buffer, the concurrency bug, and the ToS risk in one move. Keep 9router in the loop only when its fallback/quota features are actively wanted.
3. **Free/local option that preserves the contract — any OpenAI-native provider.** A local Ollama or a cheap OpenAI-compatible key routed through 9router keeps the passthrough property. Accept the structured-output downgrade to prompt-injected `json_object` on `openai-compatible-*` routes [25] and validate app-side.
4. **Do not** use `cx/*`, fusion combos, or 9router's `/v1/messages` and `/v1/responses` surfaces for our agent loop.

**Implementation guardrails for #32, regardless of route:**

- Treat `finish_reason: "tool_calls"` plus a **JSON-parse of every `arguments` string** as a validation gate; on parse failure, retry once rather than trusting the payload. The parallel-call collapse produces syntactically invalid JSON, so this catches it.
- Do not depend on `tool_choice` or `parallel_tool_calls` being honoured; design the loop to work with `auto` and to tolerate one call per turn.
- Do not depend on `response_format`. Keep Pydantic validation + one repair retry as #18 already recommended — that conclusion survives and is now load-bearing rather than precautionary.
- Treat a stream that ends without `finish_reason`/`[DONE]` as a cancelled/failed turn and discard partial tool arguments.
- Subtract `BUFFER_TOKENS` (2000) from streamed `prompt_tokens`, and skip usage marked `estimated: true`, before feeding the #25 budget.
- Pin one concrete model ID; never a combo name.

---

## Reproducing the probes

Both probes execute 9router v0.5.50's real translator functions — no mocks of the code under test.

```bash
git clone --depth 1 https://github.com/decolua/9router.git   # v0.5.50 == npm dist-tags.latest [49]
# stub two unrelated deps pulled in by the translator barrel (uuid, undici)
```

- **Probe 1** imports `openaiResponsesToOpenAIResponse` from `open-sse/translator/response/openai-responses.js`, feeds it Responses-API event sequences for two parallel function calls under three orderings, and accumulates the emitted chunks the way an OpenAI client does (by `delta.tool_calls[].index`). Output is the table in [§The parallel tool-call collapse](#the-parallel-tool-call-collapse), plus the usage object quoted in [§Token usage reporting](#token-usage-reporting).
- **Probe 2** imports `openaiToOpenAIResponsesRequest` from `open-sse/translator/request/openai-responses.js`, passes a representative agent request, then applies the codex executor's deletion list and `RESPONSES_API_ALLOWLIST` verbatim. Output is the final upstream body quoted in [§Tool calling: request direction](#tool-calling-request-direction).

---

## Sources

All primary. 9router source read from a shallow clone of `decolua/9router` at **v0.5.50** (`package.json` version confirmed); paths are repo-relative. Accessed **2026-08-12**.

1. `open-sse/providers/registry/codex.js` — codex transport (`chatgpt.com/backend-api/codex/responses`, `format: "openai-responses"`, `forceStream: true`), Codex-CLI headers/OAuth client id, and the current `cx/` model list
2. `open-sse/handlers/chatCore/sseToJsonHandler.js` — `handleForcedSSEToJson`: Responses-SSE→JSON branch, `function_call`→`tool_calls` mapping, cache-token folding; and the chat-SSE delta accumulator
3. `open-sse/providers/registry/openai.js` — `transport.baseUrl = https://api.openai.com/v1/chat/completions`, `forceStream: true`, no `format` override
4. `open-sse/translator/index.js` — `needsTranslation(sourceFormat, targetFormat) { return sourceFormat !== targetFormat; }`; and `translateRequest`, whose format conversion is gated on `if (sourceFormat !== targetFormat)` ("If same format, skip translation steps") while `ensureToolCallIds` / `fixMissingToolResponses` run unconditionally
5. `open-sse/handlers/chatCore/streamingHandler.js` — `buildTransformStream`, passthrough vs translation selection, `CODEX_SOURCE_TO_TARGET`
6. `gitbook/content/en/**` — grep for "tool call", "function call", "tool_calls", "structured output", "json mode", "json_schema": **no matches**
7. `gitbook/content/en/features/combos.md`, `gitbook/content/en/providers/free.md` — docs still recommending `cx/gpt-5.2-codex`
8. `gitbook/content/en/integration/other-tools.md`, `.../continue.md` — docs recommending `cx/deepseek-chat` (wrong provider prefix)
9. `open-sse/translator/request/openai-responses.js` — `openaiToOpenAIResponsesRequest`: forced `stream:true`/`store:false`, pass-through field list, tool conversion, `clampCallId`, `normalizeToolParameters`, single-`instructions` behavior
10. `open-sse/executors/codex.js` — `RESPONSES_API_ALLOWLIST`, `normalizeCodexTools`, the `delete body.*` block, `delete body.stream_options`
11. Repo-wide grep for a writer of the Responses `text.format` / `json_schema` field in `open-sse/`: **no matches**
12. `openai/codex` — `codex-rs/model-provider-info/src/lib.rs` (`CHATGPT_CODEX_BASE_URL`, auth-mode base-URL selection), `codex-rs/codex-api/src/common.rs` (`ResponsesApiRequest` has no sampling fields), OAuth client id
13. `open-sse/translator/concerns/toolCall.js` — `ensureToolCallIds`, `generateToolCallId`, `fixMissingToolResponses`, `hasToolResults`
14. `open-sse/translator/response/openai-responses.js` — `openaiResponsesToOpenAIResponse` (scalar `toolCallIndex`/`currentToolCallId`, argument-delta emission, `computeFinishReason`, usage extraction from `response.completed`)
15. Grep for `data.output_index` / `chunk.output_index` in `open-sse/`: **no matches**
16. `open-sse/transformer/streamToJsonConverter.js` — `convertResponsesStreamToJson`: `state.items.set(parsed.output_index ?? 0, parsed.item)`, usage accumulation without `input_tokens_details`
17. `open-sse/utils/streamHandler.js` — `pipeWithDisconnect`, stall watchdog rearm-on-chunk
18. `open-sse/utils/stream.js` — `flush()` emitting `[DONE]` + `onStreamComplete`; buffered-vs-original usage split
19. `open-sse/executors/grok-cli.js` — `delete body.stream_options`, `tool_choice` normalization/removal
20. `open-sse/executors/iflow.js` — injects `stream_options: { include_usage: true }` to obtain usage
21. `open-sse/utils/streamHandler.js` — `createStreamController.handleDisconnect` (500 ms delayed abort), `createDisconnectAwareStream` (`emitTerminal` gated on `onAbortTerminal`)
22. `open-sse/handlers/chatCore/streamingHandler.js` — `isResponsesPassthrough` gating of `buildAbortedResponsesTerminalBytes`; `"[Streaming in progress...]"` placeholder row
23. `open-sse/handlers/chatCore.js` — `createErrorResult(499, "Request aborted")`
24. `open-sse/translator/request/openai-to-claude.js` — `response_format` → system-prompt injection; tool-name prefixing + `_toolNameMap`; Claude Code system prompt
25. `open-sse/executors/default.js` — `applyJsonSchemaFallback` (gated on `openai-compatible-` prefix; rewrites to `json_object`)
26. `open-sse/translator/concerns/paramSupport.js` — `STRIP_RULES` (Claude `temperature`, Copilot rules, output clamping)
27. `open-sse/providers/capabilities.js` — capability flags derived from models.dev (`tool_call` → `tools`); no structured-output flag
28. `open-sse/services/combo.js` — `detectRequiredCapabilities` (modalities only; never `tools`)
29. https://github.com/decolua/9router/issues — #2896 "Codex route breaks Chat Completions json_schema and non-streaming response reconstruction"; #1343 "[Bug] json_schema response_format rejected with 400 Invalid JSON body"; #2003 (Gemini structured outputs); #1592 (forced `tool_choice` 400 on `cc/`); #302 (`stream=False` drops `tool_calls`)
30. `open-sse/utils/usageTracking.js` — `BUFFER_TOKENS = 2000`, `addBufferToUsage`
31. `open-sse/utils/usageTracking.js` — `estimateInputTokens` (`length/4`), `estimateOutputTokens`, `formatUsage` (applies buffer, sets `estimated: true`), `filterUsageForFormat`
32. `open-sse/translator/concerns/usage.js` — `buildUsage`, `prompt_tokens_details.cached_tokens`, per-provider extractors
33. `next.config.mjs` — `proxyClientMaxBodySize` default `"128mb"`, env `NINEROUTER_PROXY_CLIENT_MAX_BODY_SIZE`
34. `open-sse/config/runtimeConfig.js` — `STREAM_STALL_TIMEOUT_MS` 360 s, `STREAM_FIRST_CHUNK_TIMEOUT_MS` 200 s, `FETCH_CONNECT_TIMEOUT_MS` 60 s, `DEFAULT_MAX_TOKENS` 64000
35. `src/app/api/v1/chat/completions/route.js` + `src/sse/handlers/chat.js` — no rate limiting; grep for `maxConcurrent`/`semaphore`/`p-limit`/`concurrencyLimit` in `open-sse/` and `src/`: **no matches**
36. https://github.com/decolua/9router/issues/3164 — "Responses swapped between concurrent requests to the same model" (open, filed 2026-08-08 against v0.5.50; keep-alive multiplexing dependency)
37. `open-sse/services/combo.js` (`const { tools, tool_choice, ...rest } = body;`) and `src/sse/handlers/chat.js` (fusion panel `cleanBody`) — fusion strips tools
38. https://developers.openai.com/api/docs/deprecations — "2026-04-22: Legacy GPT model snapshots (July 2026 shutdown)": `gpt-5-codex`, `gpt-5.1-codex`, `gpt-5.1-codex-max`, `gpt-5.2-codex` shut down 2026-07-23 → `gpt-5.6-sol`; definition of "shut down"
39. https://developers.openai.com/api/docs/models/gpt-5.2-codex — supported features (streaming, structured outputs, function calling); endpoints: `v1/responses` only
40. https://developers.openai.com/api/docs/models/gpt-5.1-codex-max — "streaming, structured_outputs, function_calling, image_input, web_search, prompt_caching"; `v1/responses` only
41. https://developers.openai.com/api/docs/models/gpt-5.1-codex — same capability set; `v1/responses` only
42. `openai/codex` — `codex-rs/model-provider-info/src/lib.rs`: `enum WireApi { Responses }`; `wire_api = "chat"` deserialization error
43. https://github.com/openai/codex/discussions/7782 — "Deprecating `chat/completions` support in Codex"; proxy/gateway warning
44. `src/shared/constants/providersDisplay.js` — `RISK_NOTICE` text; `open-sse/providers/registry/codex.js` — `deprecated: true, deprecationNotice: "RISK_NOTICE"`
45. `open-sse/handlers/responsesHandler.js` — `sourceFormatOverride: "openai-responses"`
46. `CHANGELOG.md` (v0.5.50) — "Translator: drop JSON Schema keywords Gemini rejects (`uniqueItems`, `contains`, `multipleOf`, `unevaluatedProperties`, `unevaluatedItems`, `contentSchema`)"
47. https://developers.openai.com/api/docs/changelog — `gpt-5.6-sol` / `-terra` / `-luna` released 2026-07-09; "The `gpt-5.6` alias routes requests to `gpt-5.6-sol`"
48. `open-sse/providers/schema.js` — transport-config default `format: "openai"` (providers override only what differs)
49. https://registry.npmjs.org/9router — `dist-tags.latest = 0.5.50`, modified 2026-08-05, 214 versions; matches the cloned `package.json`, confirming the read source is the current release

**OpenAI Chat Completions contract** (official spec, reference, guides, and shipped SDK source). `platform.openai.com/docs/*` returns HTTP 403 behind a Cloudflare bot challenge; OpenAI serves the same official docs from `developers.openai.com`, which its own `llms.txt` designates as the Markdown source. Accessed 2026-08-12.

50. https://raw.githubusercontent.com/openai/openai-openapi/master/openapi.yaml — OpenAPI 3.1.0, `info.version: 2.3.0`: `ChatCompletionToolChoiceOption` (values + nested named-function form + defaults), `ParallelToolCalls` (`default: true`), `FunctionObject` (`strict` default `false`), `ChatCompletionMessageToolCall` (`arguments` is a string; validation warning), `finish_reason` enum, `ChatCompletionRequestToolMessage`, `ChatCompletionStreamOptions.include_usage`, `CompletionUsage`, `response_format` union; and the absence of any chat-completions cancel endpoint
51. https://developers.openai.com/api/docs/guides/function-calling.md — "You can prevent this by setting `parallel_tool_calls` to `false`, which ensures exactly zero or one tool is called"; tool definitions count against context and are billed as input tokens
52. https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events.md — `CreateChatCompletionStreamResponse` / `ChatCompletionMessageToolCallChunk`: `index` required, `id` / `type` / `function.name` / `function.arguments` optional per fragment
53. https://raw.githubusercontent.com/openai/openai-node/master/src/lib/ChatCompletionStream.ts — `choice.message.tool_calls[index] ??= {}` and `tool_call.function!.arguments += fn.arguments`
54. https://raw.githubusercontent.com/openai/openai-python/main/src/openai/lib/streaming/_deltas.py — string deltas accumulated, `index`/`type` assigned not accumulated, `RuntimeError` if a list delta entry lacks `index`
55. https://developers.openai.com/api/docs/guides/structured-outputs.md — `strict: true` schema subset: all fields required, `additionalProperties: false`, object root, unsupported composition keywords, size limits; `refusal` semantics; JSON-mode limitations
56. https://developers.openai.com/api/reference/resources/chat.md — Chat Completions parameter reference (`tool_choice`, `stream_options`, `response_format` prose); no documented server-side abort/billing semantics
57. https://raw.githubusercontent.com/openai/openai-node/master/src/lib/ChatCompletionStream.ts and `src/lib/EventStream.ts` — "stopping iteration early aborts the underlying request"; `abort()`
58. https://raw.githubusercontent.com/openai/openai-python/main/helpers.md and `src/openai/_streaming.py` — `.stream()` requires a context manager; `close()` releases the connection
59. `open-sse/translator/formats/openai.js` — inbound `tool_choice` normalization producing the nested `{type:"function", function:{name}}` Chat Completions form

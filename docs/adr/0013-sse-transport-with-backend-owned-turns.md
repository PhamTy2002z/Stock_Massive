# Every Turn is POST admission plus same-origin SSE, and the Turn belongs to the backend

Alpha Desk uses a **two-request transport**: a `POST` admits and creates the Turn,
then a `GET` subscribes to its events as a native same-origin `EventSource` through a
Next.js Route Handler. Fast and tool-heavy Turns use the same contract.

```
POST /api/alpha-desk/threads/{threadId}/turns
GET  /api/alpha-desk/turns/{turnId}/events
POST /api/alpha-desk/turns/{turnId}/cancel
```

The load-bearing rule is that **an admitted Turn belongs to the backend, not to a
connection**. Reloading, navigating away, closing the tab, or losing the network
closes only that subscriber; the Turn runs until it reaches a terminal state or
receives an explicit cancel.

## Why not the app's existing job-polling pattern

Polling is the established precedent for jobs (`JobProgressBar`,
`use-jobs-status.ts`) and it is the right pattern for a job whose only interesting
output is a completion. A Turn is different in kind: its value arrives
*incrementally*, over up to eight tool rounds and a ten-minute deadline, and a poll
interval short enough to feel live is a poll interval that costs more than the stream
it imitates. Alpha Desk is the app's first and only v1 streaming consumer; every
existing page, hook, and route lifetime is unchanged.

WebSockets were not needed: the channel is one-directional after admission, and
cancel is an ordinary authenticated `POST`. SSE brings `Last-Event-ID` and browser
reconnection for free.

## Why two requests and not one streaming POST

Admission errors must be ordinary HTTP responses, decided *before* a stream opens —
`429` for an exhausted user allowance, `503` for exhausted service budget or all
three execution slots occupied, with the stable reason from ADR-0014. Folding
admission into the stream turns a refusal into an in-band event the client has to
parse, and it makes the idempotency key arrive at the same moment as the work.

The browser generates a UUID `turnId` before the `POST`, and the backend treats it as
an idempotency key scoped to its owner: resubmitting the same id and payload returns
the existing Turn, while reusing the id with a different payload returns `409`. That
is what makes a retried admission safe on a flaky network.

## `content.block`, not `content.delta`

The backend buffers provider deltas into complete, Markdown-safe presentation units —
a paragraph, a related bullet group, a complete table, a closed code fence — and
emits one event per block. **There is no typewriter animation and no
character-by-character rendering.**

Two reasons. A half-streamed Markdown table or an unclosed fence is unreadable, so
character-level delivery buys the *appearance* of speed at the cost of legibility.
And under ADR-0015 a content block is not releasable until its grounding is proven
against the same Turn's traces; a block is the smallest unit that can be validated,
so it is also the smallest unit that can honestly be shown. A live block gets a light
150–200 ms reveal with no artificial delay; a reconnect snapshot renders everything
already present at once and never replays the staged reveal.

`turn.activity` exposes only a generic phase — *Searching…*, *Reading data…*,
*Analyzing…*, *Preparing visual…*. It never emits a tool name, symbol, arguments, raw
result, prompt, or reasoning; the full detail stays in the **Tool Call Trace**. The
activity line is ephemeral rather than a verbose tool history.

V1 event types: `turn.snapshot`, `turn.activity`, `content.block`, `widget.ready`,
`turn.completed`, `turn.incomplete`, `turn.failed`, `turn.cancelled`. Every event
carries a versioned envelope with a monotonic per-Turn `seq`, which is also the SSE
`id`. A 15-second SSE comment heartbeat keeps an otherwise quiet path observable
without consuming a sequence.

## Replay is snapshot-based, not a durable delta log

A snapshot carries the checkpointed assistant blocks, validated Widgets, the current
generic activity, Turn status, terminal reason, and `throughSeq`; the subscriber then
receives only events with `seq > throughSeq`. Subscriber registration and snapshot
capture are atomic with respect to the publisher, so there is no window in which an
event is neither in the snapshot nor in the stream.

A durable log of token deltas would have to be retained, ordered, and trimmed for a
replay nobody wants to watch a second time. What a reconnecting reader wants is the
current state of the answer, which is what a snapshot is. A duplicate sequence is
ignored; a gap forces a reconnect and full replacement from a fresh snapshot. A fast
Turn that finishes before `EventSource` connects is returned complete as a terminal
snapshot.

Each subscriber has a bounded queue. A slow tab cannot apply backpressure to the
agent loop — only that connection is dropped, and it recovers from a snapshot. No
canonical content is discarded.

## The Next Route Handler is an authenticated BFF, not the authorization boundary

Next owns cookies; FastAPI stays bearer-only. Each handler validates Origin on
state-changing requests, reads the httpOnly access and refresh cookies, obtains a
valid access token **before** returning the streaming response, forwards
`Authorization: Bearer …`, and passes through an API-shaped status rather than
redirecting to HTML. `/api/alpha-desk/*` is therefore excluded from the middleware
login redirect and authenticates inside each handler.

On an upstream `401`, Next performs one refresh under a process-local single-flight so
simultaneous tabs do not race the rotating refresh token, then retries the subscribe
exactly once. Token expiry after a stream has opened does not terminate it; the next
connection authenticates again.

**FastAPI independently verifies the active user and ownership of the Thread and Turn**
on create, subscribe, snapshot, and cancel. This keeps `fetchApi` unchanged for the
rest of the app, which is deliberate: retro-fitting auth onto roughly twenty-five
existing hooks is its own effort.

## Considered Options

- **Job polling, reusing the existing pattern.** Rejected above.
- **WebSockets.** Rejected: bidirectionality buys nothing here and costs a second
  connection model, a second auth path, and proxy configuration that SSE gets from
  ordinary HTTP.
- **Streaming `content.delta` tokens.** Rejected above on legibility and on the
  grounding boundary.
- **Holding the Turn on the connection.** Rejected: it makes a reload a
  cancellation, which is the behaviour users read as the system losing their work.

## Consequences

- The persistence model gains an **`agent_turn`** table. A durable lifecycle plus a
  checkpointed draft cannot live in `agent_message`, which is the canonical
  immutable transcript, nor in `agent_tool_call`, which is anchored to a single
  tool call. Draft content is checkpointed at most once per second and at activity,
  Widget, cancellation, and terminal boundaries — never once per token — and one
  terminal transaction freezes the draft into the canonical assistant message.
- The create transaction commits the user message and `agent_turn` **before**
  execution starts, and FastAPI then holds an `asyncio.Task` in a process-local Turn
  registry. A crash between commit and task start is recoverable as an incomplete
  Turn rather than an invisible or duplicated request. On startup, any Turn left
  active by a crash or deploy is frozen from its last checkpoint and marked
  `incomplete`; **v1 never resumes model or tool execution after a restart.**
- Cancel is authenticated and idempotent, changes the client state to *Cancelling…*
  immediately, and dispatches no new call. A read-only call already in flight is
  allowed to finish as ADR-0008 requires; its trace is retained but its result is
  not fed into another round. Retry creates a **new** Turn carrying
  `retry_of_turn_id`; the previous Turn, its spend, message, and traces stay
  immutable. A network reconnection is not a retry.
- Four terminal meanings, and the UI never replaces useful content with a
  full-screen error: `completed`, `incomplete` (useful content exists but budget,
  the wall-clock deadline, shutdown, or a later failure stopped the Turn), `failed`
  (no useful answer), `cancelled`.
- Timings: a hard **10-minute** Turn deadline, **120 seconds** per LLM call, a
  shorter per-tool timeout, and **30 seconds** of graceful shutdown for active Turns
  to reach a safe checkpoint — the container stop grace must exceed that interval.
- The live Turn uses a dedicated reducer, not per-block writes into TanStack Query,
  which continues to own canonical Threads, messages, and every other resource. At a
  terminal event the client refetches the Thread and replaces the draft projection
  with the canonical message.
- Subscription and reconnection have their own per-user and per-Turn limiter and are
  **not** charged as a Turn start; they must not pass through the current IP-based
  heavy limiter as if Next's IP represented the user.
- Deployment: the handler forwards the upstream body without buffering, sets
  `Content-Type: text/event-stream`, `Cache-Control: no-store, no-transform`, and
  `X-Accel-Buffering: no`, and must not synthesize `Content-Length`. Every
  intermediary must stream for longer than the 10-minute deadline plus margin.
  `docker-compose.prod.yml` has no outer proxy configuration and does not give the
  web container an internal API URL — the build must add that internal route rather
  than silently falling back to the public build-time URL.

  **Chosen at A6 and recorded in `docs/streaming-topology.md`**: `browser → Caddy →
  Next → FastAPI`, the outer proxy opt-in under a compose profile, the web container
  reaching FastAPI over `INTERNAL_API_URL`. Two consequences the paragraph above did
  not name, both found by the acceptance below. Uvicorn drains open connections
  *before* the ASGI lifespan shuts down, and an SSE subscriber's connection is open
  for the length of the Turn — so the drain has to be bounded or the 30-second
  checkpoint window never begins. And `request.nextUrl.origin` is the address Next is
  bound to rather than the one the browser asked for, so the handler's cross-origin
  check reads `X-Forwarded-Host`/`Host`; checking against `nextUrl` refuses every
  Alpha Desk write the moment a proxy is put in front.
- **Streaming is accepted only against an end-to-end test through the real browser →
  Next → FastAPI path**: first block and a 15-second heartbeat arrive before
  completion, a reconnect begins with an ordered snapshot and duplicates nothing, a
  slow subscriber cannot slow the Turn, and the terminal refetch yields the canonical
  message. Any future CDN or reverse proxy passes the same test. It lives in
  `apps/web/e2e/streaming.spec.ts` and runs with `pnpm test:e2e`.

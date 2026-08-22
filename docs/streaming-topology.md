# The streaming deployment, and the test any topology has to pass

ADR-0013 states the requirement and leaves the topology open; spec 0003 §14.4 records
that gap and blocks A6 on closing it. This is the answer: what the deployment looks like,
what every hop owes an event stream, and how to prove a new hop still honours it.

## The path

```
browser ──HTTPS──▶ proxy (Caddy) ──HTTP──▶ web (Next) ──HTTP──▶ api (FastAPI)
                                            └── internal network, INTERNAL_API_URL
```

- **The browser talks only to the Next app.** `/api/alpha-desk/*` is a Route Handler that
  authenticates with the session cookie and forwards a bearer token; FastAPI independently
  verifies the user and the ownership of the Thread and the Turn (ADR-0013).
- **Next reaches FastAPI over the internal network**, through `INTERNAL_API_URL`. Without
  it the build falls back to the public `NEXT_PUBLIC_API_URL` and hairpins out through the
  internet to reach the container next door.
- **The API is also published**, because everything outside Alpha Desk calls it directly
  from the browser. Alpha Desk itself never takes that route.
- **The outer proxy is opt-in**, the way the self-hosted database is:
  `docker compose -f docker-compose.prod.yml --profile proxy up -d`. A deployment that
  terminates TLS at a load balancer it already owns runs without it and owes the same
  contract in its own configuration.

## The event contract

Envelope, unchanged in shape and at `version: 2` since ADR-0026 replaced the harness:
`{version, seq, type, turn_id, data}`. Framing is `id: {seq}` + `event: {type}` +
`data: {json}`; the heartbeat is an SSE comment and consumes no `seq`; `Last-Event-ID`
is answered with a snapshot that restates rather than a filtered replay.

| `type` | `data` |
| --- | --- |
| `turn.snapshot` | `through_seq`, `status`, `terminal_reason`, `text`, `tool_calls[]`, `message_id` |
| `content.delta` | `text` — appended to what the stream has sent so far |
| `tool.call` | `id`, `name`, `status` (`running` \| `ok` \| `error`), `summary` |
| `turn.completed` · `turn.incomplete` · `turn.failed` · `turn.cancelled` | `status`, `terminal_reason`, `message_id` |

The old contract's `content.block`, `widget.ready` and five-phase `turn.activity` are
gone, along with the citation, widget and manifest payloads they carried. A canonical
message stores `{text, tool_calls}`.

## What every hop owes an event stream

1. **Do not buffer.** Forward each write as it arrives. Caddy does not buffer a proxied
   body by default and `flush_interval -1` says so out loud; nginx buffers unless
   `proxy_buffering off` is set, and a buffered event stream is one delivery at the end of
   the Turn.
2. **Do not compress with buffering.** The Alpha Desk stream route is excluded from
   `encode` — a compressor filling its window holds the stream until the Turn ends, and
   the win on a few hundred bytes per frame is not worth the class of bug.
3. **Do not synthesize `Content-Length`.** A stream has no length to declare, and a
   declared one makes every hop wait for exactly that many bytes.
4. **Stay open longer than the deadline plus margin.** A Turn may run for the full
   ten-minute deadline, so read and write timeouts on the stream route are disabled
   (`read_timeout 0`, `write_timeout 0`).
5. **Preserve the request's host.** The Route Handler refuses a cross-origin write by
   comparing `Origin` against `X-Forwarded-Host`/`Host` — see the trap below.

## The shutdown arithmetic

Three numbers, in three files, and they have to line up. `apps/api/tests/test_deployment_topology.py`
asserts the arithmetic so it cannot drift silently.

| Window | Where | Value |
| --- | --- | --- |
| Turn checkpointing | `GRACEFUL_SHUTDOWN_SECONDS`, `src/agent/turns.py` | 30s |
| Connection drain | `--timeout-graceful-shutdown`, `apps/api/Dockerfile.prod` | 10s |
| Container stop grace | `stop_grace_period`, `docker-compose.prod.yml` | api 60s, web 30s, proxy 45s |

They run **in sequence, not in parallel**: uvicorn stops accepting, waits out the
connection drain, cancels what is left, and only then does the ASGI lifespan shut down —
which is where Alpha Desk spends its thirty seconds getting active Turns to a checkpoint.

The connection drain is the part that is easy to miss. An SSE subscriber holds its
connection for as long as the Turn runs, so with no timeout uvicorn would wait for the
ten-minute deadline before the lifespan began, and the deploy would have killed the
container long before any checkpoint was written. A Turn interrupted this way comes back
as `incomplete` with the content it had reached — never as a Turn that lost its answer,
and never as one left `running` forever (the startup sweep freezes those).

The API's grace is the longest because it is the only hop with work to finish: the two
windows above happen inside it. The proxy's is longer than the web container's because it
holds the outermost connection — cutting that first would end a stream whose inner hop was
still being given time to finish it.

## The trap this path already fell into

`request.nextUrl.origin` is built from the address the Next process is **bound to**, not
from the request. Behind a proxy — or in the standalone server, which binds `0.0.0.0` — it
reads `http://0.0.0.0:3000` for a browser that asked for `https://app.example.com`, so an
`Origin` check against it refuses **every Alpha Desk write** the moment a proxy is put in
front. The handler therefore compares `Origin` against `X-Forwarded-Host`/`Host`, or
against `APP_ORIGIN` when the operator names it explicitly.

Neither header is attacker-controlled for this app: a cross-site write still carries this
app's host, because that is where it was sent, and its `Origin` says otherwise.

Set `APP_ORIGIN` in production when you want the check pinned to a list rather than
derived from headers.

This was invisible to unit tests on either side of the proxy, and the end-to-end
acceptance found it on its first run. That is the argument for the acceptance existing.

## Running the acceptance

```
cd apps/web && pnpm test:e2e
```

Playwright starts both servers and tears them down:

- **FastAPI**: `apps/api/tests/e2e/server.py` — the production app, with the model
  replaced by a Turn the test drives through `/e2e` control endpoints. Those endpoints are
  defined in a file under `tests/`, so no production process can serve them.
- **Next**: a real production build, assembled the way `Dockerfile.prod` assembles it
  (`next build`, then the standalone server with `.next/static` and `public/` copied
  beside it), bound to `0.0.0.0` and pointed at FastAPI over `INTERNAL_API_URL`.

Prerequisites: a migrated database reachable through `DATABASE_URL`
(`docker compose up -d db` and `alembic upgrade head`), and the Chromium build Playwright
installs with `pnpm exec playwright install chromium`.

The four properties, all through the real browser → Next → FastAPI path:

1. **The first `content.delta` and a 15-second heartbeat arrive before completion.** A
   harness that buffers looks identical to one that is hung, and this is the assertion
   that tells them apart. The heartbeat is an SSE comment, so `EventSource` discards it by
   design — the test reads the stream as raw bytes through the same proxy to see one.
2. **A reconnect begins with an ordered snapshot and duplicates nothing.** The page is
   reloaded mid-Turn; the transcript is the same transcript, in the same order, and the
   next delta lands on the reattached subscriber.
3. **A slow subscriber cannot slow the Turn.** A second subscriber opens the stream and
   never reads it; its bounded queue fills and it is dropped without ever receiving the
   terminal event, while the Turn reaches its terminal state and the canonical message
   replaces the draft.
4. **The terminal refetch yields the canonical message.** The draft is replaced, not
   appended to — one copy of the answer text, and the tool-call list the canonical message
   stores rather than the running one the stream carried.

**Any future CDN or reverse proxy passes this same file.** Point `E2E_WEB_PORT` at the
new hop, or run the suite against a staging deployment by pointing the config's `baseURL`
at it, and the four properties are the acceptance criteria for the change.

import { NextResponse, type NextRequest } from "next/server"

import { currentAccessToken, rotateAccessToken } from "@/lib/auth/bearer"

/**
 * The browser's way into the authenticated half of the API.
 *
 * Tokens live in httpOnly cookies precisely so client JavaScript cannot read
 * them, which means client code cannot call FastAPI directly either. Next owns
 * the cookie and forwards a bearer token; **FastAPI still verifies the user and
 * the ownership of everything it serves**, so this handler is a transport, not
 * an authorization boundary.
 *
 * The prefix list is the one piece of policy here. Without it, a signed-in
 * user's token would reach any path they could type — including the operational
 * routes behind the admin check — through a same-origin URL that carries their
 * cookies automatically. An allowlist of the Alpha Desk resources is cheaper to
 * keep honest than an audit of everything mounted upstream.
 *
 * A 401 from upstream is answered by rotating the access token once and
 * retrying. Rotation is reactive rather than pre-emptive because the upstream is
 * the only authority on whether a token is still good, and it goes through a
 * process-local single flight so simultaneous tabs do not race the rotating
 * refresh token.
 *
 * ## Two bodies, and only one of them may be read
 *
 * `watchlist` and `analyses` answer with JSON, and reading it here is what lets
 * the handler retry after a refresh. **A Turn's event stream cannot be read to
 * the end before it is returned** — the end is up to ten minutes away, and the
 * whole point is that the first block arrives long before it. So the upstream
 * `Content-Type` decides: an event stream is handed on unbuffered, with no
 * `Content-Length` synthesised and nothing between the two sockets.
 *
 * A stream is a `GET`, so it carries no request body to replay; that is why the
 * one refresh retry is still safe on this path.
 */

// The resources this proxy will carry, matched on the first path segment.
// `threads` and `turns` are the Alpha Desk transport (ADR-0013); the other two
// are the Watchlist rail and the Analyses behind it.
const FORWARDED_RESOURCES = new Set(["watchlist", "analyses", "threads", "turns"])

const EVENT_STREAM = "text/event-stream"

/**
 * What an event stream is answered with, and why each header is here.
 *
 * `no-transform` is the load-bearing half of the cache header: an intermediary
 * permitted to transform a body is permitted to buffer it, and a buffered event
 * stream is one that arrives all at once at the end. `X-Accel-Buffering` says
 * the same thing to nginx, which buffers proxied responses by default. No
 * `Content-Length` appears at all — a stream has no length to declare, and
 * declaring one would make every hop wait for exactly that many bytes.
 */
const STREAM_HEADERS = {
  "Content-Type": EVENT_STREAM,
  "Cache-Control": "no-store, no-transform",
  "X-Accel-Buffering": "no",
  Connection: "keep-alive",
} as const

const upstreamBase = () =>
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v1"

interface RouteContext {
  params: Promise<{ path: string[] }>
}

/**
 * Whether a state-changing request came from this app.
 *
 * The session cookie is `SameSite=Lax`, which stops a cross-site `POST` from
 * carrying it — but Lax is a browser default, not a guarantee this handler
 * makes, and one `<form>` posted from another origin is all it takes to find
 * out which browsers disagree. `Origin` is sent on every state-changing request
 * by every browser that implements the header, so an absent or foreign one on a
 * write is refused rather than trusted.
 */
function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin")
  if (!origin) return false
  try {
    return new URL(origin).origin === request.nextUrl.origin
  } catch {
    return false
  }
}

async function forward(request: NextRequest, path: string[]): Promise<NextResponse> {
  if (path.length === 0 || !FORWARDED_RESOURCES.has(path[0])) {
    return NextResponse.json({ detail: "Unknown Alpha Desk resource" }, { status: 404 })
  }

  if (request.method !== "GET" && !sameOrigin(request)) {
    return NextResponse.json({ detail: "Cross-origin request refused" }, { status: 403 })
  }

  const target = `${upstreamBase()}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`
  // Read once: a request body is a stream and cannot be replayed into the retry.
  const body = request.method === "GET" ? undefined : await request.text()

  // Awaited *before* anything is returned. A streaming response that went out
  // and only then discovered it had no token would have to report the failure
  // inside the stream, which is the shape ADR-0013 exists to avoid.
  let token = await currentAccessToken()
  let response = await send(request, target, token, body)

  if (response.status === 401) {
    // Exactly one refresh and exactly one retry. A loop here would turn one
    // dead credential into a run of identical exchanges against a token that
    // rotates on every one of them.
    await response.body?.cancel()
    token = (await rotateAccessToken()) ?? undefined
    if (!token) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 })
    }
    response = await send(request, target, token, body)
  }

  if (isEventStream(response)) return streamed(response)

  const payload = await response.text()
  return new NextResponse(payload || null, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
      // The rail polls, and a cached rail is a rail showing the previous session.
      "Cache-Control": "no-store",
    },
  })
}

function isEventStream(response: Response): boolean {
  return (
    response.body !== null &&
    (response.headers.get("Content-Type") ?? "").startsWith(EVENT_STREAM)
  )
}

/**
 * Hand the upstream body on without touching it.
 *
 * `response.body` is passed through as the `ReadableStream` it already is.
 * There is no `await response.text()` anywhere on this path, and that absence
 * *is* the feature: reading it would wait for the Turn to finish and then
 * deliver every event at once.
 */
function streamed(response: Response): NextResponse {
  return new NextResponse(response.body, {
    status: response.status,
    headers: { ...STREAM_HEADERS },
  })
}

function send(
  request: NextRequest,
  target: string,
  token: string | undefined,
  body: string | undefined,
): Promise<Response> {
  const lastEventId = request.headers.get("Last-Event-ID")
  return fetch(target, {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      // Carried through because it is the whole of a reconnect: the browser
      // sets it natively, and dropping it here would leave the backend unable
      // to say where this reader believes it got to.
      ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
    },
    body: body || undefined,
    cache: "no-store",
  })
}

export async function GET(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

export async function POST(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

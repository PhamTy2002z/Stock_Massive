import { NextResponse, type NextRequest } from "next/server"

import { currentAccessToken, rotateAccessToken } from "@/lib/auth/bearer"
import { UPSTREAM_UNREACHABLE } from "@/lib/connection-status"

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
 * ## Two directions, three body shapes, and the request side must be buffered
 *
 * Response side: `watchlist` and `analyses` answer with JSON, and reading it
 * here is what lets the handler retry after a refresh. **A Turn's event stream
 * cannot be read to the end before it is returned** — the end is up to ten
 * minutes away, and the whole point is that the first block arrives long
 * before it. So the upstream `Content-Type` decides: an event stream is handed
 * on unbuffered, with no `Content-Length` synthesised and nothing between the
 * two sockets. Everything that is neither JSON nor an event stream — `assets`'
 * favicon images, `attachments`' files — goes out unbuffered the same way,
 * carrying whatever `Content-Type`, `Cache-Control`, `Content-Disposition` and
 * `X-Content-Type-Options` the API set rather than the JSON defaults below.
 * `await response.text()` would decode that body as UTF-8, which is exactly
 * wrong for an image or a PDF — it would replace bytes the decoder cannot
 * represent and hand the browser a corrupted file.
 *
 * Request side: a stream response is a `GET`, so it carries no request body to
 * replay; that is why the one refresh retry is safe on that path without
 * reading anything first. A `POST` or `PATCH` is different — its body must be
 * read once up front (a stream cannot be replayed into the retry) and the
 * result buffered so the same bytes can be sent again. JSON is buffered as
 * text; anything else — a multipart upload's boundary included — is buffered
 * as an `ArrayBuffer`, because `await request.text()` UTF-8-decodes it and
 * would corrupt the boundary and any binary part inside it.
 */

// The resources this proxy will carry. Most are matched on the first segment;
// Market Monitor is the sole stocks subtree admitted because its browser reads
// require the same httpOnly-cookie-to-bearer bridge.
// `threads` and `turns` are the Alpha Desk transport (ADR-0013); `watchlist` and
// `analyses` are the rail and the Analyses behind it. `messages` is the flag
// action of ADR-0016 and nothing else: upstream mounts `POST` and `DELETE` on
// `/messages/{id}/flag` alone, and both resolve ownership through the Thread, so
// the same argument covers it. `assets` is the favicon fetch-and-cache: the
// browser must never reach a search result's domain directly to load its
// icon — that would tell the domain, and the network path to it, which page a
// signed-in user is reading and from what IP — so the API fetches it and this
// allowlist is what lets the browser reach that endpoint at all. `artifacts` is
// the desk view fetch: upstream mounts a single `GET /artifacts/{id}` that resolves
// ownership through the Thread the Study ran in, so the same argument as
// `messages` covers it. `attachments` is the composer's file and image upload:
// upstream mounts `POST /attachments` and `GET /attachments/{id}`, and both
// resolve ownership the same way `read_artifact` does — through the account
// that stored the row, not through anything the request itself asserts — so a
// wider proxy grant here still cannot reach another account's upload.
// `usage` is this account's own allowance: upstream mounts
// a single `GET /usage` that takes no parameters and reads the user id from the
// resolved session, so there is no shape of the request that reaches another
// account's ledger. `capabilities` is the route's deployment facts (vision on or
// off): upstream mounts a single `GET /capabilities` behind the session that
// takes no parameters and answers the same for every caller, so nothing
// account-specific is reachable through it.
const FORWARDED_RESOURCES = new Set([
  "watchlist",
  "analyses",
  "threads",
  "turns",
  "messages",
  "artifacts",
  "attachments",
  "assets",
  "usage",
  "capabilities",
])

function isForwardedPath(path: string[]): boolean {
  return (
    (path.length > 0 && FORWARDED_RESOURCES.has(path[0])) ||
    (path[0] === "stocks" && path[1] === "market-monitor")
  )
}

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
 * The origins this deployment answers on, as the operator names them.
 *
 * Comma-separated, and empty in development, where the address the browser used
 * is derived below instead.
 */
const configuredOrigins = (): string[] =>
  (process.env.APP_ORIGIN ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean)

/**
 * The address the browser actually asked for, as this process can see it.
 *
 * **Not `nextUrl.origin`.** Next builds that from the address the server is
 * bound to, not from the request: a Next process listening on `0.0.0.0:3000`
 * behind a reverse proxy reports `http://localhost:3000` for a request the
 * browser made to `https://app.example.com`, so an `Origin` check against it
 * refuses every write the moment a proxy is put in front — which is precisely
 * the deployment ADR-0013 asks for. That failure is invisible to a unit test on
 * either side of the proxy and is why the end-to-end acceptance exists.
 *
 * `X-Forwarded-Host` and `Host` are safe to compare an `Origin` against because
 * neither is attacker-controlled *for this app*: a cross-site request from
 * `evil.example` still carries this app's host — that is where it was sent —
 * while its `Origin` says `evil.example`, so the two disagree and the request
 * is refused. A forged `Host` reaches an app that answers for that host and
 * proves nothing about the session cookie.
 */
function requestedOrigin(request: NextRequest): string | null {
  const host = (request.headers.get("x-forwarded-host") ?? request.headers.get("host"))
    ?.split(",")[0]
    ?.trim()
  // No host header at all is not a browser. Falling back to the bound address
  // keeps the check meaningful for anything speaking to this process directly.
  if (!host) return request.nextUrl.origin
  const proto =
    request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ??
    request.nextUrl.protocol.replace(":", "")
  return `${proto}://${host}`
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
  const header = request.headers.get("origin")
  if (!header) return false
  let origin: string
  try {
    origin = new URL(header).origin
  } catch {
    return false
  }

  const allowed = configuredOrigins()
  if (allowed.length > 0) return allowed.includes(origin)

  return origin === requestedOrigin(request)
}

async function forward(request: NextRequest, path: string[]): Promise<NextResponse> {
  if (!isForwardedPath(path)) {
    return NextResponse.json({ detail: "Unknown Alpha Desk resource" }, { status: 404 })
  }

  if (request.method !== "GET" && !sameOrigin(request)) {
    return NextResponse.json({ detail: "Cross-origin request refused" }, { status: 403 })
  }

  const target = `${upstreamBase()}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`
  const requestContentType = request.headers.get("Content-Type")
  // Absent means the browser's own JSON-by-default caller (`lib/alpha.ts`), not
  // a body that happens to look like JSON — this is a Content-Type check, not
  // a body sniff, matching the response-side predicate below.
  const isJsonRequest = requestContentType === null || requestContentType.startsWith("application/json")

  // Read once: a request body is a stream and cannot be replayed into the
  // retry below. That read must also *buffer* the body rather than merely
  // consume it, because the buffer — not the original stream — is what a
  // second `fetch` call can be given. `text()` already did that for the JSON
  // path; a non-JSON body (a multipart upload's boundary, an image's bytes)
  // gets the same treatment via `arrayBuffer()` rather than `text()`, which
  // would UTF-8-decode it and corrupt exactly the bytes a boundary or an image
  // depends on. The alternative — read nothing and let a 401 racing an upload
  // fail outright — would turn one token rotation into a corrupted or dropped
  // attachment; buffering costs one upload's bytes in memory for the length of
  // one request and turns that failure into an ordinary, retryable one.
  const body: BodyInit | undefined =
    request.method === "GET" ? undefined : isJsonRequest ? await request.text() : await request.arrayBuffer()

  // Awaited *before* anything is returned. A streaming response that went out
  // and only then discovered it had no token would have to report the failure
  // inside the stream, which is the shape ADR-0013 exists to avoid.
  let token = await currentAccessToken()
  let response = await send(request, target, token, body, requestContentType)

  if (response.status === 401) {
    // Exactly one refresh and exactly one retry. A loop here would turn one
    // dead credential into a run of identical exchanges against a token that
    // rotates on every one of them.
    //
    // The refused body is **read** and thrown away rather than cancelled.
    // `body.cancel()` never settles under the fetch this runtime installs, and
    // an await that never returns here is the worst possible place for one: the
    // rotation below never runs, so the request the browser is waiting on hangs
    // instead of being retried with a fresh token — which is every request on
    // this path from the moment an access token expires. Reading it is what the
    // success path does with the same body a few lines down, so it is the shape
    // already proven against this runtime, and a refusal's body is one short
    // sentence of JSON.
    await response.text().catch(() => "")
    token = (await rotateAccessToken()) ?? undefined
    if (!token) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 })
    }
    response = await send(request, target, token, body, requestContentType)
  }

  if (isEventStream(response)) return streamed(response)
  if (!isJsonResponse(response)) return passthrough(response)

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
 * Whether the upstream answered with the JSON this handler already knows how
 * to buffer and retry-through.
 *
 * A whitelist, deliberately: this predicate decides who takes the *old* path,
 * not who takes the new one. Missing a binary resource here sends it through
 * `passthrough` unbuffered, which is safe for anything; missing it the other
 * way — a blacklist of what counts as binary — would silently text-decode a
 * JSON response the day someone adds a resource that answers with something
 * this file was never told about.
 */
function isJsonResponse(response: Response): boolean {
  const contentType = response.headers.get("Content-Type")
  return contentType === null || contentType.startsWith("application/json")
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

/**
 * Hand a binary upstream body on without decoding it, keeping its own headers.
 *
 * Unlike `streamed`, the `Content-Type` and `Cache-Control` are not fixed —
 * they are the resource's own decision (an image type and a long or short
 * cache lifetime for `assets` depending on whether a favicon was found; a
 * filename and a media type for `attachments`), and copying them through is
 * what lets the browser cache a hit for a week and a miss for a day, or
 * download a file under its own name, exactly as the API intended.
 * `Content-Disposition` names that filename and `X-Content-Type-Options`
 * (phase 05) is what stops the browser from sniffing an uploaded file into
 * something more dangerous than its declared type — both are copied for the
 * same reason as `Content-Type` and `Cache-Control`: they are useless if the
 * proxy silently drops them.
 */
function passthrough(response: Response): NextResponse {
  const headers: Record<string, string> = {
    "Content-Type": response.headers.get("Content-Type") ?? "application/octet-stream",
    "Cache-Control": response.headers.get("Cache-Control") ?? "no-store",
  }
  const disposition = response.headers.get("Content-Disposition")
  if (disposition) headers["Content-Disposition"] = disposition
  const contentTypeOptions = response.headers.get("X-Content-Type-Options")
  if (contentTypeOptions) headers["X-Content-Type-Options"] = contentTypeOptions

  return new NextResponse(response.body, { status: response.status, headers })
}

async function send(
  request: NextRequest,
  target: string,
  token: string | undefined,
  body: BodyInit | undefined,
  contentType: string | null,
): Promise<Response> {
  try {
    return await dispatch(request, target, token, body, contentType)
  } catch (cause) {
    // `fetch` rejects only when the request never completed: the API is not
    // listening yet, or the connection was reset mid-flight. Both are ordinary
    // during the half-minute a freshly started container spends migrating and
    // booting. Letting the rejection escape made every one of them an unhandled
    // 500 with a stack trace, which reads as a bug in this handler rather than
    // as an upstream that is not up.
    console.warn(`alpha-desk proxy: upstream unreachable (${(cause as Error).message})`)
    return NextResponse.json(
      {
        detail: {
          reason: UPSTREAM_UNREACHABLE,
          message: "Hệ thống đang không phản hồi. Đang thử lại…",
        },
      },
      { status: 503 },
    )
  }
}

function dispatch(
  request: NextRequest,
  target: string,
  token: string | undefined,
  body: BodyInit | undefined,
  contentType: string | null,
): Promise<Response> {
  const lastEventId = request.headers.get("Last-Event-ID")
  return fetch(target, {
    method: request.method,
    headers: {
      // The request's own Content-Type, forwarded verbatim — a multipart
      // boundary lives nowhere else, so hardcoding this to `application/json`
      // (the previous default) would break every non-JSON upload silently.
      // `application/json` remains the fallback for a request that named
      // none, matching the default every caller already gets from `sendAlpha`.
      "Content-Type": contentType ?? "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      // Carried through because it is the whole of a reconnect: the browser
      // sets it natively, and dropping it here would leave the backend unable
      // to say where this reader believes it got to.
      ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
    },
    // An empty string (a write with no body at all) is normalised to
    // `undefined`, same as before this file carried binary bodies; an
    // `ArrayBuffer`, empty or not, is passed through as-is.
    body: typeof body === "string" ? body || undefined : body,
    cache: "no-store",
  })
}

export async function GET(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

export async function POST(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return forward(request, (await context.params).path)
}

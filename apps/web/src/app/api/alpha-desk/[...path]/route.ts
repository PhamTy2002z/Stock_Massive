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
 * cookies automatically. An allowlist of the two Alpha Desk resources is
 * cheaper to keep honest than an audit of everything mounted upstream.
 *
 * A 401 from upstream is answered by rotating the access token once and
 * retrying. Rotation is reactive rather than pre-emptive because the upstream
 * is the only authority on whether a token is still good.
 */

// The resources this proxy will carry, matched on the first path segment.
// `widgets` reads back the fixed slice a stored Widget descriptor names;
// upstream serves one only when it hangs off a message the caller owns, so
// adding it here widens the proxy without widening what anyone can reach.
const FORWARDED_RESOURCES = new Set(["watchlist", "analyses", "widgets"])

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

  let token = await currentAccessToken()
  let response = await send(target, request.method, token, body)

  if (response.status === 401) {
    token = (await rotateAccessToken()) ?? undefined
    if (!token) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 })
    }
    response = await send(target, request.method, token, body)
  }

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

function send(
  target: string,
  method: string,
  token: string | undefined,
  body: string | undefined,
): Promise<Response> {
  return fetch(target, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

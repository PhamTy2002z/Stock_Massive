import { NextResponse } from "next/server"

import { getApiBaseUrl } from "@/lib/api"
import { healthUrlFrom } from "@/lib/connection-status"

/**
 * Whether the API is answering, asked from this origin.
 *
 * The connection gate polls this while the page waits on a restart. Asked from
 * the browser directly it would need the API's public address, which a
 * same-origin deployment does not publish — and a build without one probed
 * `localhost:8000` on the reader's own machine. So the question goes through
 * this process, which knows where the API lives.
 *
 * Only the status comes back. The upstream body is not this route's to repeat,
 * and a probe needs nothing but yes or no.
 */

// Short, because a probe that hangs is a probe that answered "no" slowly: the
// gate asks again every few seconds anyway.
const HEALTH_TIMEOUT_MS = 2500

export async function GET() {
  let healthy = false
  try {
    const response = await fetch(healthUrlFrom(getApiBaseUrl()), {
      cache: "no-store",
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    })
    healthy = response.ok
    // Read and dropped, so the connection is released rather than left open.
    await response.text().catch(() => "")
  } catch {
    // Unreachable, refused or timed out: all the same answer to the gate.
  }
  return new NextResponse(null, {
    status: healthy ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  })
}

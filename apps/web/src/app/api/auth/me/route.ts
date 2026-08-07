import { NextResponse } from "next/server"

import { getCurrentUser } from "@/lib/auth/current-user"

/**
 * Who am I? Backs the client-side `useAuth` hook.
 *
 * A route handler rather than a Server Component because resolving the user may
 * rotate an expired access token, and only route handlers can write cookies.
 */
export async function GET() {
  try {
    const user = await getCurrentUser()
    return NextResponse.json({ user })
  } catch {
    // The API is unreachable or erroring — report unknown rather than signed out,
    // so the UI does not flip to a logged-out state on a transient blip.
    return NextResponse.json({ error: "Unable to resolve session" }, { status: 503 })
  }
}

import "server-only"

import { AuthApiError, fetchMe, type AuthUser } from "./api"
import { rotateAccessToken } from "./bearer"
import { clearSessionCookies, getAccessToken } from "./session"

/**
 * Resolve the signed-in user, transparently rotating an expired access token.
 *
 * Returns null rather than throwing when there is no usable session, so callers
 * can treat "signed out" as an ordinary state.
 *
 * Only callable where cookies are writable (route handlers, server actions).
 * Server Components cannot set cookies; in those, read the user from a parent
 * route handler or accept that a refresh will not persist.
 *
 * **The rotation goes through `rotateAccessToken`, never straight to the API.**
 * This route and the Alpha Desk proxy both hit an expired access token in the
 * same instant — the page asks who the user is while its data is loading — and
 * a second exchange of the same refresh token is a replay as far as the
 * upstream is concerned, which costs every session the user has. Its own copy of
 * the exchange was exactly that second one.
 */
export async function getCurrentUser(): Promise<AuthUser | null> {
  const accessToken = await getAccessToken()

  if (accessToken) {
    try {
      return await fetchMe(accessToken)
    } catch (error) {
      // Anything other than a rejected token is an API problem, not a signed-out
      // user — don't destroy a valid session over a 500.
      if (!(error instanceof AuthApiError) || error.status !== 401) {
        throw error
      }
    }
  }

  const rotated = await rotateAccessToken()
  if (rotated === null) return null

  try {
    return await fetchMe(rotated)
  } catch (error) {
    // A token minted a moment ago and refused already is a session that ended
    // between the two calls, so the cookies go with it.
    if (error instanceof AuthApiError && error.status === 401) {
      await clearSessionCookies()
      return null
    }
    throw error
  }
}

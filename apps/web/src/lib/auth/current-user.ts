import "server-only"

import { AuthApiError, fetchMe, refresh, type AuthUser } from "./api"
import { clearSessionCookies, getAccessToken, getRefreshToken, setSessionCookies } from "./session"

/**
 * Resolve the signed-in user, transparently rotating an expired access token.
 *
 * Returns null rather than throwing when there is no usable session, so callers
 * can treat "signed out" as an ordinary state.
 *
 * Only callable where cookies are writable (route handlers, server actions).
 * Server Components cannot set cookies; in those, read the user from a parent
 * route handler or accept that a refresh will not persist.
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

  const refreshToken = await getRefreshToken()
  if (!refreshToken) {
    return null
  }

  try {
    const tokens = await refresh(refreshToken)
    await setSessionCookies({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      expiresIn: tokens.expires_in,
    })
    return await fetchMe(tokens.access_token)
  } catch (error) {
    if (error instanceof AuthApiError && error.status === 401) {
      await clearSessionCookies()
      return null
    }
    throw error
  }
}

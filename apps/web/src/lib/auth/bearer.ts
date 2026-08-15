import "server-only"

import { AuthApiError, refresh } from "./api"
import { clearSessionCookies, getAccessToken, getRefreshToken, setSessionCookies } from "./session"

/**
 * The access token to send upstream, and how to get a fresh one after a 401.
 *
 * Tokens live in httpOnly cookies, so the browser cannot attach them itself —
 * anything the browser calls that needs the API has to go through a route
 * handler that reads the cookie and forwards a bearer token.
 *
 * The rotation is deliberately reactive rather than pre-emptive: checking
 * expiry here would mean decoding the token on every request and still being
 * wrong whenever the clocks disagree. The upstream 401 is the authoritative
 * answer, and one retry after it is the whole recovery.
 */
export async function currentAccessToken(): Promise<string | undefined> {
  return getAccessToken()
}

/**
 * The rotation in flight, if there is one.
 *
 * The refresh token rotates: exchanging it invalidates it. The rail polls
 * alongside history, detail and opened requests, so several of them can meet a
 * `401` in the same instant — and without this, each would exchange the same
 * token. The first wins, the rest are handed a token the API has already
 * retired, and their `401` clears the cookies and signs the user out mid-poll.
 *
 * Process-local, which is the whole of the guarantee and worth stating: two Next
 * instances behind a load balancer would still race. That is acceptable at this
 * size and would need a shared lock, not a bigger variable, to fix.
 */
let inFlight: Promise<string | null> | null = null

/**
 * Exchange the refresh cookie for a new pair, or null when there is no session.
 *
 * Only callable where cookies are writable — route handlers and server actions.
 * A rejected refresh clears the cookies: the session is genuinely over, and
 * leaving a dead refresh token behind makes every later request pay for the
 * same failed exchange.
 *
 * Concurrent callers share one exchange. They are asking the same question of
 * the same cookie, so there is one answer.
 */
export async function rotateAccessToken(): Promise<string | null> {
  if (inFlight) return inFlight

  inFlight = exchange().finally(() => {
    inFlight = null
  })
  return inFlight
}

async function exchange(): Promise<string | null> {
  const refreshToken = await getRefreshToken()
  if (!refreshToken) return null

  try {
    const tokens = await refresh(refreshToken)
    await setSessionCookies({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      expiresIn: tokens.expires_in,
    })
    return tokens.access_token
  } catch (error) {
    if (error instanceof AuthApiError && error.status === 401) {
      await clearSessionCookies()
      return null
    }
    throw error
  }
}

import "server-only"

import { AuthApiError, refresh, type TokenPair } from "./api"
import { clearSessionCookies, getAccessToken, getRefreshToken, setSessionCookies } from "./session"
import { keyedSingleFlight } from "./single-flight"

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
 * How long a completed exchange stays available to a caller holding the same
 * refresh token.
 *
 * Sized for one burst of requests, not for the life of a session: the callers
 * it exists to serve are the ones that were already in the air when the access
 * token expired, and they arrive within a second of each other.
 */
const REMEMBER_EXCHANGE_MS = 60_000

/**
 * The network half of a rotation, and the only place it happens.
 *
 * Keyed by the token being spent, so a token is exchanged **once** no matter
 * how many requests present it. That is a stronger promise than one exchange at
 * a time, and the upstream is why: it reads a second presentation of a spent
 * token as a replayed credential and revokes every session the user has
 * (`auth/service.py`). A race here does not cost one request, it signs the user
 * out of everything.
 *
 * No cookie is written in here. Cookies belong to a response, so each caller
 * writes its own — see :func:`rotateAccessToken`.
 */
const exchangeOnce = keyedSingleFlight(exchange, { ttlMs: REMEMBER_EXCHANGE_MS })

/**
 * Exchange the refresh cookie for a new pair, or null when there is no session.
 *
 * Only callable where cookies are writable — route handlers and server actions.
 *
 * Every caller writes the cookies itself, including one served from the memo
 * above. That is not duplicated work: the pair only reaches the browser on a
 * response that carries it, so a straggler that skipped the write would answer
 * the request and leave the browser still holding the spent token.
 *
 * A rejected exchange clears the cookies: the session is genuinely over, and
 * leaving a dead refresh token behind makes every later request pay for the
 * same failed exchange.
 */
export async function rotateAccessToken(): Promise<string | null> {
  const refreshToken = await getRefreshToken()
  if (!refreshToken) return null

  const tokens = await exchangeOnce(refreshToken)
  if (tokens === null) {
    await clearSessionCookies()
    return null
  }

  await setSessionCookies({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresIn: tokens.expires_in,
  })
  return tokens.access_token
}

/**
 * One exchange with the API. Null means the session is over; anything else
 * throws, because an unreachable API is not a signed-out user.
 */
async function exchange(refreshToken: string): Promise<TokenPair | null> {
  try {
    return await refresh(refreshToken)
  } catch (error) {
    if (error instanceof AuthApiError && error.status === 401) return null
    throw error
  }
}

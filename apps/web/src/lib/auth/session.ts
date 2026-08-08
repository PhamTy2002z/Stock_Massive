import "server-only"

import { cookies } from "next/headers"

/**
 * Tokens live in httpOnly cookies written by the server, never in JS-readable
 * storage — client code asks `/api/auth/me` who it is instead of holding a token.
 */
export const ACCESS_TOKEN_COOKIE = "sm_access_token"
export const REFRESH_TOKEN_COOKIE = "sm_refresh_token"

// Refresh cookie outlives the access cookie so an expired access token can
// still be exchanged; keep in sync with REFRESH_TOKEN_EXPIRE_DAYS on the API.
const REFRESH_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

const baseCookieOptions = {
  httpOnly: true,
  sameSite: "lax",
  secure: process.env.NODE_ENV === "production",
  path: "/",
} as const

export interface SessionTokens {
  accessToken: string
  refreshToken: string
  /** Access token lifetime in seconds, as reported by the API. */
  expiresIn: number
}

export async function setSessionCookies(tokens: SessionTokens): Promise<void> {
  const cookieStore = await cookies()

  cookieStore.set(ACCESS_TOKEN_COOKIE, tokens.accessToken, {
    ...baseCookieOptions,
    maxAge: tokens.expiresIn,
  })
  cookieStore.set(REFRESH_TOKEN_COOKIE, tokens.refreshToken, {
    ...baseCookieOptions,
    maxAge: REFRESH_MAX_AGE_SECONDS,
  })
}

export async function clearSessionCookies(): Promise<void> {
  const cookieStore = await cookies()
  cookieStore.delete(ACCESS_TOKEN_COOKIE)
  cookieStore.delete(REFRESH_TOKEN_COOKIE)
}

export async function getAccessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value
}

export async function getRefreshToken(): Promise<string | undefined> {
  return (await cookies()).get(REFRESH_TOKEN_COOKIE)?.value
}

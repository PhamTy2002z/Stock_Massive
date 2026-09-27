import "server-only"

import { isIP } from "node:net"

import { headers } from "next/headers"

/**
 * Server-side client for the FastAPI auth endpoints.
 *
 * Runs only on the server so it can reach the API over the internal Docker
 * network and keep tokens inside httpOnly cookies.
 */

const AUTH_BASE_URL = () =>
  `${process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/auth`

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

/** How the reader describes their own investing, or null for "not said". */
export type InvestingStyle = "long_term" | "growth" | "dividend" | "swing" | "learning"

/**
 * What the account asks the assistant to keep in mind, stored per user.
 *
 * Presentation only: none of these can change what the verifier accepts as a
 * source, which is why a custom instruction is not a policy.
 */
export interface UserPreferences {
  nickname: string | null
  investing_style: InvestingStyle | null
  custom_instructions: string | null
  memory_enabled: boolean
}

export interface AuthUser {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string | null
  preferences: UserPreferences
}

/** A profile write. Only the keys present are changed; null clears one. */
export interface ProfilePatch {
  full_name?: string
  preferences?: Partial<UserPreferences>
}

export class AuthApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = "AuthApiError"
  }
}

/**
 * The reader's address, for the API's per-IP limits on sign-in and credentials.
 *
 * Every one of these calls leaves from this server, so without it the API sees
 * one peer for everyone and a stranger failing twenty logins a minute locks the
 * form for every reader. The address comes from the outer proxy: Caddy ignores
 * an `X-Forwarded-For` sent by a client it does not trust and writes the peer
 * it saw, so the first entry is the reader. That holds only while Caddy is the
 * sole way in — the production compose publishes no port for this container.
 * The API in turn trusts the header only from a private-network peer.
 *
 * Anything that does not parse as an IP is dropped rather than forwarded, and
 * a call outside a request scope (no incoming headers) simply sends none.
 */
async function clientIpHeader(): Promise<Record<string, string>> {
  let incoming: Headers
  try {
    incoming = await headers()
  } catch {
    return {}
  }
  const forwarded = incoming.get("x-forwarded-for")?.split(",")[0]?.trim()
  const candidate = forwarded || incoming.get("x-real-ip")?.trim()
  return candidate && isIP(candidate) ? { "X-Forwarded-For": candidate } : {}
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${AUTH_BASE_URL()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await clientIpHeader()) },
    body: JSON.stringify(body),
    cache: "no-store",
  })

  if (!response.ok) {
    throw new AuthApiError(response.status, await readErrorDetail(response))
  }

  // 204 responses (logout) have no body to parse.
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return typeof body?.detail === "string" ? body.detail : response.statusText
  } catch {
    return response.statusText
  }
}

export function register(input: {
  email: string
  password: string
  full_name?: string
}): Promise<TokenPair> {
  return post<TokenPair>("/register", input)
}

export function login(input: { email: string; password: string }): Promise<TokenPair> {
  return post<TokenPair>("/login", input)
}

export function refresh(refreshToken: string): Promise<TokenPair> {
  return post<TokenPair>("/refresh", { refresh_token: refreshToken })
}

export function logout(refreshToken: string): Promise<void> {
  return post<void>("/logout", { refresh_token: refreshToken })
}

/** A request made as the signed-in user. */
async function authed<T>(
  method: "POST" | "PATCH",
  path: string,
  accessToken: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${AUTH_BASE_URL()}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(await clientIpHeader()),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  })

  if (!response.ok) {
    throw new AuthApiError(response.status, await readErrorDetail(response))
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

export function updateMe(accessToken: string, patch: ProfilePatch): Promise<AuthUser> {
  return authed<AuthUser>("PATCH", "/me", accessToken, patch)
}

/** Answers with a fresh token pair, which becomes this browser's session. */
export function changePassword(
  accessToken: string,
  input: { current_password: string; new_password: string }
): Promise<TokenPair> {
  return authed<TokenPair>("POST", "/password", accessToken, input)
}

export function logoutAll(accessToken: string): Promise<void> {
  return authed<void>("POST", "/logout-all", accessToken)
}

export async function fetchMe(accessToken: string): Promise<AuthUser> {
  const response = await fetch(`${AUTH_BASE_URL()}/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  })

  if (!response.ok) {
    throw new AuthApiError(response.status, await readErrorDetail(response))
  }
  return (await response.json()) as AuthUser
}

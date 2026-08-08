import "server-only"

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

export interface AuthUser {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string | null
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

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${AUTH_BASE_URL()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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

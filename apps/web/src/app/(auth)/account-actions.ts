"use server"

import {
  AuthApiError,
  changePassword,
  logoutAll,
  updateMe,
  type AuthUser,
  type InvestingStyle,
  type ProfilePatch,
  type UserPreferences,
} from "@/lib/auth/api"
import { withAccessToken } from "@/lib/auth/bearer"
import { clearSessionCookies, setSessionCookies } from "@/lib/auth/session"

/**
 * The account writes Settings makes.
 *
 * Server actions because the token lives in an httpOnly cookie: only the server
 * can attach it, and only the server can write the pair a password change
 * answers with. Each returns a result instead of throwing — a thrown error is
 * masked in a production build, and the caller needs the status to say whether
 * the reader typed something wrong or the service did.
 *
 * Every argument is re-checked here. A server action is a public endpoint, so
 * the shape the settings form happens to send is not something it can assume.
 */

export type ActionResult<T = undefined> =
  | { ok: true; value: T }
  | { ok: false; status: number; error: string }

const STYLES: readonly InvestingStyle[] = ["long_term", "growth", "dividend", "swing", "learning"]

function refused(status: number, error: string): { ok: false; status: number; error: string } {
  return { ok: false, status, error }
}

function failure(error: unknown): { ok: false; status: number; error: string } {
  if (error instanceof AuthApiError) return refused(error.status, error.message)
  return refused(503, "Service unavailable")
}

const nullableText = (value: unknown): value is string | null =>
  value === null || typeof value === "string"

/** The patch with only the keys this product writes, or null when one is malformed. */
function cleanPatch(input: unknown): ProfilePatch | null {
  if (typeof input !== "object" || input === null) return null
  const raw = input as Record<string, unknown>
  const patch: ProfilePatch = {}

  if ("full_name" in raw) {
    if (typeof raw.full_name !== "string" || raw.full_name.trim() === "") return null
    patch.full_name = raw.full_name.trim()
  }

  if ("preferences" in raw) {
    if (typeof raw.preferences !== "object" || raw.preferences === null) return null
    const source = raw.preferences as Record<string, unknown>
    const preferences: Partial<UserPreferences> = {}

    for (const key of ["nickname", "custom_instructions"] as const) {
      if (!(key in source)) continue
      const value = source[key]
      if (!nullableText(value)) return null
      preferences[key] = value === null || value.trim() === "" ? null : value.trim()
    }
    if ("investing_style" in source) {
      const value = source.investing_style
      if (value !== null && !STYLES.includes(value as InvestingStyle)) return null
      preferences.investing_style = value as InvestingStyle | null
    }
    if ("memory_enabled" in source) {
      if (typeof source.memory_enabled !== "boolean") return null
      preferences.memory_enabled = source.memory_enabled
    }
    patch.preferences = preferences
  }

  return patch
}

export async function updateProfileAction(input: unknown): Promise<ActionResult<AuthUser>> {
  const patch = cleanPatch(input)
  if (patch === null) return refused(422, "Invalid profile")

  try {
    return { ok: true, value: await withAccessToken((token) => updateMe(token, patch)) }
  } catch (error) {
    return failure(error)
  }
}

export async function changePasswordAction(input: unknown): Promise<ActionResult> {
  const raw = (typeof input === "object" && input !== null ? input : {}) as Record<string, unknown>
  const current = raw.current_password
  const next = raw.new_password
  if (typeof current !== "string" || typeof next !== "string" || current === "" || next.length < 8) {
    return refused(422, "Invalid password")
  }

  try {
    const tokens = await withAccessToken((token) =>
      changePassword(token, { current_password: current, new_password: next })
    )
    await setSessionCookies({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      expiresIn: tokens.expires_in,
    })
    return { ok: true, value: undefined }
  } catch (error) {
    return failure(error)
  }
}

/**
 * Revoke every session this account has, this one included.
 *
 * The cookies go here rather than being left to the caller's sign-out: once
 * upstream has revoked the refresh token, a browser that still held it would
 * only spend a request finding that out.
 */
export async function logoutAllAction(): Promise<ActionResult> {
  try {
    await withAccessToken((token) => logoutAll(token))
    await clearSessionCookies()
    return { ok: true, value: undefined }
  } catch (error) {
    return failure(error)
  }
}

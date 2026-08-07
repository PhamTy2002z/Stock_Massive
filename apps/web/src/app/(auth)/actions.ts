"use server"

import { redirect } from "next/navigation"

import { AuthApiError, login, logout, register } from "@/lib/auth/api"
import { clearSessionCookies, getRefreshToken, setSessionCookies } from "@/lib/auth/session"

export interface AuthActionResult {
  error?: string
}

/**
 * Only relative paths are honoured, so a crafted `?next=https://evil.example`
 * cannot turn the login form into an open redirect.
 */
function safeRedirectPath(next?: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/"
  }
  return next
}

async function persist(tokens: {
  access_token: string
  refresh_token: string
  expires_in: number
}): Promise<void> {
  await setSessionCookies({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresIn: tokens.expires_in,
  })
}

export async function loginAction(
  formData: FormData,
  next?: string
): Promise<AuthActionResult> {
  const email = String(formData.get("email") ?? "")
  const password = String(formData.get("password") ?? "")

  try {
    await persist(await login({ email, password }))
  } catch (error) {
    if (error instanceof AuthApiError) {
      return { error: error.status === 401 ? "Incorrect email or password" : error.message }
    }
    return { error: "Unable to sign in. Please try again." }
  }

  redirect(safeRedirectPath(next))
}

export async function registerAction(
  formData: FormData,
  next?: string
): Promise<AuthActionResult> {
  const email = String(formData.get("email") ?? "")
  const password = String(formData.get("password") ?? "")
  const fullName = String(formData.get("full_name") ?? "").trim()

  try {
    await persist(
      await register({ email, password, full_name: fullName || undefined })
    )
  } catch (error) {
    if (error instanceof AuthApiError) {
      return {
        error:
          error.status === 409
            ? "That email is already registered"
            : error.status === 422
              ? "Please check your email and password (minimum 8 characters)"
              : error.message,
      }
    }
    return { error: "Unable to create your account. Please try again." }
  }

  redirect(safeRedirectPath(next))
}

export async function logoutAction(): Promise<void> {
  const refreshToken = await getRefreshToken()

  if (refreshToken) {
    // Revoking server-side is best-effort: the local cookies must be cleared
    // either way, or a failed call would leave the user stuck signed in.
    try {
      await logout(refreshToken)
    } catch {
      // ignored deliberately
    }
  }

  await clearSessionCookies()
  redirect("/login")
}

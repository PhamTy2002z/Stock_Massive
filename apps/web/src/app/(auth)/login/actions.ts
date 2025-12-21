"use server"

import { redirect } from "next/navigation"
import { createClient } from "@/utils/supabase/server"

/**
 * Handle Google OAuth sign-in via Supabase Auth
 */
export async function handleGoogleSignIn(
  callbackUrl?: string
): Promise<{ error?: string }> {
  const supabase = await createClient()

  const redirectTo = `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback${
    callbackUrl ? `?next=${encodeURIComponent(callbackUrl)}` : ""
  }`

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo,
      queryParams: {
        access_type: "offline",
        prompt: "consent",
      },
    },
  })

  if (error) {
    return { error: error.message }
  }

  if (data.url) {
    redirect(data.url)
  }

  return { error: "Failed to initiate OAuth flow" }
}

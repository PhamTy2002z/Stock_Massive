"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { logoutAction } from "@/app/(auth)/actions"
import { ApiUnavailableError, connectionStatus, isRetryableStatus } from "@/lib/connection-status"
import { queryKeys } from "@/lib/query-keys"

export interface AuthUser {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string | null
}

const ME_URL = "/api/auth/me"

/**
 * Ask the route handler who is signed in, in the vocabulary the rest of the app
 * already speaks.
 *
 * The handler answers 503 when the API is unreachable — which it is for the
 * first half-minute after `pnpm dev`, while the container migrates and boots.
 * A plain `Error` for that made the shell's very first read fatal: nothing
 * retried it, the boundary swallowed the page, and the reader got an error
 * screen for a backend that was merely still starting. Silence belongs to
 * `ApiUnavailableError`, so ConnectionGate veils and lifts on its own.
 */
async function fetchCurrentUser(): Promise<AuthUser | null> {
  let response: Response
  try {
    response = await fetch(ME_URL, { credentials: "same-origin" })
  } catch (cause) {
    connectionStatus.reportWaiting(ME_URL)
    throw new ApiUnavailableError(undefined, undefined, { cause })
  }

  if (isRetryableStatus(response.status)) {
    connectionStatus.reportWaiting(ME_URL)
    throw new ApiUnavailableError(undefined, response.status)
  }

  connectionStatus.reportReady(ME_URL)

  if (!response.ok) {
    throw new Error("Unable to resolve session")
  }
  return (await response.json()).user ?? null
}

/**
 * Current user for client components.
 *
 * Tokens live in httpOnly cookies, so the browser cannot read them — the
 * session is resolved by asking our own route handler, which also rotates an
 * expired access token on the way through.
 */
export function useAuth() {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.currentUser,
    queryFn: fetchCurrentUser,
    staleTime: 5 * 60 * 1000,
    // Retry is left to QUERY_DEFAULTS, which waits out an unreachable API and
    // gives up quickly on anything the server actually answered.
    refetchOnWindowFocus: true,
  })

  const signOut = useMutation({
    mutationFn: logoutAction,
    // `logoutAction` ends in `redirect()`, which Next reports by rejecting the
    // action promise — the mutation therefore never settles as a success, so
    // the clean-up has to run either way.
    onSettled: () => {
      // Drop every cached query: some hold data scoped to the user who left.
      queryClient.clear()
    },
  })

  return {
    user: query.data ?? null,
    isPending: query.isPending,
    isAuthenticated: !!query.data,
    signOut: signOut.mutate,
    isSigningOut: signOut.isPending,
  }
}

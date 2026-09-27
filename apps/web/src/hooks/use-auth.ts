"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { updateProfileAction } from "@/app/(auth)/account-actions"
import { logoutAction } from "@/app/(auth)/actions"
import type { AuthUser, ProfilePatch, UserPreferences } from "@/lib/auth/api"
import { ApiUnavailableError, connectionStatus, isRetryableStatus } from "@/lib/connection-status"
import { queryKeys } from "@/lib/query-keys"

export type { AuthUser, InvestingStyle, ProfilePatch, UserPreferences } from "@/lib/auth/api"

/**
 * What an account that has never set a preference means by each one.
 *
 * Applied to the session read, so an API that has not yet learned to send
 * `preferences` answers as an account with no opinions rather than as a
 * crash in every pane that reads one.
 */
export const DEFAULT_USER_PREFERENCES: UserPreferences = {
  nickname: null,
  investing_style: null,
  custom_instructions: null,
  memory_enabled: true,
}

function withPreferences(user: AuthUser | null): AuthUser | null {
  if (user === null) return null
  return { ...user, preferences: { ...DEFAULT_USER_PREFERENCES, ...user.preferences } }
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
  return withPreferences((await response.json()).user ?? null)
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

/** A profile write the API refused, with the status that says why. */
export class ProfileWriteError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = "ProfileWriteError"
  }
}

function merge(user: AuthUser, patch: ProfilePatch): AuthUser {
  return {
    ...user,
    ...(patch.full_name === undefined ? {} : { full_name: patch.full_name }),
    preferences: { ...user.preferences, ...patch.preferences },
  }
}

/**
 * Write part of the profile, and put the answer where every pane reads it.
 *
 * The response replaces the cached user rather than the patch being merged in,
 * because the API is the one that normalises what was sent. `optimistic` draws
 * the change before the answer and puts the old user back on a refusal — right
 * for a switch, whose new position the reader expects at once; a text field
 * keeps its own draft instead and needs nothing drawn early.
 */
export function useUpdateProfile({ optimistic = false }: { optimistic?: boolean } = {}) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (patch: ProfilePatch) => {
      const result = await updateProfileAction(patch)
      if (!result.ok) throw new ProfileWriteError(result.status, result.error)
      return result.value
    },
    onMutate: async (patch) => {
      const previous = queryClient.getQueryData<AuthUser | null>(queryKeys.currentUser)
      if (optimistic && previous) {
        await queryClient.cancelQueries({ queryKey: queryKeys.currentUser })
        queryClient.setQueryData(queryKeys.currentUser, merge(previous, patch))
      }
      return { previous }
    },
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.currentUser, withPreferences(user))
      toast.success("Saved")
    },
    onError: (error, _patch, context) => {
      if (optimistic && context?.previous !== undefined) {
        queryClient.setQueryData(queryKeys.currentUser, context.previous)
      }
      const status = error instanceof ProfileWriteError ? error.status : 0
      toast.error(
        status === 422
          ? "That value isn't valid."
          : status === 401
            ? "Your session has expired. Please sign in again."
            : "Couldn't save the change. Please try again.",
      )
    },
  })
}

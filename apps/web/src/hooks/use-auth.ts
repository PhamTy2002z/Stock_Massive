"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { logoutAction } from "@/app/(auth)/actions"
import { queryKeys } from "@/lib/query-keys"

export interface AuthUser {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string | null
}

async function fetchCurrentUser(): Promise<AuthUser | null> {
  const response = await fetch("/api/auth/me", { credentials: "same-origin" })

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
    retry: false,
    refetchOnWindowFocus: true,
  })

  const signOut = useMutation({
    mutationFn: logoutAction,
    onSuccess: () => {
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

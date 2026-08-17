"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"

import { ApiUnavailableError } from "@/lib/connection-status"

/**
 * What every query in the app inherits, exported so a test can hold a client to
 * the same terms the app runs on.
 *
 * A query that must not obey `throwOnError` — one whose pane reports its own
 * failure instead of replacing the page — opts out at its own hook, and that
 * opt-out is only worth testing against these defaults rather than against a
 * copy of them.
 */
export const QUERY_DEFAULTS = {
  queries: {
    staleTime: 5 * 60 * 1000, // 5 minutes (relaxed strategy per plan)
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
    // An unreachable API is worth waiting out; a refusal is not. One
    // retry each would give up on a container that takes three seconds
    // to come back, and the user would get an error screen for it.
    retry: (failureCount: number, error: Error) =>
      error instanceof ApiUnavailableError ? failureCount < 6 : failureCount < 1,
    retryDelay: (attempt: number) => Math.min(1000 * 2 ** attempt, 15000),
    // Errors still reach the ErrorBoundary — except the ones the system
    // resolves on its own, which ConnectionGate veils instead. Throwing
    // those would replace the page over a two-second restart.
    throwOnError: (error: Error) => !(error instanceof ApiUnavailableError),
  },
} as const

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: QUERY_DEFAULTS }))

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}

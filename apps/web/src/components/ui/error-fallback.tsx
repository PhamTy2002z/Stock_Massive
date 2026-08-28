"use client"

/**
 * What an error boundary shows, in the product's own vocabulary.
 *
 * This used to sniff the error's *message* for the words "network" or "fetch"
 * and otherwise print the raw `error.message` under a fixed heading — so a 403
 * and a dropped connection arrived as the same card, and an unlucky reader got
 * an English exception string in the middle of a Vietnamese product. The
 * classification now happens in `lib/failure.ts`, which reads the status rather
 * than guessing at prose, and this component only chooses the density.
 *
 * The signature is unchanged because `QueryErrorBoundary` is mounted in several
 * places and every one of them keeps working.
 */

import { FailureState } from "@/components/ui/failure-state"
import { describeFailure } from "@/lib/failure"

interface ErrorFallbackProps {
  error: Error
  resetErrorBoundary: () => void
  compact?: boolean
  className?: string
}

export function ErrorFallback({
  error,
  resetErrorBoundary,
  compact,
  className,
}: ErrorFallbackProps) {
  return (
    <FailureState
      failure={describeFailure(error)}
      density={compact ? "inline" : "region"}
      // Resetting the boundary is what re-runs the render that threw, and for a
      // query that is also what refetches it: `QueryErrorBoundary` wires this to
      // TanStack's own reset.
      onRetry={resetErrorBoundary}
      className={className}
    />
  )
}

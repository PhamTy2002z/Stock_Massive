"use client"

import { QueryErrorResetBoundary } from "@tanstack/react-query"
import { ErrorBoundary } from "react-error-boundary"
import { ErrorFallback } from "@/components/ui/error-fallback"

interface QueryErrorBoundaryProps {
  children: React.ReactNode
  compact?: boolean
  className?: string
}

/**
 * JS lets you throw anything, so react-error-boundary hands back `unknown`.
 * ErrorFallback reads `.message`, so give it a real Error either way.
 */
function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error))
}

export function QueryErrorBoundary({
  children,
  compact,
  className,
}: QueryErrorBoundaryProps) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary
          onReset={reset}
          fallbackRender={({ error, resetErrorBoundary }) => (
            <ErrorFallback
              error={toError(error)}
              resetErrorBoundary={resetErrorBoundary}
              compact={compact}
              className={className}
            />
          )}
        >
          {children}
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}

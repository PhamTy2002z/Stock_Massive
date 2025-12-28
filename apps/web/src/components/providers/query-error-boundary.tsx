"use client"

import { QueryErrorResetBoundary } from "@tanstack/react-query"
import { ErrorBoundary } from "react-error-boundary"
import { ErrorFallback } from "@/components/ui/error-fallback"

interface QueryErrorBoundaryProps {
  children: React.ReactNode
  compact?: boolean
  className?: string
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
              error={error}
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

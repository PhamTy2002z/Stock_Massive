/**
 * Suspense fallback for the auth pages.
 *
 * AuthForm reads search params, which suspends on first render; this keeps the
 * page from collapsing to blank while that resolves.
 */
export default function AuthFormFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-[450px] space-y-6">
        <div className="flex flex-col items-center space-y-2 text-center">
          <div className="h-8 w-48 animate-pulse rounded bg-muted" />
          <div className="h-4 w-64 animate-pulse rounded bg-muted" />
        </div>
        <div className="space-y-4">
          <div className="h-12 w-full animate-pulse rounded bg-muted" />
          <div className="h-12 w-full animate-pulse rounded bg-muted" />
          <div className="h-12 w-full animate-pulse rounded bg-muted" />
        </div>
      </div>
    </div>
  )
}

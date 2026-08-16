/**
 * What stands in for the form while it loads.
 *
 * The shapes are the form's own — two fields and a full-width action — drawn on
 * the surface ladder rather than in the light greys the v3 design used. A
 * placeholder painted #eef0f3 on a #0c0c0c page is a white flash, which is the
 * one thing a loading state must not be.
 */
export default function AuthFormFallback() {
  return (
    <div className="grid min-h-dvh bg-background lg:grid-cols-2">
      <div className="flex min-h-dvh items-center justify-center px-6 sm:px-14">
        <div className="w-full max-w-[392px] space-y-5">
          <div className="h-11 w-56 animate-pulse rounded-lg bg-foreground/[0.07]" />
          <div className="h-5 w-80 max-w-full animate-pulse rounded bg-foreground/[0.07]" />
          <div className="h-12 w-full animate-pulse rounded-[10px] bg-foreground/[0.07]" />
          <div className="h-12 w-full animate-pulse rounded-[10px] bg-foreground/[0.07]" />
          <div className="h-12 w-full animate-pulse rounded-full bg-primary/40" />
        </div>
      </div>
      <div className="hidden min-h-dvh bg-surface-panel lg:block" />
    </div>
  )
}

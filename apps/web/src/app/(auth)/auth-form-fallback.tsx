/**
 * What stands in for the form while it loads.
 *
 * The shapes are the form's own — a heading, two fields and a full-width action
 * — drawn on the surface ladder rather than in light greys. A placeholder
 * painted white on a #191815 page is a flash, which is the one thing a loading
 * state must not be.
 */
export default function AuthFormFallback() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-6">
      <div className="w-full max-w-[392px] space-y-5">
        <div className="h-11 w-56 animate-pulse rounded-lg bg-foreground/[0.07]" />
        <div className="h-5 w-80 max-w-full animate-pulse rounded bg-foreground/[0.07]" />
        <div className="h-12 w-full animate-pulse rounded-[11px] bg-foreground/[0.07]" />
        <div className="h-12 w-full animate-pulse rounded-[11px] bg-foreground/[0.07]" />
        <div className="h-12 w-full animate-pulse rounded-[11px] bg-primary/40" />
      </div>
    </div>
  )
}

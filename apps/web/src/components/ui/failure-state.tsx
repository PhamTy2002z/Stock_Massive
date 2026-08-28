"use client"

/**
 * What a failure looks like, at the three sizes this product fails at.
 *
 * The words come from `lib/failure.ts`; this file only decides how much room
 * they get. Splitting it that way is what stops the same 401 from being a
 * heading on one screen and a toast on another.
 *
 * **A failure is tonal, not red.** The reflex is to paint an error state in the
 * destructive colour, and this system forbids it: red and green here are the
 * *board's* vocabulary — a falling price, a losing session — and spending red
 * on ordinary chrome teaches the reader that the colour means nothing in
 * particular. So a failure is drawn in the same ink ladder as everything else,
 * one step quieter, and what carries the emphasis is the way out. Red stays
 * where it is genuinely about loss: a destructive confirmation, a field the
 * reader must fix.
 *
 * **The three densities are three amounts of room, not three importances.**
 *
 * - `page` owns the viewport. The mark, the serif line the product greets with,
 *   and the one filled control — the only place amber is right, because nothing
 *   else is on screen to compete with it.
 * - `region` owns a pane: the desk panel, the thread rail, a tab. Its action is
 *   an outline, because the shell around it already spends the view's amber on
 *   the composer, and the rationing rule is per view rather than per component.
 * - `inline` owns a line inside a block. A sentence and a word to press.
 *
 * Every density is announced: a failure that replaced content after the reader
 * pressed something is exactly the case a screen reader is otherwise never told
 * about.
 */

import Link from "next/link"
import { RefreshCw } from "lucide-react"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { Button } from "@/components/ui/button"
import type { Failure } from "@/lib/failure"
import { cn } from "@/lib/utils"

export type FailureDensity = "page" | "region" | "inline"

interface FailureStateProps {
  failure: Failure
  density?: FailureDensity
  /**
   * What the recovery control does, when the route out is one this surface owns.
   *
   * `retry` and `reload` are the caller's to implement — only it knows whether
   * that means refetching one query, resetting a boundary, or reloading the
   * document. `signin` and `home` are navigations and are handled here, so two
   * surfaces cannot send the reader to two different sign-in routes.
   */
  onRetry?: () => void
  className?: string
}

export function FailureState({
  failure,
  density = "region",
  onRetry,
  className,
}: FailureStateProps) {
  const action = <RecoveryControl failure={failure} density={density} onRetry={onRetry} />

  if (density === "inline") {
    return (
      <p
        role="alert"
        className={cn("text-meta text-muted-foreground", className)}
      >
        {failure.detail !== "" && failure.detail}
        {action}
      </p>
    )
  }

  if (density === "page") {
    return (
      <div
        className={cn(
          "flex h-dvh flex-col items-center justify-center gap-4 bg-background px-6 text-center",
          className,
        )}
      >
        <VisgniteMark className="h-8 w-[21px]" />
        <h1 className="font-serif text-[1.8rem] font-normal leading-tight text-ink-display">
          {failure.title}
        </h1>
        {failure.detail !== "" && (
          <p className="max-w-sm text-pretty text-row text-ink-4">{failure.detail}</p>
        )}
        {action}
      </div>
    )
  }

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-2 py-6 text-left",
        className,
      )}
    >
      <p className="text-row font-medium text-ink-2">{failure.title}</p>
      {failure.detail !== "" && (
        <p className="max-w-[46ch] text-pretty text-meta leading-relaxed text-ink-4">
          {failure.detail}
        </p>
      )}
      {action}
    </div>
  )
}

/**
 * The way out, drawn at this density.
 *
 * Returns nothing at all when the failure has no route out. A disabled button,
 * or a "Thử lại" that re-asks a question already answered, is worse than the
 * blank: it tells the reader there is something to try when the whole point of
 * the state is that there is not.
 */
function RecoveryControl({
  failure,
  density,
  onRetry,
}: {
  failure: Failure
  density: FailureDensity
  onRetry?: () => void
}) {
  if (failure.recovery === "none" || failure.action === null) return null

  if (failure.recovery === "signin" || failure.recovery === "home") {
    const href = failure.recovery === "signin" ? "/login" : "/"
    if (density === "inline") {
      return (
        <Link href={href} className={INLINE_ACTION}>
          {failure.action}
        </Link>
      )
    }
    return (
      <Button
        asChild
        size="action"
        variant={density === "page" ? "default" : "outline"}
        className="mt-2 px-4"
      >
        <Link href={href}>{failure.action}</Link>
      </Button>
    )
  }

  // `reload` is the last resort and belongs to the document, not to a query:
  // it is what is left when the interface itself is the thing that broke.
  const run =
    failure.recovery === "reload"
      ? () => window.location.reload()
      : onRetry

  // A retry with nothing wired to it would be the lying button this component
  // exists to avoid.
  if (run === undefined) return null

  if (density === "inline") {
    return (
      <button type="button" onClick={run} className={INLINE_ACTION}>
        {failure.action}
      </button>
    )
  }

  return (
    <Button
      onClick={run}
      size="action"
      variant={density === "page" ? "default" : "outline"}
      className="mt-2 px-4"
    >
      <RefreshCw aria-hidden />
      {failure.action}
    </Button>
  )
}

/** The word-sized action, held to the same focus ring as every other control. */
const INLINE_ACTION =
  "ml-1.5 rounded-sm text-ink-2 underline underline-offset-2 transition-colors hover:text-ink-1 focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-ring"

"use client"

/**
 * PROTOTYPE CHROME — throwaway, and never shipped: the whole bar returns null in
 * a production build. Flips the `?variant=` param with the arrows or the ← / →
 * keys, and hosts any extra prototype-only controls via `children`.
 */

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface PrototypeSwitcherProps {
  variants: readonly string[]
  /** Optional display name per variant key. */
  names?: Record<string, string>
  current: string
  /** Extra prototype-only controls, e.g. a fixture picker. */
  children?: React.ReactNode
}

export function PrototypeSwitcher({
  variants,
  names,
  current,
  children,
}: PrototypeSwitcherProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const index = Math.max(0, variants.indexOf(current))

  const go = React.useCallback(
    (delta: number) => {
      const next = variants[(index + delta + variants.length) % variants.length]
      const params = new URLSearchParams(searchParams.toString())
      params.set("variant", next)
      router.replace(`${pathname}?${params.toString()}`, { scroll: false })
    },
    [index, pathname, router, searchParams, variants]
  )

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      ) {
        return
      }
      if (e.key === "ArrowLeft") go(-1)
      if (e.key === "ArrowRight") go(1)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [go])

  if (process.env.NODE_ENV === "production") return null

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center">
      <div className="pointer-events-auto flex max-w-[calc(100vw-1rem)] items-center gap-1 overflow-x-auto rounded-full bg-neutral-900 px-1.5 py-1.5 text-white shadow-2xl ring-1 ring-black/20">
        <button
          type="button"
          onClick={() => go(-1)}
          aria-label="Variant trước"
          className="rounded-full p-1.5 transition-colors hover:bg-white/15"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="min-w-0 shrink-0 px-1 text-center text-xs font-medium tabular-nums sm:min-w-[13rem] sm:px-2">
          {current}
          {names?.[current] && (
            <span className="hidden sm:inline"> — {names[current]}</span>
          )}
          <span className="ml-1.5 text-white/50">
            {index + 1}/{variants.length}
          </span>
        </span>
        <button
          type="button"
          onClick={() => go(1)}
          aria-label="Variant sau"
          className="rounded-full p-1.5 transition-colors hover:bg-white/15"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        {children && (
          <>
            <span className="mx-1 h-5 w-px bg-white/20" />
            {children}
          </>
        )}
      </div>
    </div>
  )
}

/** Segmented picker for the bar — used here to swap the fixture symbol. */
export function PrototypeSegments({
  param,
  options,
  current,
}: {
  param: string
  options: readonly string[]
  current: string
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const set = (value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set(param, value)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }

  return (
    <>
      <select
        value={current}
        onChange={(event) => set(event.target.value)}
        aria-label={param}
        className="mr-1 rounded-full border-0 bg-white px-2 py-1 text-xs font-medium text-neutral-900 outline-none sm:hidden"
      >
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
      <div className="hidden items-center gap-0.5 pr-1 sm:flex">
        {options.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => set(o)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              o === current ? "bg-white text-neutral-900" : "hover:bg-white/15"
            }`}
          >
            {o}
          </button>
        ))}
      </div>
    </>
  )
}

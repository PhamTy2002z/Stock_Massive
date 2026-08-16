"use client"

import { useEffect, useState } from "react"
import { BarChart3 } from "lucide-react"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { useAuth } from "@/hooks/use-auth"
import { useMarketIndices } from "@/hooks/use-market-indices"
import { FIRST_RUN } from "@/lib/alpha-desk/copy"
import { formatVietnamDate } from "@/lib/market-session"

import { Composer } from "./composer"
import { Figure } from "./primitives"
import { useShell } from "./shell-state"

/**
 * What a new conversation opens on.
 *
 * The whole cluster — greeting, field, and where the market stands — sits in the
 * middle of the surface rather than at the bottom of it. Nothing here is a
 * separate route: asking a question switches the view and the composer keeps
 * its focus and its half-typed text through the change, which it could not do
 * if this screen owned a second composer of its own.
 */
export function NewConversationView() {
  const { dispatch } = useShell()

  return (
    <div className="scrollbar-thin flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-5 pb-16 pt-5">
      <div className="w-full max-w-[680px]">
        <Greeting />

        <div className="mt-5">
          <Composer variant="opening" />
        </div>

        <SessionGlance />

        <div className="mt-2.5 flex justify-center">
          <button
            type="button"
            onClick={() => dispatch({ type: "view", view: "board" })}
            className="flex items-center gap-1.5 px-1 py-1.5 text-meta text-ink-6 transition-colors hover:text-primary"
          >
            <BarChart3 className="size-[15px]" strokeWidth={1.6} />
            Mở bảng giá phiên {formatVietnamDate(new Date()).slice(0, 5)}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * The mark, and the time of day by the reader's own clock.
 *
 * The hour is read after mount. Rendered on the server it would state whichever
 * part of the day the *server* is in, and the first client frame would disagree
 * with it — a hydration mismatch over a pleasantry.
 */
function Greeting() {
  const { user } = useAuth()
  const [hour, setHour] = useState<number | null>(null)

  useEffect(() => setHour(new Date().getHours()), [])

  const name = user?.full_name?.split(" ").at(-1) || user?.email?.split("@")[0] || null
  const partOfDay =
    hour === null
      ? null
      : hour < 12
        ? "Chào buổi sáng"
        : hour < 17
          ? "Chào buổi chiều"
          : "Chào buổi tối"

  return (
    <div className="flex items-center justify-center gap-3">
      <VisgniteMark className="h-[26px] w-[17px]" />
      {/* The one serif line in the product. Set at display size and in a warm
          off-white because at this weight the body's neutral white goes cold
          against the ground — see the note on the font in app/layout. */}
      <h2 className="min-w-0 font-serif text-[clamp(1.6rem,2.7vw,2.15rem)] font-normal leading-[1.1] tracking-[-0.01em] text-ink-display">
        {partOfDay ? `${partOfDay}${name ? `, ${name}` : ""}` : FIRST_RUN.question}
      </h2>
    </div>
  )
}

const percent = (value: number) =>
  `${value >= 0 ? "+" : "−"}${Math.abs(value).toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`

/**
 * Where the market stands, in one monospaced line.
 *
 * Only what the indices endpoint actually returns. The reference glances at
 * turnover and at the foreign net as well, and this deliberately does not:
 * neither figure is on this API, and a desk that exists to keep numbers
 * provable is the last surface that should print one it cannot source.
 */
function SessionGlance() {
  const { data } = useMarketIndices()
  const indices = (data ?? []).slice(0, 3)

  if (indices.length === 0) return null

  return (
    <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-1.5 font-mono text-micro">
      {indices.map((index) => (
        <span key={index.symbol} className="inline-flex items-baseline gap-1.5">
          <span className="text-ink-5">{index.name}</span>
          <Figure className="text-ink-2">
            {index.value.toLocaleString("vi-VN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </Figure>
          <Figure className={index.changePercent >= 0 ? "text-positive" : "text-negative"}>
            {percent(index.changePercent)}
          </Figure>
        </span>
      ))}
    </div>
  )
}

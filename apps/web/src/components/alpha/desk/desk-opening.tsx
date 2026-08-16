"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { BarChart3 } from "lucide-react"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { useAuth } from "@/hooks/use-auth"
import { useMarketIndices } from "@/hooks/use-market-indices"
import { FIRST_RUN } from "@/lib/alpha-desk/copy"
import { FirstRun } from "./first-run"

/**
 * The first-run screen with its two live parts filled in.
 *
 * Everything that needs a hook lives here rather than in `FirstRun`, for the
 * same reason the dock is assembled by the container: the transcript and the
 * surface under it are presentational, and a query hook inside them would make
 * rendering the layout mean mocking three of them.
 */
export function DeskOpening() {
  return <FirstRun heading={<Greeting />} glance={<SessionGlance />} />
}

/**
 * The mark, and the time of day by the reader's own clock.
 *
 * The hour is read after mount. Rendered on the server it would state whichever
 * part of the day the *server* is in, and the first client frame would disagree
 * with it — a hydration mismatch over a pleasantry. Until then the opening
 * question carries the line on its own, which is what it always did.
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
    <div className="flex items-center gap-3">
      <VisgniteMark className="h-[26px] w-[17px]" />
      {/* The one serif line in the product. It is set at display size and in a
          warm off-white because at this weight the body's neutral white goes
          cold against the ground — see the note on the font in app/layout. */}
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
 *
 * It renders nothing until the query answers — an empty conversation with a row
 * of dashes in it looks like the session failed.
 */
function SessionGlance() {
  const { data } = useMarketIndices()
  const indices = (data ?? []).slice(0, 3)

  if (indices.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 font-mono text-micro">
      {indices.map((index) => (
        <span key={index.symbol} className="inline-flex items-baseline gap-1.5">
          <span className="text-ink-5">{index.name}</span>
          <span className="text-ink-3">
            {index.value.toLocaleString("vi-VN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
          <span className={index.changePercent >= 0 ? "text-positive" : "text-negative"}>
            {percent(index.changePercent)}
          </span>
        </span>
      ))}

      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-ink-5 transition-colors hover:text-foreground"
      >
        <BarChart3 className="size-[15px]" />
        Mở bảng giá
      </Link>
    </div>
  )
}

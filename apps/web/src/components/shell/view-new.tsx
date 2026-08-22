"use client"

import { BarChart3 } from "lucide-react"
import { useState } from "react"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { useAuth } from "@/hooks/use-auth"
import { useMarketIndices } from "@/hooks/use-market-indices"
import { greetingFor, plainGreeting } from "@/lib/greeting"
import { stickyRoll } from "@/lib/greeting-roll"
import { formatVietnamDate, vietnamPartOfDay } from "@/lib/market-session"

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
 * The mark, and the time of day on the market's clock.
 *
 * The hour is read during render, not after mount: an effect-borne value would
 * open the surface on a placeholder line and replace it a frame later, which
 * reads as the screen changing its mind. Vietnam's zone is the same on the
 * server and in the browser, so the word matches across hydration whatever zone
 * the reader is actually sitting in.
 *
 * **This one line is in English, and it is the only one.** The rest of the
 * product speaks Vietnamese; the greeting is set in the serif display face
 * where the Vietnamese diacritics sit unevenly at this size, so it is left as
 * `Morning, <name>`.
 *
 * Which of the day's lines gets used is drawn once and then held for two hours
 * (`stickyRoll`), so a session opens on one line instead of dealing a new one
 * every trip back to this screen. The draw is gated on the session having
 * resolved, and that gate is what keeps hydration quiet: the roll below is
 * thrown on the server too, where there is no storage to read and the answer is
 * not the browser's. Until `/api/auth/me` comes back — which is the state the
 * server renders in and the state the browser hydrates in — the line is the
 * plain `plainGreeting`, identical on both sides. Once the account is in the
 * cache the very first render already has it, so switching back to this screen
 * picks up the held line without flashing the plain one first.
 */
function Greeting() {
  const { user, isPending } = useAuth()
  const [roll] = useState(stickyRoll)

  // The whole name, not the last word of it. A Vietnamese name is read in full,
  // and cutting it to the given name is a Western reading of the order.
  const name = user?.full_name?.trim() || user?.email?.split("@")[0] || null
  const partOfDay = vietnamPartOfDay()
  const line = isPending
    ? plainGreeting(partOfDay, name)
    : greetingFor(partOfDay, name, roll)

  return (
    <div className="flex items-center justify-center gap-3">
      <VisgniteMark className="h-[26px] w-[17px]" />
      {/* The one serif line in the product. Set at display size and one step
          brighter than body ink, because at this weight the serif thins out
          against the ground — see the note on the font in app/layout. */}
      <h2 className="min-w-0 font-serif text-[clamp(1.6rem,2.7vw,2.15rem)] font-normal leading-[1.1] tracking-[-0.01em] text-ink-display">
        {line}
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

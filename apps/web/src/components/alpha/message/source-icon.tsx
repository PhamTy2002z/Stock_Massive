"use client"

import { useState } from "react"

import { cn } from "@/lib/utils"

/**
 * One source's mark: its favicon, or two letters when there isn't one.
 *
 * **The image comes from our own origin, never from the source.** An `<img>`
 * pointed at `https://somenewspaper.com/favicon.ico` would tell whoever runs
 * that site which reader was looking at which answer, complete with their IP —
 * one request per row, on a row nobody asked to click. The backend fetches and
 * caches it instead, so the browser only ever talks to us.
 *
 * The letters are what the circle holds until an icon proves it can replace
 * them, and what it goes back to when none can. They render immediately rather
 * than after a failed request, so a row never reflows and never flashes empty
 * while one is in flight — plenty of sites serve no usable icon at all, which
 * makes the fallback an ordinary outcome rather than an error.
 *
 * Decorative in both surfaces that use it: the chip stack stands for "there
 * were sources" and the domain is spelled out in text beside the list version,
 * so an alt text here would only make a screen reader read every hostname
 * twice.
 */
export function SourceIcon({
  source,
  size = 19,
  className,
}: {
  source: string
  /** Diameter in px. 19 in the chip stack, 18 in the source list. */
  size?: number
  className?: string
}) {
  // Three states, not two. `idle` shows the letters while the request is in
  // flight; `loaded` hides them, because a favicon with a transparent
  // background would otherwise have two letters showing through the middle of
  // it; `failed` keeps them for good.
  const [status, setStatus] = useState<"idle" | "loaded" | "failed">("idle")
  const domain = source.trim()

  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className={cn(
        "relative flex flex-none items-center justify-center overflow-hidden rounded-full bg-surface-raised font-mono text-[0.55rem] text-ink-3",
        className,
      )}
    >
      {status !== "loaded" && initials(domain)}
      {domain !== "" && status !== "failed" && (
        <img
          src={`/api/alpha-desk/assets/favicon?domain=${encodeURIComponent(domain)}`}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("failed")}
          className="absolute inset-0 size-full object-cover"
        />
      )}
    </span>
  )
}

/**
 * Two upper-case letters from a hostname's own label.
 *
 * Derived from the string rather than assigned, so one domain always draws the
 * same two letters and a row does not change under the reader between renders
 * of the same tool call.
 */
export function initials(source: string): string {
  const label = source.trim().replace(/^www\./i, "").split(".")[0] ?? ""
  return label.slice(0, 2).toUpperCase() || "??"
}

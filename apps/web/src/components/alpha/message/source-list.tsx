"use client"

import { useState } from "react"

import type { ProgressSource, ProgressStep } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * The public pages an answer stood on, as a list and as an icon.
 *
 * One definition for both places they appear — inside the progress trail while
 * the Turn runs, and behind the source count under the finished answer. Two
 * copies of a row that links out to an untrusted page is two places for a
 * missing `rel` to hide.
 */
export function SourceList({
  sources,
  className,
}: {
  sources: ProgressSource[]
  className?: string
}) {
  if (sources.length === 0) return null

  return (
    <ul className={cn("grid gap-0.5 rounded-xl bg-surface-raised p-2", className)}>
      {sources.map((source) => (
        <li key={source.url}>
          <a
            href={source.url}
            target="_blank"
            // `noreferrer` as well as `noopener`: these are untrusted external
            // pages reached from an authenticated surface, and the referrer
            // would tell each of them which app sent the reader.
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-surface-menu"
          >
            <SourceIcon domain={source.domain} />
            <span className="min-w-0 flex-1 truncate text-[0.95rem] text-ink-2">
              {source.title}
            </span>
            <span className="shrink-0 text-meta text-ink-5">{source.domain}</span>
          </a>
        </li>
      ))}
    </ul>
  )
}

/**
 * One host's icon, fetched from that host, or its initial when it has none.
 *
 * Not through a favicon service: the reader is already being shown that page,
 * so its own server learning of the request adds nothing, where a third-party
 * icon endpoint would learn every domain shown to every reader. A host with no
 * `/favicon.ico` falls back to a letter, which is also what a blocked request
 * produces.
 */
export function SourceIcon({
  domain,
  ringed = false,
}: {
  domain: string
  ringed?: boolean
}) {
  const [failed, setFailed] = useState(false)

  if (!domain || failed) {
    return (
      <span
        aria-hidden
        className={cn(
          "grid size-[18px] shrink-0 place-items-center rounded bg-surface-menu text-[0.6rem] font-semibold uppercase text-ink-4",
          ringed && "ring-2 ring-background",
        )}
      >
        {(domain || "?").charAt(0)}
      </span>
    )
  }

  return (
    // A plain `img` rather than `next/image`: the host is whatever the search
    // returned, and `next/image` would need every one of them allowlisted in
    // `next.config.js` before a single icon rendered.
    <img
      src={`https://${domain}/favicon.ico`}
      alt=""
      aria-hidden
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn(
        "size-[18px] shrink-0 rounded bg-surface-raised object-contain",
        ringed && "ring-2 ring-background",
      )}
    />
  )
}

/** Up to three host icons, overlapped, as a picture of who answered. */
export function SourceCluster({ sources }: { sources: ProgressSource[] }) {
  const domains: string[] = []
  for (const source of sources) {
    if (source.domain && !domains.includes(source.domain)) domains.push(source.domain)
    if (domains.length === 3) break
  }
  if (domains.length === 0) return null

  return (
    <span className="flex items-center -space-x-1.5" aria-hidden>
      {domains.map((domain) => (
        <SourceIcon key={domain} domain={domain} ringed />
      ))}
    </span>
  )
}

/** Every public page the trail recorded, once each, in the order found. */
export function sourcesOf(steps: ProgressStep[]): ProgressSource[] {
  const found: ProgressSource[] = []
  const seen = new Set<string>()
  for (const step of steps) {
    for (const source of step.detail?.sources ?? []) {
      if (seen.has(source.url)) continue
      seen.add(source.url)
      found.push(source)
    }
  }
  return found
}

"use client"

import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { PROGRESS_COPY } from "@/lib/alpha-desk/copy"
import type { ProgressSource, SourceAndMethod } from "@/lib/alpha-desk/types"
import { SourceIcon } from "./source-list"
import { SourcesAndMethods } from "./sources-and-methods"

/**
 * Every page the answer stood on, in a panel beside the conversation.
 *
 * A drawer rather than an inline expansion because the list is *reference*, not
 * part of the answer's reading order: fifteen titled excerpts unfolding between
 * an answer and the composer push the next question off screen, where a panel
 * lets the reader keep the answer and its evidence side by side.
 *
 * Each row shows what the search result itself said — host, publication date,
 * title, excerpt, and when it was retrieved. All of it arrived on the wire from
 * the backend (`docs/adr/0020`); nothing here derives a fact the renderer would
 * then appear to vouch for. A row whose result offered no excerpt or date simply
 * has none.
 *
 * The figure-level provenance (`SourcesAndMethods`) rides in the same drawer,
 * under the pages: one control under the answer, one place everything it stood
 * on can be inspected.
 */
export function SourceDrawer({
  sources,
  rows,
  children,
}: {
  sources: ProgressSource[]
  rows: SourceAndMethod[]
  /** The trigger — the count-with-faces button under the answer. */
  children: React.ReactNode
}) {
  return (
    <DialogPrimitive.Root>
      <DialogPrimitive.Trigger asChild>{children}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <DialogPrimitive.Content
          // No description: the title says everything the panel is, and Radix
          // warns rather than renders when the id points at nothing.
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[480px] flex-col border-l border-border bg-background shadow-2xl focus:outline-none"
        >
          <header className="flex items-center justify-between gap-3 px-5 pb-3 pt-5">
            <DialogPrimitive.Title className="text-[1.05rem] font-semibold text-ink-display">
              {PROGRESS_COPY.drawerTitle(sources.length)}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label={PROGRESS_COPY.drawerClose}
              className="grid size-7 shrink-0 place-items-center rounded-lg text-ink-5 transition-colors hover:bg-surface-raised hover:text-ink-2"
            >
              <X className="size-4" strokeWidth={1.8} />
            </DialogPrimitive.Close>
          </header>

          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 pb-6">
            <ul className="grid gap-5 pt-1">
              {sources.map((source) => (
                <SourceRow key={source.url} source={source} />
              ))}
            </ul>
            {rows.length > 0 && <SourcesAndMethods rows={rows} className="mt-5" />}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

/** One page: who published it and when, what it is called, what it claims. */
function SourceRow({ source }: { source: ProgressSource }) {
  const published = formatDay(source.published_at)
  const retrieved = formatDay(source.retrieved_at)

  return (
    <li className="grid gap-1">
      <p className="flex min-w-0 items-center gap-2 text-meta text-ink-5">
        <SourceIcon domain={source.domain} />
        <span className="truncate">{source.domain}</span>
        {published !== null && (
          <>
            <span aria-hidden>·</span>
            <span className="shrink-0">{published}</span>
          </>
        )}
      </p>
      <a
        href={source.url}
        target="_blank"
        // `noreferrer` as well as `noopener`: an untrusted external page reached
        // from an authenticated surface, and the referrer would tell it which
        // app sent the reader.
        rel="noopener noreferrer"
        className="w-fit font-semibold leading-snug text-ink-display hover:underline"
      >
        {source.title}
      </a>
      {source.snippet && (
        <p className="line-clamp-2 text-meta leading-relaxed text-ink-4">{source.snippet}</p>
      )}
      {retrieved !== null && (
        <p className="text-meta text-ink-5">{PROGRESS_COPY.updatedAt(retrieved)}</p>
      )}
    </li>
  )
}

/**
 * A timestamp as the reader's calendar says it, or nothing.
 *
 * Nothing — not the raw string — when it does not parse: an unparseable value on
 * screen would be the wire format leaking, and absence is what every other
 * missing fact in this drawer already means.
 */
function formatDay(iso: string | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat("vi-VN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date)
}

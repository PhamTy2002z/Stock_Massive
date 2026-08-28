"use client"

/**
 * The Signal Desk's own chrome: one tab per picture, and the way out to a file.
 *
 * **Every desk view in the conversation keeps a tab.** The surface used to hold one
 * artifact id, so a Thread that ran three Studies could show only the newest and
 * the first two became unreachable the moment the third arrived — the reader had
 * watched them being drawn and then had nowhere to click. A strip is the whole
 * point of the redesign.
 *
 * **"Nguồn" is the last tab, not a second panel.** What an answer rested on and
 * what it was drawn from are the same question asked from two sides, and a
 * reader comparing a figure with its source should not have to give up half the
 * screen to see the other. It carries a different glyph and no close control:
 * it is not a desk view, and there is nothing to close.
 *
 * **There is no "Lưu".** The design draws one beside the export and there is no
 * endpoint behind it — the sidebar's "Báo cáo đã lưu" is still "Sắp ra mắt". A
 * control that swallowed the press would tell a reader their work was kept.
 */

import { Download, Link2, PanelTop, X } from "lucide-react"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import type { SignalDeskTab } from "@/components/shell/shell-state"
import { cn } from "@/lib/utils"

export function SignalDeskHeader({
  deskViews,
  activeDeskViewId,
  showingSources,
  canExport,
  onOpenDeskView,
  onCloseDeskView,
  onOpenSources,
  onShare,
  onExport,
}: {
  deskViews: SignalDeskTab[]
  activeDeskViewId: string | null
  showingSources: boolean
  /** False until the numbers are in the browser: there is nothing to write yet. */
  canExport: boolean
  onOpenDeskView: (artifactId: string) => void
  onCloseDeskView: (artifactId: string) => void
  onOpenSources: () => void
  onShare: () => void
  onExport: () => void
}) {
  return (
    <header className="flex flex-none items-center gap-2 px-3.5 pt-2.5">
      <div
        role="tablist"
        aria-label="Signal Desk"
        className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto scrollbar-thin"
      >
        {deskViews.map((deskView) => {
          const active = !showingSources && deskView.artifactId === activeDeskViewId
          return (
            <div key={deskView.artifactId} role="presentation" className="relative flex-none">
              <button
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onOpenDeskView(deskView.artifactId)}
                className={cn(TAB, "max-w-[220px] pr-7", active ? TAB_ON : TAB_OFF)}
              >
                <PanelTop className="size-[13px] flex-none" strokeWidth={1.7} aria-hidden />
                <span className="min-w-0 truncate">{deskView.title}</span>
              </button>
              {/* A sibling rather than a child: a button inside a button is not
                  something a browser will lay out, and the close affordance has
                  to be reachable without selecting the tab it sits on. */}
              <button
                type="button"
                aria-label={`Close ${deskView.title}`}
                onClick={() => onCloseDeskView(deskView.artifactId)}
                className="absolute right-1.5 top-1/2 flex size-[18px] -translate-y-1/2 items-center justify-center rounded text-ink-6 transition-colors hover:bg-foreground/10 hover:text-ink-2"
              >
                <X className="size-3" strokeWidth={2} aria-hidden />
              </button>
            </div>
          )
        })}

        <button
          type="button"
          role="tab"
          aria-selected={showingSources}
          onClick={onOpenSources}
          className={cn(TAB, "flex-none", showingSources ? TAB_ON : TAB_OFF)}
        >
          <Link2 className="size-[13px] flex-none" strokeWidth={1.7} aria-hidden />
          <span>{SIGNAL_DESK_COPY.sources}</span>
        </button>
      </div>

      <div className="flex flex-none items-center gap-2">
        <button
          type="button"
          onClick={onShare}
          className="shrink-0 whitespace-nowrap rounded-[9px] border border-border bg-foreground/[0.04] px-3.5 py-1.5 text-control text-ink-2 transition-colors hover:bg-foreground/[0.08]"
        >
          Chia sẻ
        </button>
        <button
          type="button"
          onClick={onExport}
          disabled={!canExport}
          // The one solid shape in this header, and it lifts on hover: it is the
          // only control here that leaves the application, so it is the only one
          // that acknowledges the press before the browser takes over.
          className="inline-flex items-center gap-1.5 rounded-full bg-foreground px-3 py-1.5 text-meta font-medium text-background transition-[transform,filter] duration-150 hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-40 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
        >
          <Download className="size-3.5" strokeWidth={1.6} aria-hidden />
          {SIGNAL_DESK_COPY.export}
        </button>
      </div>
    </header>
  )
}

/** The folder-tab shape: square-cut at the bottom, where the content meets it. */
const TAB =
  "flex items-center gap-1.5 rounded-t-lg px-3 py-[0.42rem] text-[0.83rem] transition-colors"
const TAB_ON = "bg-surface-raised text-ink-1"
const TAB_OFF = "text-ink-6 hover:text-ink-3"

"use client"

/**
 * The Signal Desk: the workspace beside the conversation.
 *
 * The proportions are inverted from what this panel used to be. It began as a
 * 408px inspector squeezed against the right edge, which is the right shape for
 * a list of citations and the wrong one for a chart with an axis: the picture
 * the answer was written about ended up the smallest thing on screen. So the
 * **chat column is now the fixed one** — 420px and a hairline — and the desk
 * takes what is left. The seam between them is still draggable; what it moves is
 * the conversation's width, because the desk is defined as the remainder.
 *
 * It opens because the reader switched it on, not because an answer produced
 * something. That distinction is the whole of the mode: a desk view arriving with
 * the desk off leaves a card in the transcript, and the layout changes only when
 * a person asks it to.
 *
 * The market lenses that used to live here (indices, VN30, sector performance,
 * stock detail, price history, news sources) went with the market surfaces on
 * 2026-08-25. What a chat lane needs is what is left: the pictures, and the
 * citations behind the answer in view — the last tab in the same strip, because
 * a reader comparing a figure with its source should not have to choose which
 * half of the screen to give up.
 */

import { useCallback } from "react"
import dynamic from "next/dynamic"
import { X } from "lucide-react"

import { SignalDeskBuilding } from "@/components/signal-desk/signal-desk-building"
import { QueryErrorBoundary } from "@/components/providers/query-error-boundary"
import { exportArtifact } from "@/components/signal-desk/signal-desk-export"
import { SignalDeskHeader } from "@/components/signal-desk/signal-desk-header"
import { useArtifact } from "@/components/signal-desk/use-artifact"
import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { IconButton } from "./primitives"
import {
  chatColumnWidth,
  isCompact,
  maxChatWidth,
  MIN_CHAT_WIDTH,
  useChatColumnDrag,
  useShell,
} from "./shell-state"
import { SourcesTab } from "./sources-tab"

/**
 * The desk view panel arrives with the chart runtime behind it.
 *
 * Loaded on demand rather than with the shell: recharts is the largest thing in
 * this application by some way, and most conversations never draw anything. A
 * reader who switches the desk on is already waiting on a model call, which is
 * the moment there is room to fetch a chart library.
 */
const SignalDeskPanel = dynamic(
  () => import("@/components/signal-desk/signal-desk-panel").then((m) => m.SignalDeskPanel),
  {
    ssr: false,
    loading: () => (
      <div
        aria-hidden
        className="h-32 animate-pulse rounded-xl border border-hairline bg-surface-raised"
      />
    ),
  },
)

export function Inspector() {
  const { state, dispatch, panelWidth } = useShell()
  const desk = useDesk()
  const onDrag = useChatColumnDrag()

  const compact = isCompact(state.viewport)
  const showingSources = state.inspector !== null && state.inspector !== "deskView"
  const activeDeskViewId = showingSources ? null : state.deskViewArtifactId

  // The same row the panel under this draws, under the same freeze — one query
  // key, so naming the tab and filling the file cost no second request.
  const artifact = useArtifact(activeDeskViewId)

  const onTitle = useCallback(
    (artifactId: string, title: string) =>
      dispatch({ type: "signal-desk-title", artifactId, title }),
    [dispatch],
  )

  if (state.inspector === null) return null

  const chatWidth = chatColumnWidth(state)
  // The build state and the composer's pill are one fact read in two places.
  const building = desk.building

  return (
    <aside
      role="complementary"
      aria-label={SIGNAL_DESK_COPY.name}
      style={{ width: compact ? "100%" : panelWidth }}
      className={cn(
        "fixed right-0 top-0 z-20 flex h-dvh min-w-0 flex-col border-l border-border bg-background",
        compact ? "shadow-2xl" : "",
      )}
    >
      {!compact && (
        <div
          role="separator"
          tabIndex={0}
          aria-orientation="vertical"
          aria-label="Resize chat column"
          aria-valuemin={MIN_CHAT_WIDTH}
          aria-valuemax={maxChatWidth(state)}
          aria-valuenow={chatWidth}
          onPointerDown={onDrag}
          onKeyDown={(event) => {
            // The seam is the chat column's right edge, so left narrows the
            // conversation and right widens it — the direction the handle moves.
            let width = chatWidth
            const step = event.shiftKey ? 40 : 12
            if (event.key === "ArrowLeft") width = chatWidth - step
            if (event.key === "ArrowRight") width = chatWidth + step
            if (event.key === "Home") width = MIN_CHAT_WIDTH
            if (event.key === "End") width = maxChatWidth(state)
            if (width !== chatWidth) {
              event.preventDefault()
              dispatch({ type: "resize-chat", width })
            }
          }}
          className="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize bg-transparent hover:bg-border/60"
        />
      )}

      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <SignalDeskHeader
            deskViews={state.deskViews}
            activeDeskViewId={activeDeskViewId}
            showingSources={showingSources}
            canExport={artifact.data !== undefined}
            onOpenDeskView={(artifactId) => dispatch({ type: "open-desk-view", artifactId })}
            onCloseDeskView={(artifactId) => dispatch({ type: "close-desk-view", artifactId })}
            onOpenSources={() => dispatch({ type: "open-inspector", tab: "sources" })}
            onShare={() => dispatch({ type: "overlay", overlay: "share" })}
            onExport={() => {
              if (artifact.data !== undefined) exportArtifact(artifact.data)
            }}
          />
        </div>
        <div className="flex-none pr-2 pt-3">
          <IconButton
            label="Close Signal Desk"
            onClick={() => dispatch({ type: "close-inspector" })}
          >
            <X className="size-4" />
          </IconButton>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto border-t border-hairline scrollbar-thin">
        <div className="mx-auto max-w-[1120px] px-6 pb-[60px] pt-5">
          <Body
            showingSources={showingSources}
            building={building}
            activeDeskViewId={activeDeskViewId}
            signalDesk={state.signalDesk}
            frozen={state.dragging}
            onTitle={onTitle}
          />
        </div>
      </div>
    </aside>
  )
}

/**
 * What fills the column, in the order the reader's attention is owed.
 *
 * The build state outranks a finished desk view deliberately. A Study running is
 * the newest thing the reader asked for, and a pane that kept the previous
 * picture up would answer a question nobody is still asking — the tab strip is
 * how the earlier one stays reachable.
 */
function Body({
  showingSources,
  building,
  activeDeskViewId,
  signalDesk,
  frozen,
  onTitle,
}: {
  showingSources: boolean
  building: string | null
  activeDeskViewId: string | null
  signalDesk: boolean
  frozen: boolean
  onTitle: (artifactId: string, title: string) => void
}) {
  if (showingSources) return <SourcesTab />
  if (building !== null) return <SignalDeskBuilding label={building} />
  if (activeDeskViewId === null) {
    // Two different emptinesses. A desk switched on and waiting is a state the
    // reader put the surface into, and it says what will fill it; a desk with
    // nothing in the conversation at all is a fact about the conversation.
    return (
      <p className="text-meta text-muted-foreground">
        {signalDesk ? SIGNAL_DESK_COPY.empty : SIGNAL_DESK_COPY.noDeskView}
      </p>
    )
  }
  // The chart runtime arrives over the network, and networks fail.
  //
  // `dynamic()` has a `loading` state and no failed one: a chunk that 404s
  // after a deploy, or on a connection that dropped between opening the desk
  // and fetching recharts, rejects the import and throws on render. With
  // nothing to catch it the throw unmounts the inspector — the tab stays
  // selected and its contents simply vanish, which reads as the panel being
  // empty rather than broken. The boundary turns that into a named failure
  // with the retry that actually fixes it, since the second import is a fresh
  // request for the same chunk.
  return (
    <QueryErrorBoundary compact>
      <SignalDeskPanel artifactId={activeDeskViewId} frozen={frozen} onTitle={onTitle} />
    </QueryErrorBoundary>
  )
}

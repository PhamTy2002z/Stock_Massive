"use client";

/**
 * The right-hand pane: a source drawer in Chat, or the Signal Desk workspace.
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
 * 2026-08-25. Chat keeps citations in a narrow supporting drawer. Once Signal
 * Desk is on, the same citations become a sibling toggle in its header, because
 * a reader comparing a figure with its source should not have to leave the
 * workspace.
 */

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { X } from "lucide-react";

import { SignalDeskBuilding } from "@/components/signal-desk/signal-desk-building";
import { QueryErrorBoundary } from "@/components/providers/query-error-boundary";
import { exportArtifact } from "@/components/signal-desk/signal-desk-export";
import { SignalDeskEmpty } from "@/components/signal-desk/signal-desk-empty";
import { SignalDeskHeader } from "@/components/signal-desk/signal-desk-header";
import { useArtifact } from "@/components/signal-desk/use-artifact";
import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy";
import { cn } from "@/lib/utils";

import { useDesk } from "./desk-state";
import { IconButton } from "./primitives";
import {
  chatColumnWidth,
  isCompact,
  maxChatWidth,
  MIN_CHAT_WIDTH,
  ShellSnapshot,
  useChatColumnDrag,
  useShell,
  type ShellApi,
} from "./shell-state";
import { SourcesTab } from "./sources-tab";

/**
 * The desk view panel arrives with the chart runtime behind it.
 *
 * Loaded on demand rather than with the shell: recharts is the largest thing in
 * this application by some way, and most conversations never draw anything. A
 * reader who switches the desk on is already waiting on a model call, which is
 * the moment there is room to fetch a chart library.
 */
const SignalDeskPanel = dynamic(
  () =>
    import("@/components/signal-desk/signal-desk-panel").then(
      (m) => m.SignalDeskPanel,
    ),
  {
    ssr: false,
    loading: () => (
      <div
        aria-hidden
        className="h-32 animate-pulse rounded-xl border border-hairline bg-surface-raised"
      />
    ),
  },
);

/** How long the pane takes to leave — the same clock as `duration-panel`. */
const PANEL_LEAVE_MS = 420;

function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false)
  );
}

/**
 * The pane, kept on screen for as long as it takes to slide shut.
 *
 * The state that opens it is one boolean, and a boolean has no "closing". Drawn
 * straight from it, the pane vanished on the frame the desk went off while the
 * conversation beside it took 420ms to widen — a blank strip, then a jump. So
 * closing is a third phase here: the pane keeps drawing from the shell as it
 * was, slides out on the chat column's own curve, and unmounts when the slide
 * ends (or when a timer says it should have — `animationend` does not fire
 * everywhere, and a pane that never went away would be worse than one that
 * went a frame early).
 *
 * The phase is derived during render rather than in an effect on purpose:
 * an effect runs after the commit, and that commit would have painted nothing
 * where the pane was. Under reduced motion there is no slide to wait for.
 */
export function Inspector() {
  const shell = useShell();
  const open = shell.state.inspector !== null;
  const [phase, setPhase] = useState<"open" | "leaving" | "closed">(
    open ? "open" : "closed",
  );
  const [last, setLast] = useState<ShellApi>(shell);

  if (open) {
    if (phase !== "open") setPhase("open");
    if (last !== shell) setLast(shell);
  } else if (phase === "open") {
    setPhase(reducedMotion() ? "closed" : "leaving");
  }

  const onGone = useCallback(() => setPhase("closed"), []);

  if (!open && phase !== "leaving") return null;
  // One tree in both phases. Wrapping only the leaving pane would make React
  // tear the open one down and mount a fresh copy to slide out — a remount
  // the reader would see as the board redrawing itself on its way off.
  return (
    <ShellSnapshot value={open ? shell : last}>
      <Pane leaving={!open} onGone={onGone} />
    </ShellSnapshot>
  );
}

function Pane({ leaving, onGone }: { leaving: boolean; onGone: () => void }) {
  const { state, dispatch, panelWidth } = useShell();
  const desk = useDesk();
  const onDrag = useChatColumnDrag();

  // The fallback clock for a slide whose `animationend` never arrives.
  useEffect(() => {
    if (!leaving) return;
    const timer = window.setTimeout(onGone, PANEL_LEAVE_MS + 60);
    return () => window.clearTimeout(timer);
  }, [leaving, onGone]);

  // Warm the chart runtime the moment the desk is switched on, while the pane
  // is still showing its empty state and the reader is typing a question. By
  // the time a board arrives the chunk is in cache, and the skeleton the
  // dynamic import would otherwise show for it never has to.
  useEffect(() => {
    if (!state.signalDesk) return;
    void import("@/components/signal-desk/signal-desk-panel");
  }, [state.signalDesk]);

  const compact = isCompact(state.viewport);
  const showingSources =
    state.inspector !== null && state.inspector !== "deskView";
  const chatSources = showingSources && !state.signalDesk;
  const activeDeskViewId = showingSources ? null : state.deskViewArtifactId;

  // The same row the panel under this draws, under the same freeze — one query
  // key, so naming the tab and filling the file cost no second request.
  const artifact = useArtifact(activeDeskViewId);

  const onTitle = useCallback(
    (artifactId: string, title: string) =>
      dispatch({ type: "signal-desk-title", artifactId, title }),
    [dispatch],
  );

  const chatWidth = chatColumnWidth(state);
  // The build state and the composer's pill are one fact read in two places.
  const building = desk.building;

  return (
    <aside
      role="complementary"
      aria-label={chatSources ? SIGNAL_DESK_COPY.sources : SIGNAL_DESK_COPY.name}
      aria-hidden={leaving || undefined}
      style={{ width: compact ? "100%" : panelWidth }}
      onAnimationEnd={(event) => {
        if (leaving && event.target === event.currentTarget) onGone();
      }}
      className={cn(
        "fixed right-0 top-0 z-20 flex h-dvh min-w-0 flex-col bg-background will-change-transform",
        compact
          ? "shadow-2xl"
          : chatSources
            ? "border-l border-border"
            : "py-2.5 pr-2.5",
        // The width moves with the room — folding the list, resizing the
        // window — on the same clock the chat column's padding does, so the
        // seam between the two never opens for a frame. A drag is the one
        // time the width must follow the pointer exactly.
        state.dragging
          ? "transition-none"
          : "transition-[width] duration-panel ease-panel",
        leaving
          ? "pointer-events-none animate-vg-panel-out"
          : "motion-safe:animate-vg-panel-in",
      )}
    >
      {!compact && !chatSources && (
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
            let width = chatWidth;
            const step = event.shiftKey ? 40 : 12;
            if (event.key === "ArrowLeft") width = chatWidth - step;
            if (event.key === "ArrowRight") width = chatWidth + step;
            if (event.key === "Home") width = MIN_CHAT_WIDTH;
            if (event.key === "End") width = maxChatWidth(state);
            if (width !== chatWidth) {
              event.preventDefault();
              dispatch({ type: "resize-chat", width });
            }
          }}
          className="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize bg-transparent hover:bg-border/60"
        />
      )}

      {/* The desk is a raised card inset from the window edge rather than a
          column ruled off from the conversation: no seam between the two, and
          the card's own shape says where the picture begins. */}
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-hidden",
          chatSources ? "bg-background" : "bg-surface-raised",
          compact || chatSources ? "" : "rounded-[18px]",
        )}
      >
        {chatSources ? (
          <header className="flex flex-none items-center justify-between border-b border-border px-4 py-2.5">
            <h2 className="text-sm font-medium text-ink-1">{SIGNAL_DESK_COPY.sources}</h2>
            <IconButton
              label="Đóng nguồn"
              onClick={() => dispatch({ type: "close-inspector" })}
            >
              <X className="size-4" />
            </IconButton>
          </header>
        ) : (
          <div className="flex items-start gap-1">
            <div className="min-w-0 flex-1">
              <SignalDeskHeader
                boards={state.deskBoards}
                pinned={state.deskPinned}
                activeDeskViewId={activeDeskViewId}
                showingSources={showingSources}
                canExport={artifact.data !== undefined}
                menuOpen={state.overlay === "board-menu"}
                onOpenDeskView={(artifactId) =>
                  dispatch({ type: "open-desk-view", artifactId })
                }
                onOpenSources={() =>
                  dispatch({ type: "open-inspector", tab: "sources" })
                }
                onToggleMenu={(open) =>
                  dispatch({
                    type: "overlay",
                    overlay: open ? "board-menu" : null,
                  })
                }
                onTogglePin={(artifactId, pinned) =>
                  dispatch({ type: "pin-desk-view", artifactId, pinned })
                }
                onOpenSwitcher={() =>
                  dispatch({ type: "overlay", overlay: "boards" })
                }
                onShare={() => dispatch({ type: "overlay", overlay: "share" })}
                onExport={() => {
                  if (artifact.data !== undefined) exportArtifact(artifact.data);
                }}
              />
            </div>
            {/* A hairline between the header's own controls and the way out.
                Closing the desk is not one of the things the reader does *to* the
                board, and without a rule the X reads as the fourth item in that
                row. */}
            <div className="flex flex-none items-center gap-1.5 pr-2 pt-3">
              <span
                aria-hidden
                className="block h-4 w-px flex-none bg-foreground/[0.1]"
              />
              <IconButton
                label="Close Signal Desk"
                onClick={() => dispatch({ type: "close-inspector" })}
              >
                <X className="size-4" />
              </IconButton>
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          {/* `min-h-full` and a column, so the empty state's own `m-auto` has a
              full-height box to centre in. Content that fills the pane stacks
              from the top exactly as it did before: a flex column with one
              child is block layout with extra steps. */}
          {/* Keyed on what the pane is showing, so a change of subject —
              sources to board, build state to picture — fades the new one in
              rather than swapping it under the reader between two frames. */}
          <div
            key={bodyKey(showingSources, building, activeDeskViewId)}
            className="mx-auto flex min-h-full max-w-[1120px] flex-col px-6 pb-[60px] pt-5 motion-safe:animate-vg-fade-in"
          >
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
      </div>
    </aside>
  );
}

/** One key per subject the pane can show; the fade above restarts on change. */
function bodyKey(
  showingSources: boolean,
  building: string | null,
  activeDeskViewId: string | null,
): string {
  if (showingSources) return "sources";
  if (building !== null) return "building";
  return activeDeskViewId ?? "empty";
}

/**
 * What fills the column, in the order the reader's attention is owed.
 *
 * The build state outranks a finished desk view deliberately. A Study running is
 * the newest thing the reader asked for, and a pane that kept the previous
 * picture up would answer a question nobody is still asking — the header's list
 * is how the earlier one stays reachable.
 */
function Body({
  showingSources,
  building,
  activeDeskViewId,
  signalDesk,
  frozen,
  onTitle,
}: {
  showingSources: boolean;
  building: string | null;
  activeDeskViewId: string | null;
  signalDesk: boolean;
  frozen: boolean;
  onTitle: (artifactId: string, title: string) => void;
}) {
  if (showingSources) return <SourcesTab />;
  if (building !== null) return <SignalDeskBuilding label={building} />;
  if (activeDeskViewId === null) {
    // Two different emptinesses, and they earn different surfaces. A desk
    // switched on and waiting is a state the reader put this pane into, so it
    // gets the full opening — the shape of a board, what will fill it, what it
    // can be asked. A desk switched *off* with no picture in the conversation is
    // a fact about the conversation rather than an invitation, and drawing a
    // ghost board for it would advertise a mode the reader has not chosen.
    if (signalDesk) return <SignalDeskEmpty />;
    return (
      <p className="text-meta text-muted-foreground">
        {SIGNAL_DESK_COPY.noDeskView}
      </p>
    );
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
      <SignalDeskPanel
        artifactId={activeDeskViewId}
        frozen={frozen}
        onTitle={onTitle}
      />
    </QueryErrorBoundary>
  );
}

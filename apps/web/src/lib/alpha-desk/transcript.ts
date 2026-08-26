/**
 * What the transcript shows, given a canonical Thread and one live Turn.
 *
 * The two halves arrive from different places and mean different things: the
 * Thread is a TanStack Query resource and is history, and the live Turn is a
 * reducer's draft and is not history yet. Deciding between them in JSX would
 * put the one rule that matters — **the canonical message replaces the draft,
 * it never joins it** — inside a component, where the only way to check it is
 * to render.
 *
 * So this is a pure projection. It answers one question: what rows are on
 * screen right now, in order.
 */

import type { LivePhase, LiveTurn } from "./live-turn"
import { readCanvases, readStrings, readThoughts, readToolCalls } from "./read-content"
import type {
  CanvasAnnouncement,
  FlagReason,
  Thought,
  ThreadMessage,
  ToolCall,
} from "./types"

export interface UserEntry {
  kind: "user"
  key: string
  text: string
  /** Sent, and the create has not come back yet. Never a second copy of a committed one. */
  pending: boolean
}

/** One canonical assistant message, read defensively because it is stored JSONB. */
export interface AssistantView {
  /**
   * The reply, as Markdown the message stored.
   *
   * The message also stores `text`, which is every piece of prose the Turn
   * produced including its narration — that one is what the model reads next
   * Turn. This is the half the reader is shown, and it falls back to `text` for
   * a message written before the two were told apart.
   */
  text: string
  /** The calls the Turn made, as the message stored them. Empty on most answers. */
  toolCalls: ToolCall[]
  /** What the Turn said on the way to the answer. Empty on most answers. */
  thoughts: Thought[]
  /**
   * The pictures this answer was written about. Empty on most answers.
   *
   * Ids and titles only. The numbers behind one are fetched by the panel that
   * draws it, so a transcript scrolled past a dozen answers carries no heatmaps
   * with it.
   */
  canvases: CanvasAnnouncement[]
  /**
   * Questions the model offered as sensible next steps, or none.
   *
   * Stored on the message rather than derived, because they were written in
   * the same breath as the answer and about the answer that was actually
   * given. Regenerating produces a different answer and different suggestions.
   */
  followUps: string[]
  /** How long the Turn took, for the line that says so. Zero when unrecorded. */
  elapsedMs: number
  /**
   * Whether the Turn behind this answer ran to completion.
   *
   * The text of a Turn that hit its deadline looks exactly like the text of one
   * that finished, so this is the only thing that can tell the reader they are
   * holding a fragment. Read from a `status` the message may carry and defaults
   * to complete without one: an answer in the transcript is one the backend
   * wrote in a terminal transaction, and labelling every message that predates
   * the key as *stopped* would be the louder mistake.
   */
  completed: boolean
}

export interface AssistantEntry {
  kind: "assistant"
  key: string
  messageId: number
  view: AssistantView
  /**
   * The reason this message is already flagged with, or null.
   *
   * Projected here rather than read in the component, so that the one rule
   * worth stating — **only a canonical assistant message can be flagged** — is
   * expressed by which entry kind carries the field. A draft has no message id
   * yet and a user's own question is not what the action is about, so neither
   * has anywhere to put it.
   */
  flaggedReason: FlagReason | null
  /**
   * Whether the reader already marked this answer helpful.
   *
   * A boolean rather than the stamp, because nothing on this surface renders
   * *when* the mark was left — only that it is there. Projected onto the same
   * entry kind as the flag, for the same reason: a draft has no message id to
   * mark, and a question is not what the verdict is about.
   */
  helpful: boolean
}

export interface DraftEntry {
  kind: "draft"
  key: string
  /**
   * The answer as far as it should be on screen. Grows by whole words, never
   * re-ordered — which is not the same as everything that has arrived, because
   * prose reaches the browser faster than a reader can be shown it.
   */
  text: string
  /**
   * Whether the timeline still reads as running.
   *
   * Carried rather than derived from `text`, because it is a fact about what has
   * *arrived*: the work is over the moment there is a reply to read, and at that
   * moment none of the reply is on screen yet.
   */
  working: boolean
  toolCalls: ToolCall[]
  thoughts: Thought[]
  /** The canvases announced so far, as the stream has reported them. */
  canvases: CanvasAnnouncement[]
  elapsedMs: number
  phase: LivePhase
  terminalReason: string | null
}

/**
 * One Analysis the user opened, sitting where they opened it.
 *
 * An Analysis is an artifact rather than a page, so opening one puts a row in
 * the transcript instead of navigating away from it. The row carries only the
 * pair that identifies the Analysis; the artifact reads itself, because a
 * payload threaded through this projection would be a second copy of a resource
 * TanStack Query already owns.
 */
export interface AnalysisEntry {
  kind: "analysis"
  key: string
  symbol: string
  tradingDay: string
}

export type TranscriptEntry = UserEntry | AssistantEntry | DraftEntry | AnalysisEntry

/** An Analysis the user opened, and where in the conversation they were. */
export interface OpenedAnalysis {
  symbol: string
  tradingDay: string
  /**
   * The `seq` of the newest message when it was opened; 0 for an empty Thread.
   *
   * An artifact opened before a question belongs above that question, and one
   * opened after the answer belongs under it. Anchoring to a sequence is what
   * keeps that true as the Thread grows underneath — appending them all at the
   * end would reorder the evening's reading every time an answer landed.
   */
  afterSeq: number
}

export interface TranscriptInput {
  /** The Thread on screen. A draft belonging to another one is not shown. */
  threadId: string | null
  messages: ThreadMessage[]
  live: LiveTurn
  /** What the user just sent, while the create is still in flight. */
  pendingUserText: string | null
  /** Analyses opened into this Thread, in the order they were opened. */
  openedAnalyses?: OpenedAnalysis[]
  /**
   * How much of the live Turn is on screen, when something is pacing it.
   *
   * A Turn's prose reaches the browser faster than a reader can be shown it
   * (`use-answer-reveal`), so what the draft draws is a prefix, and the Turn is
   * over well before the last word of it has arrived. Two consequences, and both
   * are decided here rather than in a component:
   *
   * The draft's `text` and `working` come from this rather than from `live`.
   *
   * And **the canonical message waits.** Handing over on the terminal event
   * alone would cut the arrival off: that message draws the same text with no
   * cadence, so every word still waiting would appear at once. So it is held
   * back rather than drawn beside the draft.
   *
   * Absent means nothing is pacing: the draft shows everything received, and its
   * canonical twin replaces it as soon as it lands.
   */
  reveal?: DraftReveal
}

/** What a pacer says about the answer on screen (`use-answer-reveal`). */
export interface DraftReveal {
  text: string
  working: boolean
  handedOver: boolean
}

export function buildTranscript(input: TranscriptInput): TranscriptEntry[] {
  const ordered = [...input.messages].sort((left, right) => left.seq - right.seq)
  const entries: TranscriptEntry[] = []
  const pendingArtifacts = [...(input.openedAnalyses ?? [])]
  const reveal = input.reveal ?? received(input.live)
  const drafting = showsDraft(input, ordered, reveal)
  // The one message the draft is still standing in for. Skipped rather than
  // drawn, because the draft below is the same answer still arriving.
  const heldBack = drafting && !reveal.handedOver ? input.live.messageId : null

  /** Every artifact anchored at or before this point in the conversation. */
  function flushArtifactsBefore(seq: number | null): void {
    while (
      pendingArtifacts.length > 0 &&
      (seq === null || pendingArtifacts[0].afterSeq < seq)
    ) {
      const opened = pendingArtifacts.shift()!
      entries.push({
        kind: "analysis",
        key: `analysis-${opened.symbol}-${opened.tradingDay}`,
        symbol: opened.symbol,
        tradingDay: opened.tradingDay,
      })
    }
  }

  for (const message of ordered) {
    flushArtifactsBefore(message.seq)
    if (message.role === "user") {
      entries.push({
        kind: "user",
        key: `message-${message.id}`,
        text: textOf(message),
        pending: false,
      })
    } else if (message.role === "assistant" && message.id !== heldBack) {
      // `summary` is context compaction. It is a fact about what the model was
      // handed, not about what the user said or was told, so it is not a row.
      entries.push({
        kind: "assistant",
        key: `message-${message.id}`,
        messageId: message.id,
        view: assistantView(message),
        flaggedReason: message.flagged_reason ?? null,
        helpful: message.helpful_at !== null && message.helpful_at !== undefined,
      })
    }
  }

  flushArtifactsBefore(null)

  const last = ordered[ordered.length - 1]
  const committed =
    last !== undefined && last.role === "user" && textOf(last) === input.pendingUserText
  if (input.pendingUserText !== null && !committed) {
    entries.push({
      kind: "user",
      key: "pending-user",
      text: input.pendingUserText,
      pending: true,
    })
  }

  if (drafting) {
    entries.push({
      kind: "draft",
      key: `draft-${input.live.turnId}`,
      text: reveal.text,
      working: reveal.working,
      toolCalls: input.live.toolCalls,
      thoughts: input.live.thoughts,
      canvases: input.live.canvases,
      elapsedMs: input.live.elapsedMs,
      phase: input.live.phase,
      terminalReason: input.live.terminalReason,
    })
  }

  return entries
}

/**
 * Whether the draft is still the newest thing on screen.
 *
 * It stops being so the moment its canonical message is in the Thread — that
 * message is the same answer as the draft, and showing both would print it
 * twice. Until then the draft stands, including when it ended with nothing: a
 * Turn that failed still owes the user a status and a retry.
 *
 * A reveal still writing the answer out postpones exactly that swap and nothing
 * else: the draft is still the newest thing on screen while it is the only copy
 * of the answer that is arriving rather than already there.
 */
function showsDraft(
  input: TranscriptInput,
  ordered: ThreadMessage[],
  reveal: DraftReveal,
): boolean {
  const { live } = input
  if (live.turnId === null || live.phase === "idle") return false
  if (live.threadId !== input.threadId) return false
  if (live.messageId === null) return true
  if (!reveal.handedOver) return true
  return !ordered.some((message) => message.id === live.messageId)
}

/**
 * The reveal for a surface that is not pacing anything: everything received is
 * on screen, and the Turn's own phase decides whether the work reads as running.
 */
function received(live: LiveTurn): DraftReveal {
  return {
    text: live.text,
    working:
      live.phase === "starting" || live.phase === "running" || live.phase === "cancelling",
    handedOver: true,
  }
}

function textOf(message: ThreadMessage): string {
  return typeof message.content.text === "string" ? message.content.text : ""
}

function assistantView(message: ThreadMessage): AssistantView {
  const content = message.content
  // `answer` is the reply; `text` is the reply plus everything narrated on the
  // way to it. A message stored before the two were told apart has only `text`,
  // and all of it was the reply then — so that is the fallback.
  const answer = typeof content.answer === "string" ? content.answer : ""
  return {
    text: answer !== "" ? answer : textOf(message),
    // A stored call cannot still be running: the Turn that made it is over.
    toolCalls: readToolCalls(content.tool_calls, "ok"),
    thoughts: readThoughts(content.thoughts),
    canvases: readCanvases(content.canvases),
    followUps: readStrings(content.follow_ups),
    elapsedMs:
      typeof content.elapsed_ms === "number" && Number.isFinite(content.elapsed_ms)
        ? content.elapsed_ms
        : 0,
    completed: content.status !== "incomplete",
  }
}


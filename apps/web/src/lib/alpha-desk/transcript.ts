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
import { readStrings, readThoughts, readToolCalls } from "./read-content"
import type { FlagReason, Thought, ThreadMessage, ToolCall } from "./types"

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
  /** The answer so far. Grows by whole deltas, never re-ordered. */
  text: string
  toolCalls: ToolCall[]
  thoughts: Thought[]
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
}

export function buildTranscript(input: TranscriptInput): TranscriptEntry[] {
  const ordered = [...input.messages].sort((left, right) => left.seq - right.seq)
  const entries: TranscriptEntry[] = []
  const pendingArtifacts = [...(input.openedAnalyses ?? [])]

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
    } else if (message.role === "assistant") {
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

  if (showsDraft(input, ordered)) {
    entries.push({
      kind: "draft",
      key: `draft-${input.live.turnId}`,
      text: input.live.text,
      toolCalls: input.live.toolCalls,
      thoughts: input.live.thoughts,
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
 */
function showsDraft(input: TranscriptInput, ordered: ThreadMessage[]): boolean {
  const { live } = input
  if (live.turnId === null || live.phase === "idle") return false
  if (live.threadId !== input.threadId) return false
  if (live.messageId === null) return true
  return !ordered.some((message) => message.id === live.messageId)
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
    followUps: readStrings(content.follow_ups),
    elapsedMs:
      typeof content.elapsed_ms === "number" && Number.isFinite(content.elapsed_ms)
        ? content.elapsed_ms
        : 0,
    completed: content.status !== "incomplete",
  }
}


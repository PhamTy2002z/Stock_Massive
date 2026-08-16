/**
 * What the transcript shows, given a canonical Thread and one live Turn.
 *
 * The two halves arrive from different places and mean different things: the
 * Thread is a TanStack Query resource and is history, and the live Turn is a
 * reducer's draft and is not history yet (ADR-0013). Deciding between them in
 * JSX would put the one rule that matters — **the canonical message replaces
 * the draft, it never joins it** — inside a component, where the only way to
 * check it is to render.
 *
 * So this is a pure projection. It answers one question: what rows are on
 * screen right now, in order.
 */

import type { LivePhase, LiveTurn } from "./live-turn"
import type {
  ActivityPhase,
  ContentBlock,
  FlagReason,
  RiskNotice,
  SourceAndMethod,
  ThreadMessage,
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
  blocks: ContentBlock[]
  /** Attached by the backend. Null only if a stored message somehow lacks one. */
  riskNotice: RiskNotice | null
  sourcesAndMethods: SourceAndMethod[]
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
}

export interface DraftEntry {
  kind: "draft"
  key: string
  blocks: ContentBlock[]
  activity: ActivityPhase | null
  phase: LivePhase
  terminalReason: string | null
  /**
   * The block that just arrived, by index, or null if nothing did.
   *
   * Carried straight from the reducer rather than derived from how the count
   * changed between renders. A snapshot and a run of events can produce the
   * same two counts, and only the action that caused them knows which happened
   * — so the reveal is decided where the events are, not where they are drawn.
   */
  appendedIndex: number | null
}

/**
 * One Analysis the user opened, sitting where they opened it.
 *
 * An Analysis is an artifact rather than a page (`docs/specs/0002` §5), so
 * opening one puts a row in the transcript instead of navigating away from it.
 * The row carries only the pair that identifies the Analysis; the artifact
 * reads itself, because a payload threaded through this projection would be a
 * second copy of a resource TanStack Query already owns.
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
      blocks: input.live.blocks,
      activity: input.live.activity,
      phase: input.live.phase,
      terminalReason: input.live.terminalReason,
      appendedIndex: input.live.appendedIndex,
    })
  }

  return entries
}

/**
 * Whether the draft is still the newest thing on screen.
 *
 * It stops being so the moment its canonical message is in the Thread — that
 * message carries the Risk Notice, the Evidence Manifest and the sources, and
 * showing both would render one answer twice with the fuller copy underneath.
 * Until then the draft stands, including when it ended with nothing: a Turn
 * that failed still owes the user a status and a retry.
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
  const blocks = Array.isArray(content.blocks) ? (content.blocks as ContentBlock[]) : []
  const text = textOf(message)
  return {
    // A stored message always carries blocks; the fallback exists so that a row
    // written before this shape existed renders as prose rather than as a gap.
    blocks: blocks.length > 0 ? blocks : text ? [proseBlock(text)] : [],
    riskNotice: isRiskNotice(content.risk_notice) ? content.risk_notice : null,
    sourcesAndMethods: Array.isArray(content.sources_and_methods)
      ? (content.sources_and_methods as SourceAndMethod[])
      : [],
  }
}

function proseBlock(text: string): ContentBlock {
  return { kind: "prose", text, symbol: null, trading_day: null, citations: [] }
}

function isRiskNotice(value: unknown): value is RiskNotice {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as RiskNotice).text === "string"
  )
}

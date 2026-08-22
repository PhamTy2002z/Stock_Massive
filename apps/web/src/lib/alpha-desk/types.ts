/**
 * The shapes the transport puts on the wire, as the browser reads them.
 *
 * Hand-written against the event contract in `docs/streaming-topology.md` and
 * the backend's own `as_wire()` methods rather than generated: the seven event
 * types and the envelope are a fixed contract with a version field, and a
 * generator would produce a moving type for something that is deliberately not
 * moving.
 *
 * Everything here is snake_case, because that is what arrives. Renaming at the
 * boundary would mean one more place where the client and the backend can
 * disagree about a field that already has exactly one name.
 */

/** The seven event types of the current contract. */
export type TurnEventType =
  | "turn.snapshot"
  | "content.delta"
  | "tool.call"
  | "turn.completed"
  | "turn.incomplete"
  | "turn.failed"
  | "turn.cancelled"

/**
 * The envelope version this client reads.
 *
 * Bumped only when the envelope itself changes, which is why it is stated here
 * rather than checked per event: an event carrying another version is a build
 * mismatch, and a client that dropped such an event would show a reader an
 * answer with holes in it instead of one that is merely unfamiliar.
 */
export const TURN_EVENT_VERSION = 2

/** Terminal Turn statuses, as `agent_turn.status` spells them. */
export type TurnStatus = "admitted" | "running" | "complete" | "incomplete" | "cancelled"

/**
 * One tool call the Turn made, as both the stream and a stored message carry it.
 *
 * `summary` is the sentence shown to the reader — the backend writes it, so the
 * surface never assembles one out of arguments it would have to interpret.
 * `status` moves from `running` to exactly one of `ok` or `error`, and the id is
 * what a later event updates rather than duplicates.
 */
export interface ToolCall {
  id: string
  name: string
  status: "running" | "ok" | "error"
  summary: string
  /**
   * Which round of the tool loop asked for this call, counting from zero.
   *
   * What the timeline groups by. The model asks for several searches in one
   * breath, and grouping them by when they arrived would guess at that; the
   * round is the fact the backend already knows.
   */
  round: number
  /** How many results the call produced, which is not always `results.length`. */
  result_count: number
  /** The sources behind this call, already flattened and capped by the backend. */
  results: ToolResult[]
}

/**
 * One source a tool call turned up, as the reader is shown it.
 *
 * **Every string here was written by somebody else.** It is the visible text of
 * a page a search engine chose, and it reaches the screen because a reader
 * deciding whether to trust an answer needs to see what it rested on. It is
 * data and never instruction, and it is never rendered as Markdown or HTML —
 * the backend strips markup and flattens whitespace, and the surface prints the
 * result as plain text inside a block labelled as outside content.
 */
export interface ToolResult {
  title: string
  url: string
  /** The hostname, which is what the reader recognises. Never a display name. */
  source: string
  snippet: string
}

/**
 * One thing the Turn said on its way to the answer.
 *
 * Prose from a round that went on to call tools: the model saying what it is
 * about to look up. It belongs to the timeline of what happened rather than to
 * the reply, and `round` is what files it beside the calls it introduced.
 */
export interface Thought {
  round: number
  text: string
}

export interface SnapshotData {
  through_seq: number
  status: TurnStatus
  terminal_reason: string | null
  /** Everything the answer says so far, not the delta that arrived last. */
  text: string
  /** What was said on the way to it, by round. Never part of `text`. */
  thoughts: Thought[]
  tool_calls: ToolCall[]
  /** The canonical assistant message, once a terminal transaction wrote one. */
  message_id: number | null
  /**
   * How long the Turn has been running, in milliseconds.
   *
   * On the snapshot as well as the terminal event, so a tab that connects late
   * — or reconnects — continues the clock from where the Turn actually is
   * rather than from when this tab started watching.
   */
  elapsed_ms: number
}

export interface TurnEvent {
  version: number
  /** Monotonic per Turn, and also the SSE `id` the browser resends. */
  seq: number
  type: TurnEventType
  turn_id: string
  data: Record<string, unknown>
}

/** The canonical assistant message, as the transcript stores it. */
export interface AssistantContent {
  text: string
  tool_calls: ToolCall[]
}

/** The user message, as the create transaction wrote it. */
export interface UserContent {
  text: string
  symbols?: string[]
}

/**
 * The four reason labels a flag may carry — the whole of the dispute
 * vocabulary (`docs/adr/0016`).
 *
 * Written out rather than derived from the API, because the backend validates
 * against its own copy on the column: the two have to stop agreeing at compile
 * time here, not at runtime in front of a reader.
 */
export type FlagReason = "wrong_figure" | "overreach" | "wrongly_refused" | "other"

/**
 * One message's flag, as the write endpoints answer it.
 *
 * Both fields move together: a message carries a reason and a stamp, or
 * neither. There is no third state, and there is no id of a ticket that was
 * opened — because no ticket is opened.
 */
export interface MessageFlag {
  message_id: number
  flagged_reason: FlagReason | null
  flagged_at: string | null
}

/**
 * One message's positive mark, as its write endpoints answer it.
 *
 * One field, because the mark carries no reason: there is nothing to categorise
 * about an answer that worked. Set is the mark, null is its absence — which is
 * what the clearing call answers with, so the caller renders the settled state
 * from the response it already has.
 */
export interface MessageHelpful {
  message_id: number
  helpful_at: string | null
}

export interface ThreadMessage {
  id: number
  seq: number
  role: "user" | "assistant" | "summary"
  content: Partial<AssistantContent> & Partial<UserContent> & Record<string, unknown>
  created_at: string
  /** Null on almost every message. Carried so a reopened Thread shows the flag. */
  flagged_reason: FlagReason | null
  flagged_at: string | null
  /** Carried for the same reason: a marked answer must come back marked. */
  helpful_at: string | null
}

export interface Thread {
  id: string
  title: string | null
  /** Every symbol the Thread has touched. It is never owned by one. */
  symbols: string[]
  /**
   * When the user pinned it, or null.
   *
   * The list arrives already ordered with the pinned group first, so this is
   * read to *label* that group and to say which way the menu's Pin toggles —
   * never to re-sort what the backend already sorted.
   */
  pinned_at: string | null
  created_at: string
  updated_at: string
}

export interface ThreadDetail extends Thread {
  messages: ThreadMessage[]
}

export interface Turn {
  id: string
  thread_id: string
  status: TurnStatus
  terminal_reason: string | null
  request_message_id: number
  response_message_id: number | null
  retry_of_turn_id: string | null
  last_event_seq: number
  cancel_requested: boolean
  started_at: string
  finished_at: string | null
}

export interface CreatedTurn extends Turn {
  /** False when the id was already known: nothing was created, nothing started. */
  created: boolean
}

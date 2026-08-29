/**
 * The shapes the transport puts on the wire, as the browser reads them.
 *
 * Hand-written against the event contract in `docs/streaming-topology.md` and
 * the backend's own `as_wire()` methods rather than generated: the event types
 * and the envelope are a fixed contract with a version field, and a
 * generator would produce a moving type for something that is deliberately not
 * moving.
 *
 * Everything here is snake_case, because that is what arrives. Renaming at the
 * boundary would mean one more place where the client and the backend can
 * disagree about a field that already has exactly one name.
 */

/** The eight event types of the current contract. */
export type TurnEventType =
  | "turn.snapshot"
  | "content.delta"
  | "tool.call"
  /**
   * A Study produced a desk view and the row holding it is committed.
   *
   * Additive rather than an envelope bump, which is why it sits in the same
   * union: a client subscribes by event name, so one that never asks for this
   * reads the Turn exactly as it did before.
   */
  | "signal_desk.ready"
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
  /**
   * Why the call ended in `error`, as the backend's stable code — or `null`.
   *
   * `status` alone cannot answer what the reader wants to know, because three of
   * the codes are not failures: the Turn spent its allowance of external calls,
   * the round asked for more than it may dispatch, the tool loop was halted.
   * Those were refused here before anything left the deployment, and drawing
   * them like a search engine going down asks the reader to retry something
   * retrying will not fix.
   */
  error: string | null
  /** How many results the call produced, which is not always `results.length`. */
  result_count: number
  /** The sources behind this call, already flattened and capped by the backend. */
  results: ToolResult[]
  /**
   * Which kind of evidence the call went and got.
   *
   * The backend reads this off the tool's own registration — the same
   * declaration that decides whether the result is wrapped as outside content —
   * so the surface can draw the two apart without keeping a list of tool names
   * it would have to remember to extend. A figure out of this system's store
   * carries a date and a health and reads the same tomorrow; a page carries
   * none of that, and drawing them alike would undo in pixels what the message
   * layer does in the prompt.
   *
   * Optional because a Turn stored before the field existed does not carry it,
   * and `external` is the safe reading of a call whose provenance is unstated.
   */
  kind?: ToolCallKind
  /**
   * What the call *yielded*, where that is a different question from whether it
   * ran.
   *
   * A store read that comes back saying the store has nothing to say is a
   * successful call: the tool worked and the answer is that there is no figure.
   * So it arrives as `ok` and was drawn exactly like a call that returned a
   * number — which, measured over the trace, was a third of them. A reader
   * watching four rows of `Đọc chỉ báo` go by had no way to see that three of
   * them came back empty.
   *
   * `value` when a figure came back; `cannot_read` when the tool declined the
   * question itself; `no_value:<signal issue>` when the store was asked and had
   * no number, carrying the reason so the surface can say which. Optional
   * because most tools have nothing to classify and because a Turn stored before
   * the field existed does not carry it.
   */
  outcome?: string | null
}

/** Where a tool call's result came from: outside this deployment, or its store. */
export type ToolCallKind = "external" | "store"

/**
 * Whether this call ran and came back with nothing, which `status` cannot say.
 *
 * A prefix test rather than an equality one: the backend appends the refusal's
 * own **Signal Issue** to `no_value`, and the surface asks a coarser question
 * than the trace stores.
 */
export function answeredNothing(call: ToolCall): boolean {
  const outcome = call.outcome
  if (!outcome) return false
  return outcome === "cannot_read" || outcome.startsWith("no_value")
}

/** The Signal Issue behind an empty answer, when the outcome names one. */
export function outcomeIssue(call: ToolCall): string | null {
  const outcome = call.outcome
  if (!outcome || !outcome.startsWith("no_value:")) return null
  return outcome.slice("no_value:".length)
}

/** What a call read, defaulting the way the backend defaults an unknown tool. */
export function toolCallKind(call: ToolCall): ToolCallKind {
  return call.kind === "store" ? "store" : "external"
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
 * One desk view a Turn produced, as the stream announces it and a message keeps it.
 *
 * **No numbers.** The matrix a picture is drawn from lives in one row and
 * travels on one request — the fetch that happens when a reader opens the panel.
 * Every open tab receives this, and a payload carrying the cells would put them
 * back on the channel the whole arrangement exists to keep them off.
 *
 * `blockCount` is here so the panel can draw a skeleton of the right height the
 * instant it hears, rather than an empty box that jumps when the fetch lands.
 */
export interface SignalDeskAnnouncement {
  artifactId: string
  /**
   * The recipe's stable name.
   *
   * **Never shown to a reader.** It is a slug the server keys registrations by,
   * and printing it would put a function name in front of somebody who came for
   * an analysis. What a person is shown is `studyDisplayName`, and what they
   * search on is both.
   */
  studyName: string
  /** The recipe's Vietnamese name, which is the one a reader may see. */
  studyDisplayName: string
  title: string
  blockCount: number
  /** Which round of the tool loop produced it. Files it beside that round. */
  round: number
  /**
   * The ticker the board is about, or `""` for a board that is about no one
   * company. Carried so a reader can type a symbol to find the board again.
   */
  symbol: string
  /** When the numbers were frozen, ISO-8601, or `""` where the run said nothing. */
  asOf: string
}

/**
 * One frame: a series, a matrix, or a table, positional against its columns.
 *
 * Rows are arrays rather than objects because a heatmap is mostly cells, and a
 * list of objects would repeat every column name once per session.
 *
 * `labels` is the Vietnamese a person reads, and it comes from the server
 * because the column names were chosen by whoever wrote the Study — a label
 * invented here would be this layer interpreting a number it does not own.
 */
export interface Frame {
  kind: "series" | "matrix" | "table"
  columns: string[]
  rows: unknown[][]
  unit: string | null
  labels: Record<string, string>
  /**
   * What a whole series is, keyed by column, as the engine declared it.
   *
   * A meaning rather than a colour — "this one fell", "this is the one the
   * answer is about" — because only the layer that computed the number knows
   * which, and a colour chosen there would be legible in one of the two themes.
   * Optional: every artifact written before this says nothing, and a picture
   * that says nothing is drawn the way it always was.
   */
  columnRoles?: Record<string, string>
  /** The same, positional against `rows`, for one bar, point or tile. */
  pointRoles?: (string | null)[]
}

/** One widget on the desk view, the frame it draws, and the options the server chose. */
export interface SignalDeskBlock {
  widget: string
  widgetVersion: number
  frame: string
  options: Record<string, unknown>
}

export interface SignalDeskSpec {
  title: string
  blocks: SignalDeskBlock[]
}

/**
 * Where the numbers came from, frozen when they were computed.
 *
 * `asOf` is the freeze, and the reason a re-opened Thread renders rather than
 * recomputes. The four fields are shown together: a date without the health, or
 * a health without the session count, is a fact a reader cannot weigh.
 */
export interface Provenance {
  /**
   * Which store the numbers were read out of.
   *
   * **Not shown to a reader.** It names a provider and a layer of this system,
   * which is a fact about the plumbing rather than about the analysis. Kept on
   * the type because the payload carries it and an export may want it.
   */
  source: string
  asOf: string
  sessionsUsed: number
  health: "normal" | "degraded" | "unavailable"
  /**
   * Why the health is what it is, when the run said.
   *
   * One Vietnamese sentence for a reader, at most 120 characters, checked by
   * the Study contract for the system's own words before the row is frozen.
   * Rows frozen before that check may carry refusal codes or internal English
   * prose; `ProvenanceStrip.readableReason` maps the codes and drops the rest.
   */
  reason: string | null
  /**
   * How the numbers were arrived at, in a reader's language.
   *
   * Behind a disclosure rather than on the strip: it is what somebody checks
   * *after* deciding the picture matters, and putting a method paragraph on the
   * line above every chart buries the three facts that belong there.
   *
   * Optional because an artifact frozen before the field existed carries none,
   * and a run that explains nothing is not a run that explains badly.
   */
  methodNotes?: string[]
}

/** One Study run, as the desk view endpoint serves it. Immutable by design. */
export interface ArtifactPayload {
  id: string
  study_name: string
  study_version: number
  params: Record<string, unknown>
  signal_desk_spec: SignalDeskSpec
  frames: Record<string, Frame>
  provenance: Provenance
  created_at: string
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
  /** The desk views announced so far. Restated so a reconnect is still told. */
  signal_desks: SignalDeskAnnouncement[]
  /** Stored by the canvas-era contract; accepted while old Turns remain readable. */
  canvases?: SignalDeskAnnouncement[]
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
  /** The pictures this answer was written about. Ids and titles, never cells. */
  signal_desks: SignalDeskAnnouncement[]
  /** Stored by the canvas-era contract; accepted while old Threads remain readable. */
  canvases?: SignalDeskAnnouncement[]
}

/** The user message, as the create transaction wrote it. */
/**
 * One thing the reader attached, as every layer that is not the bytes sees it.
 *
 * Metadata only, and that is the contract rather than an economy: the row is
 * immutable, so its bytes are a separate cacheable request against
 * `GET /attachments/{id}`. Carrying them here would make one thread open bring
 * back every picture the conversation ever held.
 */
export interface Attachment {
  id: string
  filename: string
  media_type: string
  byte_size: number
  /** What an image is charged. Absent for a text file, whose cost is its characters. */
  estimated_tokens?: number
}

/** Whether this is something to draw a thumbnail for. */
export function isImageAttachment(attachment: { media_type: string }): boolean {
  return attachment.media_type.startsWith("image/")
}

export interface UserContent {
  text: string
  symbols?: string[]
  /** What was attached to this question. Absent on every Turn that had none. */
  attachments?: Attachment[]
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

/**
 * One ceiling, what has gone against it, and when it next frees.
 *
 * `limit: null` is a ceiling the deployment turned off, which is **not** a
 * ceiling of zero: a subscription route sets all of them to zero in its config
 * and the API reports that as unlimited. Zero here would draw a full meter and
 * tell the reader they had run out of something they cannot run out of.
 *
 * `resets_at: null` means nothing is waiting to be released — an empty window
 * rather than an unknown one.
 */
export interface Allowance {
  used: number
  limit: number | null
  resets_at: string | null
}

/**
 * What this account has consumed against its own ceilings.
 *
 * Spend arrives in micro-USD, the ledger's integer unit, so rounding happens
 * once and here. It is an operating limit on generation rather than an amount
 * owed, and the panel is responsible for not implying a bill.
 */
/**
 * What this deployment's route can do.
 *
 * A property of the route the API was configured and measured against, so it is
 * the same for every account and constant until a deploy. Deliberately not a
 * field on {@link Usage}: that is one account's consumption, and folding a
 * constant into it would have the surface poll for a value that cannot move.
 */
export interface Capabilities {
  /**
   * Whether the model reads images.
   *
   * When false the composer still accepts and stores them and says so plainly —
   * a picture silently ignored reads to the reader as a wrong answer.
   */
  vision: boolean
}

export interface Usage {
  as_of: string
  turns_today: Allowance
  spend_today_micro_usd: Allowance
  spend_rolling_30d_micro_usd: Allowance
}

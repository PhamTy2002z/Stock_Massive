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

/**
 * The nine event types of the current contract.
 *
 * `part.progress` and `part.question` were added to the seven rather than in
 * place of any of them, which is why {@link TURN_EVENT_VERSION} did not move:
 * the envelope is unchanged and the other seven are byte-identical. A client
 * only ever sees a named event it subscribed to (`use-live-turn`), so the
 * addition costs an older build nothing.
 */
export type TurnEventType =
  | "turn.snapshot"
  | "content.delta"
  | "tool.call"
  | "part.progress"
  | "part.question"
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
 * surface never assembles one out of arguments it would have to interpret. The
 * id is what a later event updates rather than duplicates.
 *
 * `status` is the five states the backend's own projection has
 * (`messages.ToolCallStatus`), and the two beyond the original three are facts
 * no other field carries. `pending` is a call *written down* before its effect
 * ran — the harness checkpoints the intent of a batch that changes durable
 * state, so a crash between dispatch and result still leaves a record; it is
 * weaker than `running`, which means the call is on its way to the tool.
 * `denied` is a call a permission rule refused: nothing ran and nothing will, so
 * it is not a tool that broke and not something pressing again can fix.
 */
export interface ToolCall {
  id: string
  name: string
  status: "pending" | "running" | "ok" | "error" | "denied"
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
   * Why the call did not answer, as the backend's stable code — or `null`.
   *
   * `status` alone cannot answer what the reader wants to know, because several
   * of the codes are not failures: the Turn spent its allowance of external
   * calls, the round asked for more than it may dispatch, the tool loop was
   * halted, a permission rule closed the route. Those were refused here before
   * anything left the deployment, and drawing them like a search engine going
   * down asks the reader to retry something retrying will not fix.
   *
   * It arrives on the stream as well as on a stored message, so a live row and
   * the row a reopened Thread draws say the same thing.
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
   * it would have to remember to extend. A result out of this system's store
   * has different trust semantics from a public page, which carries
   * none of that, and drawing them alike would undo in pixels what the message
   * layer does in the prompt.
   *
   * Optional because a Turn stored before the field existed does not carry it,
   * and `external` is the safe reading of a call whose provenance is unstated.
   */
  kind?: ToolCallKind
}

/** Where a tool call's result came from: outside this deployment, or its store. */
export type ToolCallKind = "external" | "store"

/** What a call read, defaulting the way the backend defaults an unknown tool. */
export function toolCallKind(call: ToolCall): ToolCallKind {
  return call.kind === "store" ? "store" : "external"
}

/**
 * Whether this call is still on its way, whichever of the two ways that is.
 *
 * Asked here rather than compared to `running` at each site, because `pending`
 * is the same thing to a reader — a call that has not come back — and a surface
 * comparing statuses one by one gains a settled-looking row for a call still
 * out at every site somebody forgets.
 */
export function toolCallWaiting(call: ToolCall): boolean {
  return call.status === "running" || call.status === "pending"
}

/**
 * Whether this call ended with nothing to show, whichever of the two ways.
 *
 * A tool that broke and a route a permission rule closed both leave the row
 * with no result, and both are drawn as the failure they are. Which of the two
 * it was is on `error` rather than on the status: that is where the words come
 * from.
 */
export function toolCallFailed(call: ToolCall): boolean {
  return call.status === "error" || call.status === "denied"
}

/**
 * Every distinct publisher behind these calls, in the order they were first seen.
 *
 * Distinct, because that is the question a reader is asking. Three searches that
 * all came back with the same newspaper rested on one source, and a count of
 * results would say three — overstating how much of the answer was corroborated
 * rather than repeated.
 *
 * Order is first-seen rather than sorted: only the first few marks are drawn,
 * and the source the answer leaned on first is a better thing to show than
 * whichever hostname happens to sort earliest.
 *
 * The hostname is read off `source`, which the backend derived once when it
 * built the result. Parsing the link again here would be a second derivation of
 * one fact, free to disagree with the first.
 */
export function distinctDomains(calls: ToolCall[]): string[] {
  const seen = new Set<string>()
  const domains: string[] = []
  for (const call of calls) {
    for (const result of call.results) {
      const domain = result.source.trim()
      if (domain === "" || seen.has(domain)) continue
      seen.add(domain)
      domains.push(domain)
    }
  }
  return domains
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

/**
 * The seven loop events a Turn reports progress for (`agent/parts.py`).
 *
 * A closed set on the backend and a closed union here, for the same reason the
 * payload is an allowlist there: a kind nobody named is a kind nobody decided
 * was fit for a screen.
 */
export type ProgressKind =
  | "lane_selected"
  | "model_attempt"
  | "tool_round"
  | "recovery"
  | "tools_halted"
  | "rounds_exhausted"
  | "deadline"

/**
 * One thing the loop did, numbered within its Turn.
 *
 * The audit trail of the *loop* rather than a second copy of the tool calls:
 * which ceilings the Turn was given, that it asked the model and how that
 * asking ended, that it gave up transcript and asked again, that it ran out of
 * rounds. Every part is emitted by the code that did the thing it names, so
 * there is no stage a Turn is declared to have entered because a clock said so.
 *
 * `seq` is the part's ordinal in this Turn and not the publisher's event
 * sequence — the two count different things, and it is the parts' own order a
 * reader wants. `round` files it beside the calls and the narration of the same
 * round.
 *
 * `payload` stays a record of unknowns on purpose. What may be inside it is
 * decided by the backend's per-kind allowlist, which admits codes, numbers and
 * one list of call ids and never a page's text; naming the fields here would
 * claim a shape this client never checked. What reads them is the timeline that
 * draws them, and it reads them by name.
 */
export interface ProgressPart {
  seq: number
  kind: ProgressKind
  round: number
  payload: Record<string, unknown>
  /** The loop's own clock, UTC and ISO: how long a Turn sat inside one step. */
  at: string
}

/**
 * The four outcomes of one asking, as `agent_question.state` spells them.
 *
 * `pending` is what the Turn that asked wrote. The other three are ends: the
 * reader chose, the reader declined and the work runs on stated assumptions, or
 * the reader typed into the composer instead of touching the card and the next
 * Turn made the question moot. A resolved question is never reopened.
 */
export type QuestionState = "pending" | "answered" | "skipped" | "superseded"

/** One choice on a card: a stable id, a button, and at most one line under it. */
export interface QuestionOption {
  /** What the client posts back. A code, never the label — a wording can change. */
  id: string
  label: string
  detail: string | null
}

/**
 * One question a Turn ended by asking, and what became of it.
 *
 * The card itself is immutable and arrives identically by both routes: on the
 * stream just before the terminal event, and on the stored message a reopened
 * Thread reads. `state` and `selected_option_ids` are the half that changes
 * after the Turn ended — the backend merges them in from the row that records
 * the outcome, so the client draws one card rather than a card and a lookup.
 *
 * Answering is not resuming. The Turn is over; the reply is the next Turn.
 */
export interface QuestionPart {
  question_id: string
  prompt: string
  options: QuestionOption[]
  /** A property of the question rather than of the surface, from the first version. */
  multi_select: boolean
  skip_label: string
  state: QuestionState
  /** Null for every state that is not an answer — an empty list would read as a skip. */
  selected_option_ids: string[] | null
}

/**
 * What answering or skipping a question comes back as: what changed, and no more.
 *
 * The card itself is not restated. It is already in the transcript the caller is
 * holding, and sending it back would give one payload two owners.
 */
export interface ResolvedQuestion {
  id: string
  state: QuestionState
  selected_option_ids: string[] | null
  resolved_at: string | null
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
  /**
   * Every loop event published so far, in the order it happened.
   *
   * Restated like the thoughts and the calls, so a reader who reconnects draws
   * the same trail as the reader who never left. Absent from a snapshot rebuilt
   * out of a checkpoint written before parts existed, which means that Turn
   * reported no loop events rather than that its trail was lost.
   */
  progress?: ProgressPart[]
  /**
   * The card this Turn ended by asking for, or null.
   *
   * On the snapshot so that a reader whose connection dropped between the
   * question and the terminal event is not the one reader who never sees it. It
   * is always `pending` here: what the reader *did* with a card changes after
   * the Turn ended, and that is read from the transcript.
   */
  question?: QuestionPart | null
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
  /** What the loop did, kept in the transcript rather than only on the stream. */
  progress: ProgressPart[]
  /** The card this answer ended by asking for, with its outcome merged in. */
  question: QuestionPart | null
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
 * vocabulary.
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

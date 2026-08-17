/**
 * The shapes the transport puts on the wire, as the browser reads them.
 *
 * Hand-written against ADR-0013 and the backend's own `as_wire()` methods
 * rather than generated: the eight event types and the envelope are a fixed
 * contract with a version field, and a generator would produce a moving type
 * for something that is deliberately not moving.
 *
 * Everything here is snake_case, because that is what arrives. Renaming at the
 * boundary would mean one more place where the client and the backend can
 * disagree about a field that already has exactly one name.
 */

/** The eight v1 event types. `version` is bumped only when the envelope changes. */
export type TurnEventType =
  | "turn.snapshot"
  | "turn.activity"
  | "content.block"
  | "widget.ready"
  | "turn.completed"
  | "turn.incomplete"
  | "turn.failed"
  | "turn.cancelled"

/**
 * The phases the activity line may show. Never a tool name.
 *
 * `found_sources` is ADR-0020's addition, and it is a phase of its own rather
 * than `searching` with extra keys: "a search is running, here is what was
 * asked" and "the search returned, here is what came back" are different
 * moments, and a renderer telling them apart by which key is present would be
 * reading absence as meaning.
 */
export type ActivityPhase =
  | "searching"
  | "reading_data"
  | "analyzing"
  | "preparing_visual"
  | "found_sources"

/**
 * One public page an open-web step stood on. `domain` is resolved by the backend.
 *
 * The excerpt and the two timestamps are what the search result itself said —
 * present when it offered them, absent otherwise. The source drawer reads their
 * presence; nothing here is ever an empty string standing in for "unknown".
 */
export interface ProgressSource {
  title: string
  url: string
  domain: string
  snippet?: string
  published_at?: string
  retrieved_at?: string
}

/**
 * What the open-web lane disclosed about one step (`docs/adr/0020`).
 *
 * Absent on every store-reading lane, which is the whole point: presence means
 * "this step is public work and may describe itself", and every other step is
 * the bare phase ADR-0013 always allowed.
 */
export interface ProgressDetail {
  queries?: string[]
  result_count?: number
  sources?: ProgressSource[]
}

/** One step of the trail, in the order the Turn went through it. */
export interface ProgressStep {
  phase: ActivityPhase
  detail?: ProgressDetail
}

/** Terminal Turn statuses, as `agent_turn.status` spells them. */
export type TurnStatus = "admitted" | "running" | "complete" | "incomplete" | "cancelled"

export type CitationSource =
  | "registered_field"
  | "stored"
  | "source_claim"
  | "external_claim"
  | "derived"
  | "user_input"

export interface Citation {
  tool_call_id: string
  tool_name: string
  field_path: string
  value: unknown
  unit: string | null
  interpretation: string | null
  claim: string | null
  provenance: string
  as_of: string | null
  stale: boolean
  source: CitationSource
  window_health: Record<string, unknown> | null
  contradictory: boolean
  zone_label: string | null
  reference_price: boolean
}

/** One proven presentation unit. Never a token, never a partial table. */
export interface ContentBlock {
  kind: "prose" | "recommendation"
  text: string
  symbol: string | null
  trading_day: string | null
  citations: Citation[]
  /** Additive in prompt contract 1.3; absent on messages stored by older builds. */
  unverified_figures?: string[]
}

/** A validated Widget spec. The registry itself is #89's; this is its envelope. */
export interface WidgetSpec {
  [key: string]: unknown
}

export interface SnapshotData {
  through_seq: number
  status: TurnStatus
  terminal_reason: string | null
  activity: ActivityPhase | null
  /**
   * Every step the Turn has been through, in order.
   *
   * Carried by the snapshot rather than rebuilt from events the tab missed, so
   * a reconnecting reader gets the trail they were watching instead of the
   * fragment that happened to arrive after they reattached. Absent on a
   * snapshot from a build older than ADR-0020.
   */
  progress?: ProgressStep[]
  blocks: ContentBlock[]
  widgets: WidgetSpec[]
  /** The canonical assistant message, once a terminal transaction wrote one. */
  message_id: number | null
}

export interface TurnEvent {
  version: number
  /** Monotonic per Turn, and also the SSE `id` the browser resends. */
  seq: number
  type: TurnEventType
  turn_id: string
  data: Record<string, unknown>
}

/** The Risk Notice the backend attaches. The renderer displays it; prose cannot. */
export interface RiskNotice {
  version: string
  locale: string
  text: string
  meanings: string[]
}

export interface EvidenceManifest {
  schema_version: number
  prompt_version: string
  prompt_hash: string
  git_sha: string | null
  model: string
  route: string
  provider_request_id: string | null
  tool_catalog_version: string
  registry_version: string
  risk_notice_version: string
  answer_kind: "analysis" | "education" | "refusal"
  status: string
  terminal_reason: string | null
  outcomes: Record<string, unknown>
  cited_fields: Citation[]
}

export interface SourceAndMethod {
  provider_source: string
  tool_call_id: string
  tool_name: string
  registered_field: string | null
  value: unknown
  unit: string | null
  interpretation: string | null
  freshness: { as_of: string | null; stale: boolean }
  window_health: Record<string, unknown> | null
  [key: string]: unknown
}

/** The canonical assistant message, as the transcript stores it. */
export interface AssistantContent {
  text: string
  blocks: ContentBlock[]
  answer_kind: "analysis" | "education" | "refusal"
  risk_notice: RiskNotice
  evidence_manifest: EvidenceManifest
  sources_and_methods: SourceAndMethod[]
  /** ADR-0020's two additive keys. Absent on messages stored by older builds. */
  search_progress?: ProgressStep[]
  suggestions?: string[]
}

/** The user message, as the create transaction wrote it. */
export interface UserContent {
  text: string
  symbols?: string[]
}

/**
 * The four reason labels a flag may carry — the whole of v1's dispute
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

export interface ThreadMessage {
  id: number
  seq: number
  role: "user" | "assistant" | "summary"
  content: Partial<AssistantContent> & Partial<UserContent> & Record<string, unknown>
  created_at: string
  /** Null on almost every message. Carried so a reopened Thread shows the flag. */
  flagged_reason: FlagReason | null
  flagged_at: string | null
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

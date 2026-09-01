/**
 * Reading a Turn's content out of whatever shape it actually arrived in.
 *
 * Two callers need the same thing from two different places. The reducer reads
 * it off the wire, where the payload is `Record<string, unknown>` because the
 * network is not typed; the transcript reads it out of a JSONB column, where
 * the interface saying `ToolCall[]` describes the contract rather than the
 * bytes. Both are the same question — *is this actually a tool call?* — and two
 * answers to it would drift, with the drift visible only as a row that renders
 * on a reconnect and not on a reload.
 *
 * Every reader here is total: it returns a value for any input and never
 * throws. Anything malformed is dropped rather than rendered with `undefined`
 * in it, because a blank row in this list reads to the user as a source they
 * cannot see — which is worse than one fewer row.
 *
 * **The strings are not ours.** A result's title, snippet and domain were
 * written by whichever page a search engine returned. Nothing here sanitises
 * them and nothing here needs to: the backend already flattened them to visible
 * text, and the components render them as text. What this module guarantees is
 * only that they *are* strings.
 */

import type {
  ProgressKind,
  ProgressPart,
  QuestionOption,
  QuestionPart,
  QuestionState,
  Thought,
  ToolCall,
  ToolResult,
} from "./types"

/** The five statuses a call can be in, as either source may spell it. */
type CallStatus = ToolCall["status"]

/** Every status the backend's projection has, for the read below to match on. */
const CALL_STATUSES: readonly CallStatus[] = [
  "pending",
  "running",
  "ok",
  "error",
  "denied",
]

/** The loop events a progress part may name, as `parts.ProgressKind` names them. */
const PROGRESS_KINDS: readonly ProgressKind[] = [
  "lane_selected",
  "model_attempt",
  "tool_round",
  "recovery",
  "context_pruned",
  "tools_halted",
  "rounds_exhausted",
  "deadline",
]

/** What a question can have become, as `agent_question.state` spells it. */
const QUESTION_STATES: readonly QuestionState[] = [
  "pending",
  "answered",
  "skipped",
  "superseded",
]

/**
 * One tool call, or nothing.
 *
 * `fallbackStatus` is the difference between the two callers, and it is a real
 * one rather than a knob. A call arriving on the stream with no status it
 * recognises is one that has been announced and not yet settled, so it is
 * `running`. A call read out of a stored message cannot still be running — the
 * Turn that made it is over — so an unrecognised status there means the row
 * predates the field, and `ok` is what it meant.
 */
export function readToolCall(
  value: unknown,
  fallbackStatus: CallStatus,
): ToolCall | null {
  const record = asRecord(value)
  if (record === null) return null
  const id = asString(record.id)
  const name = asString(record.name)
  // A call with no id cannot be updated by the announcement that follows it, so
  // it would be appended a second time rather than replaced.
  if (id === "" || name === "") return null
  const status = record.status
  const results = readResults(record.results)
  const summary = asString(record.summary)
  return {
    id,
    name,
    // Matched against the list rather than against three literals, so a status
    // the backend adds arrives as itself instead of as the fallback. The raw
    // value is what is kept: a surface asks `toolCallWaiting` or
    // `toolCallFailed` what to draw, and collapsing `denied` into `error` here
    // would throw away the one fact that says pressing again cannot help.
    status: isCallStatus(status) ? status : fallbackStatus,
    summary: summary === "" ? name : summary,
    // Absent, empty, or the wrong type all mean the same thing here: nothing to
    // say beyond the status. Only a non-empty string is a reason.
    error: typeof record.error === "string" && record.error !== "" ? record.error : null,
    round: asNumber(record.round, 0),
    // The backend caps how many results it sends, so a count larger than the
    // list is correct and is what the reader should be told. Only a payload
    // with no count at all falls back, and it falls back to the truth.
    result_count: asNumber(record.result_count, results.length),
    results,
    // Anything other than the one value that means "this system's own store"
    // reads as outside content, which is the same direction the backend's own
    // default leans: being wrong this way costs a wrapper around a figure, and
    // being wrong the other way draws a stranger's page as our own data.
    kind: record.kind === "store" ? "store" : "external",
  }
}

/** Every tool call in a list, malformed ones dropped. */
export function readToolCalls(value: unknown, fallbackStatus: CallStatus): ToolCall[] {
  if (!Array.isArray(value)) return []
  const calls: ToolCall[] = []
  for (const item of value) {
    const call = readToolCall(item, fallbackStatus)
    if (call !== null) calls.push(call)
  }
  return calls
}

/** The sources behind one call, malformed ones dropped. */
export function readResults(value: unknown): ToolResult[] {
  if (!Array.isArray(value)) return []
  const results: ToolResult[] = []
  for (const item of value) {
    const record = asRecord(item)
    if (record === null) continue
    const title = asString(record.title)
    const url = asString(record.url)
    // Nothing to show and nowhere to go, so not a source and not a row.
    if (title === "" && url === "") continue
    results.push({
      title,
      url,
      source: asString(record.source),
      snippet: asString(record.snippet),
    })
  }
  return results
}


/**
 * One loop event, or nothing.
 *
 * `payload` is passed through as it arrived rather than field-checked, because
 * what may be in it was already decided by the allowlist that built it: codes,
 * numbers and one list of call ids, and never a page's text. What is checked is
 * what the timeline orders and files by — a part with an unknown kind is dropped
 * rather than drawn, since a row nobody designed says nothing a reader can use.
 */
export function readProgressPart(value: unknown): ProgressPart | null {
  const record = asRecord(value)
  if (record === null) return null
  const kind = record.kind
  if (!isProgressKind(kind)) return null
  return {
    seq: asNumber(record.seq, 0),
    kind,
    round: asNumber(record.round, 0),
    payload: asRecord(record.payload) ?? {},
    at: asString(record.at),
  }
}

/**
 * Every loop event in a list, malformed ones dropped, in the order they happened.
 *
 * Sorted by the parts' own `seq` rather than left as they arrived. The stream
 * delivers them in order and so does the snapshot, but the order *is* the
 * information here, and a trail that read wrongly would be a story about a Turn
 * that never happened.
 */
export function readProgressParts(value: unknown): ProgressPart[] {
  if (!Array.isArray(value)) return []
  const parts: ProgressPart[] = []
  for (const item of value) {
    const part = readProgressPart(item)
    if (part !== null) parts.push(part)
  }
  return parts.sort((left, right) => left.seq - right.seq)
}

/**
 * One question card, or nothing.
 *
 * Refused rather than half-drawn: a card is only a card if it has a prompt and
 * at least two answerable options, and one drawn with a missing option is a
 * dead end the reader cannot leave. That is the same rule the backend applies
 * when it builds one, and this is the client's half of it.
 *
 * `fallbackState` is the difference between the two callers, the way it is for a
 * tool call. A card arriving on the stream carries its state and is `pending`
 * anyway. A stored one whose state is missing has no row behind it any more —
 * the outcome lives on a row the transcript merges in — so it is read as
 * `superseded`: asked, and no longer something an answer can be recorded for.
 */
export function readQuestion(
  value: unknown,
  fallbackState: QuestionState,
): QuestionPart | null {
  const record = asRecord(value)
  if (record === null) return null
  const questionId = asString(record.question_id)
  const prompt = asString(record.prompt)
  const options = readQuestionOptions(record.options)
  if (questionId === "" || prompt === "" || options.length < 2) return null
  const state = record.state
  const chosen = readStrings(record.selected_option_ids)
  return {
    question_id: questionId,
    prompt,
    options,
    multi_select: record.multi_select === true,
    skip_label: asString(record.skip_label),
    state: isQuestionState(state) ? state : fallbackState,
    // Null and an empty list are different answers: nothing was chosen, versus
    // this is not a state that chooses. Only a state that carries choices keeps
    // them, so an `answered` card with none left cannot be drawn as a choice.
    selected_option_ids: chosen.length === 0 ? null : chosen,
  }
}

/** The choices on one card, malformed ones dropped. */
function readQuestionOptions(value: unknown): QuestionOption[] {
  if (!Array.isArray(value)) return []
  const options: QuestionOption[] = []
  for (const item of value) {
    const record = asRecord(item)
    if (record === null) continue
    const id = asString(record.id)
    const label = asString(record.label)
    // Nothing to post back, or nothing to press: not a choice and not a button.
    if (id === "" || label === "") continue
    const detail = asString(record.detail)
    options.push({ id, label, detail: detail === "" ? null : detail })
  }
  return options
}

export function readThoughts(value: unknown): Thought[] {
  if (!Array.isArray(value)) return []
  const thoughts: Thought[] = []
  for (const item of value) {
    const record = asRecord(item)
    if (record === null) continue
    const text = asString(record.text)
    if (text === "") continue
    thoughts.push({ round: asNumber(record.round, 0), text })
  }
  return thoughts
}

/**
 * The narration list with one delta folded in.
 *
 * A round already narrating has the delta appended to its line rather than
 * gaining a second one. The route splits a sentence across frames whenever it
 * feels like it, and two rows each holding half a sentence is not what was
 * said.
 */
export function appendThought(
  thoughts: Thought[],
  round: number,
  delta: string,
): Thought[] {
  const index = thoughts.findIndex((thought) => thought.round === round)
  if (index === -1) return [...thoughts, { round, text: delta }]
  const next = [...thoughts]
  next[index] = { round, text: next[index].text + delta }
  return next
}

/** A list of non-empty strings, with everything else dropped. */
export function readStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is string => typeof item === "string" && item.trim() !== "",
  )
}

function isCallStatus(value: unknown): value is CallStatus {
  return typeof value === "string" && (CALL_STATUSES as readonly string[]).includes(value)
}

function isProgressKind(value: unknown): value is ProgressKind {
  return typeof value === "string" && (PROGRESS_KINDS as readonly string[]).includes(value)
}

function isQuestionState(value: unknown): value is QuestionState {
  return typeof value === "string" && (QUESTION_STATES as readonly string[]).includes(value)
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function asNumber(value: unknown, fallback: number): number {
  // `Number.isFinite` rather than `typeof`: JSON can carry `NaN` through a
  // permissive parser, and a NaN round would sort every row to nowhere.
  return typeof value === "number" && Number.isFinite(value) ? value : fallback
}

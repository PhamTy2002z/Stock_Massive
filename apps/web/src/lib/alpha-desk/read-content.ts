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

import { SIGNAL_DESK_COPY } from "./copy"
import type { SignalDeskAnnouncement, Thought, ToolCall, ToolResult } from "./types"

/** The three statuses a call can be in, as either source may spell it. */
type CallStatus = ToolCall["status"]

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
    status:
      status === "running" || status === "ok" || status === "error"
        ? status
        : fallbackStatus,
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
 * Every desk view announced, malformed ones dropped.
 *
 * Read through the same defensive path whether it arrived on the stream or out
 * of a stored message, for the reason the tool calls are: two readers for one
 * shape drift, and the drift shows up only on a reconnect.
 *
 * An announcement with no id is dropped rather than rendered. The id is the
 * whole of what the row is fetched by, so a card without one is a button that
 * opens nothing — which reads to a reader as a picture they are not allowed to
 * see.
 */
export function readDeskViews(value: unknown): SignalDeskAnnouncement[] {
  if (!Array.isArray(value)) return []
  const deskViews: SignalDeskAnnouncement[] = []
  for (const item of value) {
    const record = asRecord(item)
    if (record === null) continue
    const artifactId = asString(record.artifactId)
    if (artifactId === "") continue
    const title = asString(record.title)
    const studyName = asString(record.studyName)
    deskViews.push({
      artifactId,
      studyName,
      // A desk view with no title still gets a name a person can read: the panel
      // and the card in the transcript are both labelled by it.
      title: title === "" ? SIGNAL_DESK_COPY.name : title,
      // Zero is honest when nothing said otherwise — the skeleton is then one
      // block tall and grows when the fetch lands, rather than guessing high.
      blockCount: asNumber(record.blockCount, 0),
      round: asNumber(record.round, 0),
    })
  }
  return deskViews
}

/** The narration of a Turn, by round, empty entries dropped. */
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

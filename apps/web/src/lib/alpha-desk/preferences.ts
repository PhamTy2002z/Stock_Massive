/**
 * What this browser remembers about how the reader likes to work.
 *
 * **`localStorage`, where `desk-session` uses `sessionStorage`, and the
 * difference is the whole point.** A desk session records what *this tab* was
 * looking at: two tabs are two workspaces, and one must not drag the other's
 * conversation around. A preference is the opposite — it is not about a tab at
 * all, so a second tab and a reload should both inherit it.
 *
 * It stops at this browser. Carrying a preference across devices needs a row
 * per user and an endpoint to write it, and neither exists yet; a reader who
 * signs in elsewhere meets the defaults. That is a real limit rather than a
 * hidden one, and the settings copy says so.
 *
 * Every field is optional in the stored record and every reader is total. A
 * record written before a field existed is not corrupt — it is a browser that
 * has no opinion about that field, and the default is the correct reading of
 * it.
 */

import { guardedStore } from "./guarded-storage"

const store = guardedStore(() => window.localStorage, "alpha-desk.preferences")

export interface Preferences {
  /**
   * Whether the sidebar was left collapsed, or null for "never said".
   *
   * Null rather than a boolean default so the shell can distinguish a reader
   * who collapsed it from one who has not touched it, and so a later change to
   * the opening default is not silently overridden by every existing browser.
   */
  sidebarOpen: boolean | null
  /** The chat column width the reader dragged to, in px, or null. */
  chatWidth: number | null
}

export const DEFAULT_PREFERENCES: Preferences = {
  sidebarOpen: null,
  chatWidth: null,
}

export function readPreferences(): Preferences {
  const raw = store.read()
  if (raw === null) return DEFAULT_PREFERENCES

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    // Someone else's key, or a truncated write. Defaults are the right reading.
    return DEFAULT_PREFERENCES
  }
  if (typeof parsed !== "object" || parsed === null) return DEFAULT_PREFERENCES

  const record = parsed as Record<string, unknown>
  return {
    sidebarOpen: flag(record.sidebarOpen),
    chatWidth: width(record.chatWidth),
  }
}

/**
 * Merge one or more fields into the stored record.
 *
 * A merge rather than a write so two independent callers — the settings dialog
 * and the shell's own layout — cannot erase each other's field by saving the
 * shape they happen to know about.
 */
export function writePreferences(patch: Partial<Preferences>): Preferences {
  const next = { ...readPreferences(), ...patch }
  store.write(JSON.stringify(next))
  return next
}

function flag(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null
}

/**
 * A stored width, or null.
 *
 * Bounds are not applied here: what a width is allowed to be depends on the
 * viewport it is being restored into, and only the shell knows that. This
 * refuses what could never be a width at all.
 */
function width(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return null
  }
  return value
}

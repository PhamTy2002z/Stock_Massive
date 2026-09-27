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

export const PREFERENCES_KEY = "alpha-desk.preferences"

const store = guardedStore(() => window.localStorage, PREFERENCES_KEY)

/** `system` follows the operating system's reduced-motion setting; `reduced` always stills. */
export type MotionPreference = "system" | "reduced"

export interface Preferences {
  /**
   * Whether a *new* conversation starts with the Signal Desk switched on.
   *
   * The default for a Thread that has no history, not an override for one that
   * does: the mode belongs to a conversation, and `desk-session` restores what
   * each one was actually doing. This only answers the question that arises
   * when there is nothing to restore.
   *
   * It expresses a wish, never an entitlement. The composer's toggle is still
   * the one edge an entitlement check attaches to, so a reader whose plan does
   * not carry the desk gets the same refusal here as there.
   */
  signalDeskByDefault: boolean
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
  /** Whether this browser stills motion even where the system does not ask. */
  motion: MotionPreference
  /**
   * Whether a Turn that settles while this tab is hidden raises a system
   * notification. A wish: the browser's own permission still decides.
   */
  notifyOnAnswer: boolean
  /** Whether a Turn that settles while this tab is hidden plays a short tone. */
  soundOnAnswer: boolean
}

export const DEFAULT_PREFERENCES: Preferences = {
  signalDeskByDefault: false,
  sidebarOpen: null,
  chatWidth: null,
  motion: "system",
  notifyOnAnswer: false,
  soundOnAnswer: false,
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
    signalDeskByDefault: flag(record.signalDeskByDefault) ?? false,
    sidebarOpen: flag(record.sidebarOpen),
    chatWidth: width(record.chatWidth),
    motion: record.motion === "reduced" ? "reduced" : "system",
    notifyOnAnswer: flag(record.notifyOnAnswer) ?? false,
    soundOnAnswer: flag(record.soundOnAnswer) ?? false,
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

/**
 * Put the motion preference on the document, where the stylesheet reads it.
 *
 * An attribute rather than a class, so it cannot collide with the theme class
 * `next-themes` owns on the same element.
 */
export function applyMotion(motion: MotionPreference): void {
  if (typeof document === "undefined") return
  if (motion === "reduced") document.documentElement.dataset.motion = "reduced"
  else delete document.documentElement.dataset.motion
}

/**
 * The same thing, before the first paint.
 *
 * Inlined into the document head by the root layout, so a reader who asked for
 * stillness never sees the first screen animate in. It repeats the reader
 * above in miniature because it runs before any bundle has loaded.
 */
export const MOTION_BOOT_SCRIPT = `try{var p=JSON.parse(localStorage.getItem(${JSON.stringify(
  PREFERENCES_KEY,
)})||"null");if(p&&p.motion==="reduced")document.documentElement.dataset.motion="reduced"}catch(e){}`

/**
 * Whether motion should be stilled right now: by this browser's preference or
 * by the system's. For the few places that animate from script rather than CSS.
 */
export function motionReduced(): boolean {
  if (typeof window === "undefined") return false
  if (document.documentElement.dataset.motion === "reduced") return true
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false
}

/**
 * Which of the day's greeting lines is on screen, and for how long.
 *
 * Split from `greeting` because the lines are copy and this is storage: the
 * failure modes here are a browser that refuses `localStorage` and a value some
 * older build wrote, neither of which has anything to do with what the lines
 * say.
 */

/**
 * How long one drawn line stays the line.
 *
 * The roll used to be thrown per mount, which meant every trip back to the
 * new-conversation screen dealt a new greeting — the screen read as restless,
 * and a joke that lands once stops landing when it is replaced three seconds
 * later. Two hours is long enough that a working session opens on one line, and
 * short enough that the line still turns over across a day.
 */
export const GREETING_ROLL_TTL_MS = 2 * 60 * 60 * 1000

const ROLL_KEY = "visgnite.greeting-roll"

interface StoredRoll {
  roll: number
  /** Epoch ms after which the roll is spent. */
  until: number
}

/**
 * The roll to open on, held for {@link GREETING_ROLL_TTL_MS} once drawn.
 *
 * Reading and writing in the same call is deliberate: the window starts when a
 * line is actually shown, not when some earlier tab happened to draw one.
 *
 * `localStorage` rather than `sessionStorage` — the point is that a second tab
 * and tomorrow morning's reload see the same line, which is exactly what a
 * per-tab store would not give. Every access is guarded: `localStorage` throws
 * rather than returning null in a Safari private window, and a greeting is not
 * worth a blank page. Storage being unavailable degrades to the old behaviour,
 * a fresh line per mount.
 *
 * Server-side there is no storage and no reader, so this hands back a plain
 * draw; the screen renders `plainGreeting` in that state anyway.
 */
export function stickyRoll(now = Date.now()): number {
  const stored = readRoll()
  if (stored !== null && stored.until > now) return stored.roll

  const roll = Math.random()
  writeRoll({ roll, until: now + GREETING_ROLL_TTL_MS })
  return roll
}

function readRoll(): StoredRoll | null {
  let raw: string | null
  try {
    raw = window.localStorage.getItem(ROLL_KEY)
  } catch {
    return null
  }
  if (raw === null) return null

  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== "object" || parsed === null) return null
    const { roll, until } = parsed as Partial<StoredRoll>
    // `roll` has to be in `Math.random()`'s own range for `greetingFor` to index
    // safely, and a non-finite `until` would read as a window that never closes.
    if (typeof roll !== "number" || !(roll >= 0 && roll < 1)) return null
    if (typeof until !== "number" || !Number.isFinite(until)) return null
    return { roll, until }
  } catch {
    return null
  }
}

function writeRoll(value: StoredRoll): void {
  try {
    window.localStorage.setItem(ROLL_KEY, JSON.stringify(value))
  } catch {
    // Full, or blocked. The line still renders; it just will not be sticky.
  }
}

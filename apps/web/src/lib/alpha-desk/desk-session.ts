/**
 * What this tab was doing, so a reload or a route change can pick it up again.
 *
 * A Turn belongs to the backend and keeps running whatever the browser does
 * (ADR-0013). Reattaching to one only needs its id — but the surface has no way
 * to ask *"which of my Turns is still running"*, because a Turn is reached
 * through the Thread that owns it and the transport publishes no such listing.
 * So the id is remembered here, on the way out.
 *
 * `sessionStorage` rather than `localStorage`: this is what *this tab* was
 * looking at. Two tabs on Alpha Desk are two workspaces, and sharing the key
 * would make one of them jump to the other's Thread on the next reload.
 *
 * Every access is guarded. `sessionStorage` throws rather than returning null
 * in a Safari private window and in an iframe with third-party storage blocked,
 * and none of that is worth a blank page.
 */

const KEY = "alpha-desk.session"

export interface DeskSession {
  /** The Thread on screen. Null before the first question is asked. */
  threadId: string | null
  /** A Turn that had not settled when this tab last rendered. */
  turnId: string | null
  /** The workspace lens. Remembered so a reload does not lose the context. */
  activeSymbol: string | null
}

const EMPTY: DeskSession = { threadId: null, turnId: null, activeSymbol: null }

export function readDeskSession(): DeskSession {
  const raw = safeRead()
  if (raw === null) return EMPTY
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== "object" || parsed === null) return EMPTY
    const { threadId, turnId, activeSymbol } = parsed as Partial<DeskSession>
    return {
      threadId: typeof threadId === "string" ? threadId : null,
      turnId: typeof turnId === "string" ? turnId : null,
      activeSymbol: typeof activeSymbol === "string" ? activeSymbol : null,
    }
  } catch {
    // Written by an older build, or by something else entirely. Starting fresh
    // is the honest reading of a value this cannot understand.
    return EMPTY
  }
}

export function writeDeskSession(session: DeskSession): void {
  if (
    session.threadId === null &&
    session.turnId === null &&
    session.activeSymbol === null
  ) {
    safeRemove()
    return
  }
  safeWrite(JSON.stringify(session))
}

/**
 * What the surface opens onto, given the URL and what this tab remembers.
 *
 * Two entry points, and they mean opposite things. A deep link is a fresh
 * intention: `?symbol=HPG` carries the symbol into context as the active lens
 * and **opens a new free-roaming Thread** (`docs/specs/0002` §7). Restoring the
 * remembered Thread there would drop the arriving symbol into a conversation
 * about something else. An ordinary arrival is a return, and picks up whatever
 * was on screen — including a Turn that is still running, because the backend
 * owns it and a reload ends only the subscriber.
 *
 * That distinction is why the caller strips `?symbol=` from the URL once this
 * has read it. Left in place, every subsequent reload would look like a fresh
 * deep link and abandon the Turn the user is watching.
 *
 * The remembered Turn travels with the remembered Thread and never without it:
 * a Turn shown under a Thread it does not belong to would render a draft that
 * the transcript then refuses to reconcile.
 *
 * `?thread=` is the third entry point and the most specific of them: it is the
 * sidebar menu's *Open in new tab*, and it names the conversation to open. It
 * outranks `?symbol=` — a link that says which Thread to show is not asking for
 * a new one — and it carries no Turn, because this tab has never subscribed to
 * one and the transport publishes no way to ask which of a Thread's Turns is
 * still running.
 */
export function openingState(
  deepLinkedSymbol: string | null,
  session: DeskSession,
  deepLinkedThreadId: string | null = null,
): { threadId: string | null; turnId: string | null; activeSymbol: string | null } {
  if (deepLinkedThreadId !== null) {
    return {
      threadId: deepLinkedThreadId,
      turnId: null,
      activeSymbol: session.activeSymbol,
    }
  }
  if (deepLinkedSymbol !== null) {
    return { threadId: null, turnId: null, activeSymbol: deepLinkedSymbol }
  }
  return {
    threadId: session.threadId,
    turnId: session.threadId === null ? null : session.turnId,
    activeSymbol: session.activeSymbol,
  }
}

/** A `?symbol=` value, or null. Normalised the way the API normalises one. */
export function deepLinkedSymbol(raw: string | null): string | null {
  const trimmed = (raw ?? "").trim().toUpperCase()
  return /^[A-Z0-9]{3,10}$/.test(trimmed) ? trimmed : null
}

/**
 * A `?thread=` value, or null.
 *
 * Checked against the shape a Thread id actually has, so a hand-edited URL
 * becomes "no deep link" rather than a request for `/threads/../admin`. The
 * backend refuses a Thread that is not the caller's anyway; this is what keeps
 * the malformed case from ever being asked.
 */
export function deepLinkedThread(raw: string | null): string | null {
  const trimmed = (raw ?? "").trim().toLowerCase()
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(trimmed)
    ? trimmed
    : null
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

function safeRead(): string | null {
  try {
    return storage()?.getItem(KEY) ?? null
  } catch {
    return null
  }
}

function safeWrite(value: string): void {
  try {
    storage()?.setItem(KEY, value)
  } catch {
    // Storage is full or blocked. The Turn keeps running either way; only the
    // reattach after a reload is lost, and that is not worth an error.
  }
}

function safeRemove(): void {
  try {
    storage()?.removeItem(KEY)
  } catch {
    // As above.
  }
}

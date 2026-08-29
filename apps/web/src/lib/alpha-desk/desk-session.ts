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

import { guardedStore } from "./guarded-storage"

const KEY = "alpha-desk.session"

export interface DeskSession {
  /** The Thread on screen. Null before the first question is asked. */
  threadId: string | null
  /** A Turn that had not settled when this tab last rendered. */
  turnId: string | null
  /** The workspace lens. Remembered so a reload does not lose the context. */
  activeSymbol: string | null
  /**
   * The Threads this tab has the Signal Desk switched on for, newest first.
   *
   * A list rather than one flag, because the desk is a property of a
   * conversation and not of the tab: opening yesterday's Thread has to restore
   * what *that* conversation was doing, and carrying the previous Thread's
   * answer forward would open a workspace over a conversation that never had
   * one. Only the "on" Threads are named — "off" is the default and needs no
   * record — and the list is capped, because a tab that ran forty conversations
   * does not need to remember the first thirty.
   *
   * Optional because a record written before the desk existed does not carry
   * it, and "this tab remembers no desks" is the correct reading of that.
   */
  signalDeskThreads?: string[]
  /**
   * Attachments uploaded for a question that has not been sent yet, by id.
   *
   * Remembered because the rows already exist server-side the moment a file is
   * chosen. Without this a reload loses the chips while the rows sit in the
   * database until the orphan sweep — the surface forgetting about bytes it
   * caused, which is how a quota fills with files nobody can see.
   *
   * Optional for the same reason the desk list is: a record written before this
   * existed carries none, and "nothing pending" is the right reading.
   */
  pendingAttachments?: string[]
}

/** How many Threads' worth of desk state one tab keeps. */
const SIGNAL_DESK_MEMORY = 24

const EMPTY: DeskSession = {
  threadId: null,
  turnId: null,
  activeSymbol: null,
  signalDeskThreads: [],
  pendingAttachments: [],
}

export function readDeskSession(): DeskSession {
  const raw = safeRead()
  if (raw === null) return EMPTY
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== "object" || parsed === null) return EMPTY
    const { threadId, turnId, activeSymbol, signalDeskThreads, pendingAttachments } =
      parsed as Partial<DeskSession>
    return {
      threadId: typeof threadId === "string" ? threadId : null,
      turnId: typeof turnId === "string" ? turnId : null,
      activeSymbol: typeof activeSymbol === "string" ? activeSymbol : null,
      // Written by a build that predates the desk, or by a hand-edited value.
      // Either way an unreadable list is no list rather than a crash.
      signalDeskThreads: Array.isArray(signalDeskThreads)
        ? signalDeskThreads.filter((id): id is string => typeof id === "string")
        : [],
      pendingAttachments: Array.isArray(pendingAttachments)
        ? pendingAttachments.filter((id): id is string => typeof id === "string")
        : [],
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
    session.activeSymbol === null &&
    (session.signalDeskThreads?.length ?? 0) === 0 &&
    (session.pendingAttachments?.length ?? 0) === 0
  ) {
    safeRemove()
    return
  }
  safeWrite(JSON.stringify(session))
}

/** Whether the Signal Desk was left on for one Thread. Off is the default. */
export function signalDeskOn(session: DeskSession, threadId: string | null): boolean {
  return threadId !== null && (session.signalDeskThreads ?? []).includes(threadId)
}

/**
 * The remembered list with one Thread's answer written into it.
 *
 * Newest first and capped, so the entry that falls off the end is the
 * conversation this tab has gone longest without touching. Returns the list it
 * was given when nothing changed, so the caller's state does not churn on every
 * render that re-states the same fact.
 */
export function rememberSignalDesk(
  threads: string[],
  threadId: string,
  on: boolean,
): string[] {
  const without = threads.filter((id) => id !== threadId)
  if (!on) return without.length === threads.length ? threads : without
  if (threads[0] === threadId) return threads
  return [threadId, ...without].slice(0, SIGNAL_DESK_MEMORY)
}

// -- pinned boards ---------------------------------------------------------

/**
 * Which boards a Thread keeps at the top of its list, remembered across
 * sessions.
 *
 * `localStorage` rather than the `sessionStorage` above, and that difference is
 * the whole point: what this *tab* was looking at is a tab's business, but "the
 * two boards I work from in this conversation" is a decision about the
 * conversation, and a reader who made it on Monday should not have to make it
 * again on Tuesday in a new window.
 *
 * Keyed by Thread inside one record rather than one key per Thread, so
 * forgetting the oldest conversations is a slice rather than a scan of the
 * whole origin's storage.
 */
const PINS_KEY = "alpha-desk.board-pins"

/** How many Threads' worth of pins one browser keeps. */
const PIN_MEMORY = 24

/** How many pins one Thread's record may hold, so storage stays bounded. */
const PINS_PER_THREAD = 5

const pins = guardedStore(() => window.localStorage, PINS_KEY)

/** Every Thread's pins, unreadable storage read as "none". */
function readAllPinnedBoards(): Record<string, string[]> {
  const raw = pins.read()
  if (raw === null) return {}
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {}
    const record: Record<string, string[]> = {}
    for (const [threadId, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (!Array.isArray(value)) continue
      record[threadId] = value.filter((id): id is string => typeof id === "string")
    }
    return record
  } catch {
    // Written by an older build, or by something else entirely. An unreadable
    // record is no pins rather than a blank workspace.
    return {}
  }
}

/** The boards pinned in one Thread, in pin order. Empty for an unknown Thread. */
export function readPinnedBoards(threadId: string | null): string[] {
  if (threadId === null) return []
  return readAllPinnedBoards()[threadId] ?? []
}

/**
 * Write one Thread's pins, dropping the least recently written Thread.
 *
 * The Thread being written goes first, so "least recently written" is simply
 * the tail — a conversation nobody has pinned anything in for twenty-four
 * conversations is the one whose pins are worth least.
 */
export function writePinnedBoards(threadId: string | null, artifactIds: string[]): void {
  if (threadId === null) return
  const all = readAllPinnedBoards()
  delete all[threadId]
  const kept = Object.entries(all).slice(0, PIN_MEMORY - 1)
  const next: Record<string, string[]> = {}
  if (artifactIds.length > 0) next[threadId] = artifactIds.slice(0, PINS_PER_THREAD)
  for (const [id, value] of kept) next[id] = value
  pins.write(JSON.stringify(next))
}

/**
 * Forget what this tab was doing.
 *
 * Called from the way in. A remembered Thread is a convenience for a reload of
 * the desk, not a place to be returned to across a sign-in: someone who has just
 * given their password is starting, and dropping them into whichever
 * conversation this tab had open before reads as the app deciding for them.
 * Clearing it here rather than after the redirect keeps the decision on the one
 * screen that means "a session begins now".
 */
export function clearDeskSession(): void {
  safeRemove()
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

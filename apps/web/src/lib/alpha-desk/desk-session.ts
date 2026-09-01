/** Tab-local state needed to restore a conversation and reattach a live Turn. */

const KEY = "alpha-desk.session"

export interface DeskSession {
  threadId: string | null
  turnId: string | null
  activeSymbol: string | null
  pendingAttachments?: string[]
}

const EMPTY: DeskSession = {
  threadId: null,
  turnId: null,
  activeSymbol: null,
  pendingAttachments: [],
}

export function readDeskSession(): DeskSession {
  const raw = safeRead()
  if (raw === null) return EMPTY
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>
    return {
      threadId: typeof parsed.threadId === "string" ? parsed.threadId : null,
      turnId: typeof parsed.turnId === "string" ? parsed.turnId : null,
      activeSymbol:
        typeof parsed.activeSymbol === "string" ? parsed.activeSymbol : null,
      pendingAttachments: Array.isArray(parsed.pendingAttachments)
        ? parsed.pendingAttachments.filter(
            (id): id is string => typeof id === "string",
          )
        : [],
    }
  } catch {
    return EMPTY
  }
}

export function writeDeskSession(session: DeskSession): void {
  if (
    session.threadId === null &&
    session.turnId === null &&
    session.activeSymbol === null &&
    (session.pendingAttachments?.length ?? 0) === 0
  ) {
    safeRemove()
    return
  }
  safeWrite(JSON.stringify(session))
}

export function clearDeskSession(): void {
  safeRemove()
}

export function openingState(
  linkedSymbol: string | null,
  session: DeskSession,
  linkedThreadId: string | null = null,
): { threadId: string | null; turnId: string | null; activeSymbol: string | null } {
  if (linkedThreadId !== null) {
    return {
      threadId: linkedThreadId,
      turnId: null,
      activeSymbol: session.activeSymbol,
    }
  }
  if (linkedSymbol !== null) {
    return { threadId: null, turnId: null, activeSymbol: linkedSymbol }
  }
  return {
    threadId: session.threadId,
    turnId: session.threadId === null ? null : session.turnId,
    activeSymbol: session.activeSymbol,
  }
}

export function deepLinkedSymbol(raw: string | null): string | null {
  const trimmed = (raw ?? "").trim().toUpperCase()
  return /^[A-Z0-9]{3,10}$/.test(trimmed) ? trimmed : null
}

export function deepLinkedThread(raw: string | null): string | null {
  const trimmed = (raw ?? "").trim().toLowerCase()
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
    trimmed,
  )
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
    // Losing reload convenience is preferable to losing the active Turn.
  }
}

function safeRemove(): void {
  try {
    storage()?.removeItem(KEY)
  } catch {
    // Storage may be unavailable in private browsing.
  }
}

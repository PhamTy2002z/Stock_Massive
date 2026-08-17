/**
 * Whether every API operation which went unavailable has recovered.
 *
 * A restarting container, an exhausted rate limit and a dropped wifi all look
 * the same from a component's point of view: the data is not here *yet*. None
 * of them is the user's problem to solve, and none of them is worth an error
 * screen — the system comes back on its own within seconds. So they collapse
 * into a single "waiting" state that the UI can veil the page with, and that
 * clears itself once every unavailable operation answers again.
 *
 * Kept outside React so the fetch layer can report each unavailable operation
 * by URL without every call site having to thread a callback down. A healthy
 * operation cannot clear a different operation's failure.
 */

export type ConnectionState = "ready" | "waiting"

/** Statuses that mean "ask again shortly", not "this request was wrong". */
const RETRYABLE_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504])

export function isRetryableStatus(status: number): boolean {
  return RETRYABLE_STATUSES.has(status)
}

/**
 * The cheapest question that proves the API is answering again.
 *
 * `/health` is mounted on the app root rather than under the versioned API
 * prefix, so the probe strips the prefix off the configured base rather than
 * appending to it — otherwise the recovery poll asks a 404 whether the server
 * is alive and never believes the answer.
 */
export function healthUrlFrom(baseUrl: string): string {
  return `${baseUrl.replace(/\/+$/, "").replace(/\/api\/v\d+$/, "")}/health`
}

type Listener = () => void

class ConnectionStatus {
  private state: ConnectionState = "ready"
  private unavailableRequests = new Set<string>()
  private listeners = new Set<Listener>()

  get(): ConnectionState {
    return this.state
  }

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /** Called by the fetch layer when one request could not be answered. */
  reportWaiting(requestKey: string): void {
    this.unavailableRequests.add(requestKey)
    this.set("waiting")
  }

  /** Clears only the operation which has demonstrably recovered. */
  reportReady(requestKey: string): void {
    this.unavailableRequests.delete(requestKey)
    if (this.unavailableRequests.size === 0) {
      this.set("ready")
    }
  }

  /** Test seam. Production code never needs to force the state. */
  reset(): void {
    this.state = "ready"
    this.unavailableRequests.clear()
    this.listeners.clear()
  }

  private set(next: ConnectionState): void {
    if (this.state === next) return
    this.state = next
    this.listeners.forEach((listener) => listener())
  }
}

export const connectionStatus = new ConnectionStatus()

/**
 * A request that failed for a reason the user can neither cause nor fix.
 *
 * Separate from ApiError so the UI can veil and wait instead of reporting: a
 * 404 is an answer, a 503 is silence.
 */
export class ApiUnavailableError extends Error {
  constructor(
    message = "Hệ thống đang không phản hồi. Đang thử lại…",
    public readonly status?: number,
    options?: ErrorOptions
  ) {
    super(message, options)
    this.name = "ApiUnavailableError"
  }
}

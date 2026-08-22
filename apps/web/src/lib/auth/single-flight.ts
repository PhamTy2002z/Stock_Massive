/**
 * One exchange per refresh token, remembered for a short while after it lands.
 *
 * The refresh token rotates: exchanging it revokes it. The upstream goes
 * further and treats a *second* presentation of a revoked token as a stolen
 * credential — it revokes every session the user has, which is the correct
 * answer to a replay and a catastrophic one to a race. So the client's job is
 * not "one exchange at a time", it is **one exchange per token, ever**.
 *
 * A plain single flight cannot promise that, and the difference is where this
 * app actually broke. Cookies are per-request: every request the browser had in
 * the air when the access token expired carries the *same* refresh cookie, and
 * the new pair only reaches the browser on the response that rotated it. A
 * caller whose `401` comes back a moment after the first exchange settled is
 * therefore holding a token that is already spent — a fresh question to a
 * window-based flight, a replay to the upstream, and a signed-out user either
 * way.
 *
 * Keying by the token and remembering the answer for `ttlMs` closes that gap:
 * the straggler is handed the pair its own token bought rather than spending it
 * twice. The memo is short-lived because it holds credentials and because the
 * only callers it needs to serve are the ones from the same burst.
 *
 * A rejected exchange is evicted immediately. Nothing was spent, the failure is
 * usually the network, and a cached rejection would make one bad moment outlive
 * itself.
 *
 * **Process-local**, which is the whole of the guarantee: two Next instances
 * behind a load balancer would still race, and fixing that needs shared state
 * rather than a bigger map.
 */

export interface KeyedFlightOptions {
  /** How long a settled answer stays available to a caller holding the same key. */
  ttlMs: number
}

interface Entry<T> {
  promise: Promise<T>
  /** Null while the work is still running; a timestamp once it resolved. */
  settledAt: number | null
}

export function keyedSingleFlight<T>(
  work: (key: string) => Promise<T>,
  { ttlMs }: KeyedFlightOptions,
): (key: string) => Promise<T> {
  const entries = new Map<string, Entry<T>>()

  return (key) => {
    prune(entries, ttlMs)

    const existing = entries.get(key)
    if (existing) return existing.promise

    const entry: Entry<T> = { promise: undefined as unknown as Promise<T>, settledAt: null }
    // Assigned before anything is awaited, and `work` is called synchronously:
    // a caller arriving in the same tick finds the promise rather than an empty
    // slot. A rewrite that awaits the key first reopens the race it closes.
    entry.promise = work(key).then(
      (value) => {
        entry.settledAt = Date.now()
        return value
      },
      (error) => {
        entries.delete(key)
        throw error
      },
    )
    entries.set(key, entry)
    return entry.promise
  }
}

/** Drop answers nobody from the original burst can still be waiting for. */
function prune<T>(entries: Map<string, Entry<T>>, ttlMs: number): void {
  const now = Date.now()
  for (const [key, entry] of entries) {
    if (entry.settledAt !== null && now - entry.settledAt > ttlMs) entries.delete(key)
  }
}

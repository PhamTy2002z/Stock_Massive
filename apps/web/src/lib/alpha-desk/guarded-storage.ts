/**
 * Web storage that cannot throw, for the places where losing it is survivable.
 *
 * Every access is guarded, because `localStorage` and `sessionStorage` do not
 * merely return null when they are unavailable — reading the property itself
 * throws in a browser configured to block site data, and `setItem` throws when
 * the quota is full or the page is in a partitioned third-party context. An
 * unguarded read is therefore a blank workspace rather than a lost preference.
 *
 * Nothing load-bearing lives behind this. A preference that failed to persist
 * has to leave the product working at its default, which is what makes
 * swallowing the failure the right answer rather than a hidden one.
 */

export interface GuardedStore {
  read: () => string | null
  write: (value: string) => void
  remove: () => void
}

/**
 * One key in one storage area, wrapped so no caller needs a `try`.
 *
 * `area` is a function rather than the `Storage` itself: the object does not
 * exist during a server render, and resolving it at module scope would evaluate
 * it there.
 */
export function guardedStore(area: () => Storage, key: string): GuardedStore {
  function resolve(): Storage | null {
    if (typeof window === "undefined") return null
    try {
      return area()
    } catch {
      return null
    }
  }

  return {
    read() {
      try {
        return resolve()?.getItem(key) ?? null
      } catch {
        return null
      }
    },
    write(value: string) {
      try {
        resolve()?.setItem(key, value)
      } catch {
        // Full, blocked, or partitioned. The caller's default still applies.
      }
    },
    remove() {
      try {
        resolve()?.removeItem(key)
      } catch {
        // As above.
      }
    },
  }
}

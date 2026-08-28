// Query keys — trimmed to what the chat lane still reads.
//
// Every market key (indices, price board, monitor, sectors, fund
// certificates, stock detail, financials, insider deals, sector peers,
// intraday order stats, volume analysis) was dropped on 2026-08-25 with the
// market surfaces. What survives is the auth key and the thread keys, which
// are what ``use-auth``, ``use-threads`` and ``use-live-turn`` reach for.

export const queryKeys = {
  currentUser: ["auth", "currentUser"] as const,

  threads: ["threads"] as const,
  thread: (threadId: string) => ["thread", threadId] as const,

  // One Study run. Immutable by design — the row is written once and never
  // updated — so the panel caches it with `staleTime: Infinity` and re-opening
  // a Thread renders what was frozen rather than refetching a moved store.
  artifact: (artifactId: string) => ["artifact", artifactId] as const,

  // This account's allowance. Unlike `artifact`, it moves: every Turn spends
  // against it and the daily half expires at Vietnamese midnight.
  usage: ["usage"] as const,
}

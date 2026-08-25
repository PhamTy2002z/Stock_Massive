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
}

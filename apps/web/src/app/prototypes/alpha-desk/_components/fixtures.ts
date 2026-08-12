/** PROTOTYPE — throwaway fixtures for issue #22. */

export const STATES = ["ready", "tool", "artifact", "pending", "empty", "deep"] as const
export type HarnessState = (typeof STATES)[number]

export interface ThreadFixture {
  id: string
  title: string
  preview: string
  symbols: string[]
  time: string
  active?: boolean
}

export interface WatchSymbol {
  symbol: string
  verdict: "Hold" | "Watch" | "Reduce" | "Pending" | "Failed"
  session: string
  unread?: boolean
  tone: "neutral" | "positive" | "negative" | "waiting"
}

export const THREADS: ThreadFixture[] = [
  {
    id: "t1",
    title: "VCB sau phiên 11/08",
    preview: "Chất lượng tài sản đi ngang…",
    symbols: ["VCB"],
    time: "21:14",
    active: true,
  },
  {
    id: "t2",
    title: "So sánh VHM và KDH",
    preview: "Dòng ngoại là điểm phân kỳ lớn nhất.",
    symbols: ["VHM", "KDH"],
    time: "Hôm qua",
  },
  {
    id: "t3",
    title: "MWG: biên lợi nhuận",
    preview: "Gross margin đã hồi hai quý…",
    symbols: ["MWG"],
    time: "09/08",
  },
]

export const WATCHLIST: WatchSymbol[] = [
  { symbol: "VCB", verdict: "Hold", session: "11/08", unread: true, tone: "neutral" },
  { symbol: "VHM", verdict: "Reduce", session: "11/08", unread: true, tone: "negative" },
  { symbol: "MWG", verdict: "Watch", session: "11/08", tone: "positive" },
  { symbol: "FPT", verdict: "Pending", session: "11/08", tone: "waiting" },
  { symbol: "HPG", verdict: "Hold", session: "11/08", tone: "neutral" },
]

export const STATE_LABELS: Record<HarnessState, string> = {
  ready: "Fast reply",
  tool: "Running tool",
  artifact: "Finished Analysis",
  pending: "On-demand wait",
  empty: "First run",
  deep: "Deep link",
}

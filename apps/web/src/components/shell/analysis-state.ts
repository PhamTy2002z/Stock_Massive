import type { AnalysisState, RunFailure } from "@/lib/alpha"

/**
 * What the Watchlist says about a symbol's Analysis, in one place.
 *
 * The rail this came from rendered a sentence under every row. The sidebar
 * does not have that room — a row is one line of symbol, price and delta — so
 * the sentence is carried by the state dot's accessible name instead of being
 * printed. Same five sentences, one surface narrower.
 *
 * They live here rather than inline in the component so that the five states
 * are five sentences in one file: a state that renders as a bare dot with no
 * sentence is then a visible omission rather than something to catch on screen.
 */

/**
 * A session as the Watchlist names it: *"phiên 08/08"*, never "today".
 *
 * The latest session with a Snapshot is frequently not today — Saturday shows
 * Friday, a holiday shows the day before it — so saying "today" would be lying
 * in the one place a user checks first.
 */
export function sessionLabel(tradingDay: string | null): string {
  if (!tradingDay) return "chưa có phiên nào chốt dữ liệu"
  return `phiên ${dayAndMonth(tradingDay)}`
}

/**
 * A Trading Day as `dd/mm`, read straight off the API's own string.
 *
 * Deliberately not parsed into a `Date` first. A Trading Day is a plain
 * calendar date with no instant behind it; turning it into one picks a zone,
 * and every zone west of UTC+7 then renders the day before — the sidebar would
 * name the wrong session for every reader outside Asia. There is nothing to
 * convert, so nothing converts it.
 */
export function dayAndMonth(tradingDay: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(tradingDay)
  return parts ? `${parts[3]}/${parts[2]}` : tradingDay
}

/**
 * The colour each state carries, as a dot.
 *
 * `unsupported` is deliberately not red: it is a fact about the Universe, not a
 * failure of anything. `pending` is the muted one because waiting is the
 * ordinary case — most symbols sit there for most of the morning.
 */
export const STATE_DOT: Record<AnalysisState, string> = {
  ready: "bg-emerald-500",
  pending: "bg-muted-foreground/40",
  producing: "bg-sky-500",
  failed: "bg-red-500",
  unsupported: "bg-amber-500",
}

/**
 * The one failure code that is a wait rather than a fault.
 *
 * The backend defers a run whose session has not been collected for this symbol
 * yet: the state stays `pending`, no attempt is spent, and the reason rides
 * along so the surface can say what is being waited on. Rendered as a previous
 * attempt's failure it would read as something going wrong once every twenty
 * minutes, which is the opposite of what is happening.
 */
export const WAITING_FOR_SESSION_DATA = "missing_market_snapshot"

export function waitingForSessionData(
  state: AnalysisState,
  failure: RunFailure | null | undefined,
): boolean {
  return state === "pending" && failure?.code === WAITING_FOR_SESSION_DATA
}

/**
 * Why a symbol is in the state it is in, as a sentence a person reads.
 *
 * Every state gets one, including the healthy ones. A surface that only
 * explains itself when something is wrong teaches the reader that silence
 * means nothing was checked.
 */
export function stateSentence(
  state: AnalysisState,
  tradingDay: string | null,
  failure: RunFailure | null = null,
): string {
  const session = sessionLabel(tradingDay)
  switch (state) {
    case "ready":
      return `Đã có Analysis cho ${session}.`
    case "pending":
      if (!tradingDay) return "Chưa có phiên nào chốt dữ liệu nên chưa dựng Analysis."
      // Two different waits, and the difference is the one a user asks about.
      // Queued behind other symbols is "not yet your turn"; waiting on the
      // Collector is "your turn came and the data had not arrived" — and the
      // backend holds the run rather than spending an attempt on it, so
      // nothing here is a failure to report.
      return waitingForSessionData(state, failure)
        ? `Đang chờ dữ liệu ${session} về cho mã này.`
        : `Chưa tới lượt dựng Analysis cho ${session}.`
    case "producing":
      return `Đang dựng Analysis cho ${session}.`
    case "failed":
      return `Chưa có Analysis cho ${session}.`
    case "unsupported":
      return "Mã không còn trong Universe nên hệ thống không dựng Analysis mới. Lịch sử vẫn đọc được."
  }
}

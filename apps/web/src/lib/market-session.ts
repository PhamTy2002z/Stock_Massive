// Which phase of the HOSE session the clock is in.
//
// Derived from the Ho Chi Minh City wall clock, the same way the API decides
// its cache TTLs. It reads the calendar only as far as weekends — a public
// holiday still reads as a trading day, so the label is a schedule, not a claim
// that a match just happened. The timestamp beside it is what proves freshness.

export type MarketPhase =
  | "pre-open"
  | "ato"
  | "continuous"
  | "lunch"
  | "atc"
  | "put-through"
  | "closed"

export interface MarketSession {
  phase: MarketPhase
  label: string
  /** Orders are matching now, so the indicator may pulse. */
  isLive: boolean
}

const VN_TIME_ZONE = "Asia/Ho_Chi_Minh"

/** Minutes since midnight in Vietnam, whatever the viewer's own time zone is. */
function vietnamMinutes(now: Date): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: VN_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now)

  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? "0")
  const minute = Number(parts.find((p) => p.type === "minute")?.value ?? "0")
  return hour * 60 + minute
}

function vietnamWeekday(now: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: VN_TIME_ZONE,
    weekday: "short",
  }).format(now)
}

const CLOSED: MarketSession = { phase: "closed", label: "Đã đóng cửa", isLive: false }

/** Boundaries in minutes from midnight, in session order. */
const PHASES: { until: number; session: MarketSession }[] = [
  { until: 9 * 60, session: { phase: "pre-open", label: "Chưa mở cửa", isLive: false } },
  { until: 9 * 60 + 15, session: { phase: "ato", label: "Phiên ATO", isLive: true } },
  {
    until: 11 * 60 + 30,
    session: { phase: "continuous", label: "Đang khớp lệnh", isLive: true },
  },
  { until: 13 * 60, session: { phase: "lunch", label: "Nghỉ trưa", isLive: false } },
  {
    until: 14 * 60 + 30,
    session: { phase: "continuous", label: "Đang khớp lệnh", isLive: true },
  },
  { until: 14 * 60 + 45, session: { phase: "atc", label: "Phiên ATC", isLive: true } },
  {
    until: 15 * 60,
    session: { phase: "put-through", label: "Giao dịch thoả thuận", isLive: false },
  },
]

export function getMarketSession(now: Date = new Date()): MarketSession {
  const weekday = vietnamWeekday(now)
  if (weekday === "Sat" || weekday === "Sun") return CLOSED

  const minutes = vietnamMinutes(now)
  return PHASES.find((p) => minutes < p.until)?.session ?? CLOSED
}

/**
 * Calendar date in Vietnam: the day a session traded or a period closed.
 *
 * The API dates both at midnight in Vietnam. Formatted in the viewer's own zone,
 * anywhere west of UTC+7 would render that instant as the day before and name
 * the wrong day — so the market's own zone is the only correct one to read it
 * in, whoever is looking.
 */
export function formatVietnamDate(
  value: string | Date | number | null | undefined
): string {
  if (value === null || value === undefined || value === "") return ""
  const moment = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(moment.getTime())) return ""
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(moment)
}

/**
 * The last `days` calendar days, as the ISO dates a series window is asked in.
 *
 * Calendar days rather than sessions: the caller does not know which of them
 * the exchange was open for, and the store answers with the ones it holds.
 */
export function recentWindow(days: number): { start: string; end: string } {
  const end = new Date()
  const start = new Date(end)
  start.setDate(start.getDate() - days)
  const iso = (date: Date) => date.toISOString().slice(0, 10)
  return { start: iso(start), end: iso(end) }
}

/** Clock time in Vietnam, for stamping when a quote was last read. */
export function formatVietnamTime(value: Date | number): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(value)
}

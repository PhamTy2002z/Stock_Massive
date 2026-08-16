import type { AnalysisState, OnDemandOutcome, RunFailure } from "@/lib/alpha"

/**
 * What the rail says, in the language each part of it belongs in.
 *
 * Chrome and field labels are English, matching the rest of the app. Everything
 * that explains a condition to a person is Vietnamese, and lives here rather
 * than inline in the components so that the five states are five sentences in
 * one place — a state that renders as a bare badge with no sentence is then a
 * visible omission rather than something to notice on screen.
 */

/**
 * A session as the rail names it: *"phiên 08/08"*, never "today".
 *
 * The latest session with a Snapshot is frequently not today — Saturday shows
 * Friday, a holiday shows the day before it — so a rail saying "today" would be
 * lying in the one place a user checks first.
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
 * and every zone west of UTC+7 then renders the day before — the rail would
 * name the wrong session for every reader outside Asia. There is nothing to
 * convert, so nothing converts it.
 */
export function dayAndMonth(tradingDay: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(tradingDay)
  return parts ? `${parts[3]}/${parts[2]}` : tradingDay
}

/** Chrome: the English label beside each state's colour. */
export const STATE_LABEL: Record<AnalysisState, string> = {
  ready: "Ready",
  pending: "Pending",
  producing: "Producing",
  failed: "Failed",
  unsupported: "Unsupported",
}

/**
 * The colour each state carries, as a dot.
 *
 * Here rather than in the row that first needed it, because the rail and the
 * Alpha Desk dock both show these five states and a second palette would mean
 * the same symbol reading amber in one place and red in the other.
 * `unsupported` is deliberately not red: it is a fact about the Universe, not a
 * failure of anything.
 */
export const STATE_DOT: Record<AnalysisState, string> = {
  ready: "bg-emerald-500",
  pending: "bg-muted-foreground/40",
  producing: "bg-sky-500",
  failed: "bg-red-500",
  unsupported: "bg-amber-500",
}

/**
 * Why a symbol is in the state it is in, as a sentence a person reads.
 *
 * Every state gets one, including the healthy ones. A rail that only explains
 * itself when something is wrong teaches the reader that silence means nothing
 * was checked.
 */
export function stateSentence(state: AnalysisState, tradingDay: string | null): string {
  const session = sessionLabel(tradingDay)
  switch (state) {
    case "ready":
      return `Đã có Analysis cho ${session}.`
    case "pending":
      return tradingDay
        ? `Chưa tới lượt dựng Analysis cho ${session}.`
        : "Chưa có phiên nào chốt dữ liệu nên chưa dựng Analysis."
    case "producing":
      return `Đang dựng Analysis cho ${session}.`
    case "failed":
      return `Chưa có Analysis cho ${session}.`
    case "unsupported":
      return "Mã không còn trong Universe nên hệ thống không dựng Analysis mới. Lịch sử vẫn đọc được."
  }
}

/**
 * The failure taxonomy as sentences.
 *
 * A closed set upstream, so an unrecognised code means the API grew one this
 * screen has not learned — which falls back to the sentence the API sent rather
 * than rendering the code itself. A code on screen is a dead end for the reader.
 */
const FAILURE_SENTENCE: Record<string, string> = {
  missing_market_snapshot: "Phiên này chưa có dữ liệu thị trường để dựng Analysis.",
  insufficient_core_evidence: "Không đủ dữ liệu cốt lõi cho mã này ở phiên đang xét.",
  auth_unavailable: "Không kết nối được tới dịch vụ mô hình.",
  llm_transport_error: "Dịch vụ mô hình không phản hồi.",
  invalid_model_output: "Kết quả mô hình trả về không đúng khuôn dạng.",
  persistence_error: "Không ghi được Analysis xuống cơ sở dữ liệu.",
  run_abandoned: "Lượt dựng bị gián đoạn giữa chừng và đã được thu dọn.",
}

export function failureSentence(failure: RunFailure): string | null {
  if (failure.code && FAILURE_SENTENCE[failure.code]) return FAILURE_SENTENCE[failure.code]
  return failure.message
}

/** What an addition did to the on-demand lane, where the user should be told. */
export function onDemandSentence(
  outcome: OnDemandOutcome,
  message: string | null,
): string | null {
  // The API sends the sentence for the two outcomes a person has to be told
  // about. A free join needs none: the rail already shows the symbol's state.
  if (outcome === "allowance_exhausted" || outcome === "no_snapshotted_session") {
    return message
  }
  return null
}

const VN_TIME_ZONE = "Asia/Ho_Chi_Minh"

// When the day's Collector run is expected to have landed a Snapshot. Before
// it, a session with no data is simply a session that has not been collected
// yet, and saying so would be noise every afternoon.
const COLLECTION_DEADLINE_MINUTES = 16 * 60 + 15

/** The parts of the Ho Chi Minh City wall clock this file reasons about. */
function vietnamNow(now: Date): { date: string; weekday: string; minutes: number } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: VN_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now)
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? ""

  return {
    date: `${value("year")}-${value("month")}-${value("day")}`,
    weekday: value("weekday"),
    // `hour12: false` renders midnight as 24 in some ICU builds.
    minutes: (Number(value("hour")) % 24) * 60 + Number(value("minute")),
  }
}

/**
 * The one system-level status line, or nothing.
 *
 * *"Dữ liệu phiên 12/08 chưa về."* — shown once for the whole rail rather than
 * once per symbol, because it is a statement about the collection run and not
 * about any one symbol's Analysis. Ten copies of a system fact would read as
 * ten separate problems.
 *
 * Three conditions, all of them required: a weekday, past the collection
 * deadline, and no Snapshot for today. Weekends show nothing at all — there was
 * no session to collect, so there is nothing late.
 *
 * The accepted cost of having no holiday calendar is that this fires once on a
 * public holiday: one redundant sentence, which is cheaper than an Analysis
 * labelled with a session that never happened.
 */
export function missingSessionNotice(
  tradingDay: string | null,
  now: Date = new Date(),
): string | null {
  const { date, weekday, minutes } = vietnamNow(now)

  if (weekday === "Sat" || weekday === "Sun") return null
  if (minutes < COLLECTION_DEADLINE_MINUTES) return null
  if (tradingDay === date) return null

  return `Dữ liệu ${sessionLabel(date)} chưa về.`
}

/**
 * The edge of the browsable window, said out loud.
 *
 * Only when something lies beyond it. A boundary announced on a symbol with
 * eleven Analyses would teach the reader that the rail always stops somewhere,
 * which is the opposite of what the line is for.
 */
export function historyBoundaryNotice(depth: number, olderExist: boolean): string | null {
  if (!olderExist) return null
  return `Chỉ hiển thị ${depth} phiên gần nhất. Analysis cũ hơn vẫn được lưu và tra cứu được theo ngày.`
}

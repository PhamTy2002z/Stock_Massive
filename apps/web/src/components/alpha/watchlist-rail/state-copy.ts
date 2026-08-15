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

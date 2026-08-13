/**
 * One Vietnamese sentence per Signal Issue code, in one place.
 *
 * The API answers with codes because prose cannot be grouped, counted or
 * restyled by the interface. That only works if the codes are translated
 * exactly once: written inline at each call site they drift, and the same
 * missing session ends up explained two different ways on two screens.
 *
 * An unknown code is rendered as a plain sentence rather than as the code
 * itself. A reader who sees `insufficient_history` learns nothing they can act
 * on, and a screen that leaks internal vocabulary teaches them to distrust the
 * parts they do understand.
 */

import type { SignalCoverageState, SignalFreshness } from "@/lib/api"

export type SignalIssueCode =
  | "missing_target_session"
  | "insufficient_history"
  | "recently_inactive"
  | "cohort_warming"
  | "lagging_market_data"
  | "stale_market_data"
  | "ranking_unavailable"

const SENTENCES: Record<SignalIssueCode, string> = {
  missing_target_session: "Chưa có dữ liệu phiên này",
  insufficient_history: "Chưa đủ 20 phiên để so sánh",
  recently_inactive: "Có phiên không phát sinh giao dịch trong 20 phiên gần nhất",
  cohort_warming: "Nhóm dẫn đầu lợi nhuận đang được nạp dữ liệu",
  lagging_market_data: "Đã có phiên mới hơn nhưng chưa đủ dữ liệu để tính",
  stale_market_data: "Dữ liệu phiên đã cũ hơn 7 ngày",
  ranking_unavailable: "Chưa có bảng xếp hạng lợi nhuận nào đang hiệu lực",
}

export function signalIssueSentence(code: string): string {
  return SENTENCES[code as SignalIssueCode] ?? "Có vấn đề về dữ liệu cho mục này"
}

/**
 * What the coverage state means for the answer on screen.
 *
 * Deliberately phrased as what the reader is looking at rather than as a status
 * name: "ready" says nothing about whether the fifty companies were all there.
 *
 * The state is typed rather than a bare string, so a state the API adds later
 * fails the build here instead of quietly falling through to the
 * "chưa đủ để kết luận" wording — which would tell the reader an answer is
 * unusable when it may be nothing of the sort.
 */
export function coverageSentence(
  state: SignalCoverageState,
  evaluated: number,
  total: number,
): string {
  if (state === "ready") {
    return `Tính được cho toàn bộ ${total} mã trong phạm vi`
  }
  if (state === "partial") {
    return `Tính được cho ${evaluated}/${total} mã trong phạm vi`
  }
  return `Chỉ tính được cho ${evaluated}/${total} mã, chưa đủ để kết luận`
}

/**
 * How the answered session relates to the newest market data.
 */
export function freshnessSentence(freshness: SignalFreshness): string {
  if (freshness === "fresh") return "Phiên mới nhất hệ thống có dữ liệu"
  if (freshness === "lagging") return "Chưa phải phiên mới nhất của thị trường"
  return "Dữ liệu đã cũ"
}

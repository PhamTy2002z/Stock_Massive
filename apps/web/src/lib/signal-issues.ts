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

/**
 * One sentence per code, and the whole closed set.
 *
 * The set is closed on the backend (`src/stocks/signals/issues.py`) and this is
 * its Vietnamese half; `src/alpha/reasons.py` holds the English half, which is
 * written for the model rather than for a reader. The Analysis artifact renders
 * a refused figure's reason directly rather than behind a tooltip, so a code
 * with no entry here would be a blank where the honesty evidence should be.
 *
 * The sentences are deliberately about the *window* rather than about any one
 * screen's window length: the same code reaches the volume-spike dashboard,
 * which measures twenty sessions, and an Analysis figure that declares its own
 * `min_sessions`. A sentence naming one of those numbers would be wrong on the
 * other screen.
 *
 * Every sentence says what is missing or what changed, never what to do about
 * it — advice in a data note is the recommendation the citation contract exists
 * to keep out of a figure.
 */
export const SIGNAL_ISSUE_SENTENCES = {
  missing_target_session: "Chưa có dữ liệu phiên này",
  insufficient_history: "Chưa đủ số phiên tối thiểu để tính chỉ số này",
  recently_inactive: "Có phiên không phát sinh giao dịch trong cửa sổ tính",
  cohort_warming: "Nhóm được so sánh vẫn đang nạp dữ liệu",
  lagging_market_data: "Đã có phiên mới hơn nhưng chưa đủ dữ liệu để tính",
  stale_market_data: "Dữ liệu phiên đã cũ hơn 7 ngày",
  ranking_unavailable: "Chưa có bảng xếp hạng nào đang hiệu lực để xếp vị trí",

  // Price Basis and the price band (ADR-0006)
  mixed_price_basis:
    "Các phiên trong cửa sổ không cùng một cơ sở giá nên không so sánh được với nhau",
  unadjustable_price_basis:
    "Giá trong cửa sổ đã được nhà cung cấp điều chỉnh sẵn và không hoàn nguyên được",
  exchange_unknown: "Không rõ sàn niêm yết trong các phiên này nên chưa đọc được biên độ",
  session_prices_incomplete:
    "Một phiên trong cửa sổ không lưu giá cao nhất và thấp nhất",
  anchor_not_stored:
    "Sàn này đo biên độ từ một mức tham chiếu hệ thống không lưu và không dựng lại được",
  anchor_missing: "Không có phiên liền trước để làm mốc tham chiếu cho biên độ",

  // Corporate Actions (ADR-0006)
  unconfirmed_corporate_action:
    "Có sự kiện doanh nghiệp trong cửa sổ chưa xác nhận được ngày giao dịch không hưởng quyền",
  corporate_action_terms_incomplete:
    "Điều khoản của sự kiện doanh nghiệp không đủ để quy ra hệ số điều chỉnh",
  price_move_exceeds_band:
    "Có phiên biến động vượt biên độ cho phép, nhiều khả năng mốc tham chiếu sai",
  unexplained_price_gap:
    "Có bước nhảy giá mà không sự kiện doanh nghiệp nào đã lưu giải thích được",
  volume_basis_break:
    "Khối lượng qua ngày thay đổi số cổ phiếu không cùng cơ sở so sánh",

  // The statistical bar (ADR-0010)
  baseline_dispersion_zero: "Nền so sánh không có độ phân tán nên không đo được theo sigma",
  zero_range_session: "Phiên được xét chỉ khớp ở một mức giá nên không có biên độ để đọc",
  insufficient_downside_observations:
    "Quá ít phiên đóng cửa dưới ngưỡng để đo độ lệch phía giảm",
  autocorrelation_unusable:
    "Tự tương quan của chuỗi lợi suất khiến phép quy đổi theo năm không dùng được",
  unavailable: "Hệ thống chưa tính chỉ số này",
  band_not_measured:
    "Cửa sổ này được dựng cho khối lượng nên không phiên nào được đối chiếu biên độ",
  band_not_applicable: "Công cụ này không có biên độ dao động",

  // Traded figures (ADR-0010)
  traded_figure_not_stored: "Một phiên trong cửa sổ không lưu giá trị giao dịch",
  no_traded_sessions: "Không phiên nào trong cửa sổ phát sinh giao dịch",
  foreign_flow_not_stored:
    "Một phiên trong cửa sổ không lưu số liệu giao dịch của khối ngoại",
  foreign_room_not_stored: "Chưa có số liệu room ngoại nào được lưu tính đến phiên này",
  foreign_room_exhausted:
    "Room ngoại đã kín nên dòng tiền ngoại trong cửa sổ bị chặn về mặt cơ học",

  // Cross-sectional and stored fields (ADR-0010)
  insufficient_cross_section: "Quá ít mã đủ điều kiện để lập phân vị",
  stale_fundamental_period: "Báo cáo quý gần nhất phía sau con số này đã cũ",
  fundamental_not_stored: "Chưa có báo cáo quý nào được lưu tính đến ngày này",
  stale_reference_reading: "Số liệu tham chiếu gần nhất phía sau con số này đã cũ",
  half_life_exceeds_window:
    "Nhịp hồi quy ước lượng dài hơn cửa sổ nên chỉ số z được giữ lại",
  limit_locked_window: "Hơn một phần năm số phiên trong cửa sổ bị khoá ở trần hoặc sàn",
} as const

export type SignalIssueCode = keyof typeof SIGNAL_ISSUE_SENTENCES

const UNNAMED_ISSUE = "Có vấn đề về dữ liệu cho mục này"

export function signalIssueSentence(code: string): string {
  return SIGNAL_ISSUE_SENTENCES[code as SignalIssueCode] ?? UNNAMED_ISSUE
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

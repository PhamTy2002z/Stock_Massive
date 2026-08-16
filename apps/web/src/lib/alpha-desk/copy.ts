/**
 * Every sentence the conversation surface says on the system's behalf.
 *
 * In one file because each of them is a promise about what the user is *not*
 * shown. The activity line must carry a phase and never a tool name, a symbol,
 * an argument or a result (`docs/specs/0002` §6, §9); a Turn that stopped early
 * must carry a sentence and never its stable code, the same way the rail maps a
 * `Signal Issue` code to prose. Spread across the components that render them,
 * both rules would be enforced by whoever happened to write the JSX.
 *
 * Application chrome is English and narration is Vietnamese (`docs/specs/0002`
 * §5). Almost everything here is the system narrating, so almost everything
 * here is Vietnamese; the one exception is named where it appears, and it is a
 * control label rather than a sentence.
 */

import type { ActivityPhase } from "./types"

/**
 * What the collapsed line says, and what it says when opened.
 *
 * The phase is the whole vocabulary. `summary` describes the *kind* of work in
 * user language — it is not a longer trace, and expanding it must never become
 * the way a curious user learns the catalog. The Tool Call Trace is where the
 * detail lives, and it is an audit surface rather than part of the answer.
 */
export const ACTIVITY_COPY: Record<ActivityPhase, { line: string; summary: string }> = {
  searching: {
    line: "Đang tìm…",
    summary: "Đang tìm trong các nguồn tin đã được duyệt cho câu hỏi này.",
  },
  reading_data: {
    line: "Đang đọc dữ liệu…",
    summary: "Đang đọc số liệu phiên gần nhất và các chỉ số đã đăng ký.",
  },
  analyzing: {
    line: "Đang phân tích…",
    summary: "Đang đối chiếu những gì vừa đọc trước khi trả lời.",
  },
  preparing_visual: {
    line: "Đang dựng hình…",
    summary: "Đang chuẩn bị một hình minh hoạ cho phần trả lời.",
  },
}

/**
 * How a Turn that stopped early is described.
 *
 * Keyed by the stable `terminal_reason` the lifecycle writes. A reason with no
 * entry falls back to a sentence rather than to the code itself: an unmapped
 * code on screen is the failure this table exists to prevent, and a reason this
 * table has not learned is still a Turn the user watched stop.
 */
const TERMINAL_REASONS: Record<string, string> = {
  cancelled_by_user: "Bạn đã dừng lượt này.",
  shutdown: "Hệ thống khởi động lại nên lượt này dừng giữa chừng.",
  interrupted_restart: "Hệ thống khởi động lại nên lượt này dừng giữa chừng.",
  turn_deadline: "Lượt này chạy quá thời gian cho phép nên dừng lại.",
  turn_failed: "Lượt này gặp sự cố nên dừng lại.",
  grounding_failed:
    "Một phần nội dung không dẫn được về số liệu đã đăng ký nên đã bị giữ lại.",
  llm_call_timeout: "Mô hình không trả lời kịp nên lượt này dừng lại.",
  gateway_timeout: "Tuyến mô hình không phản hồi nên lượt này dừng lại.",
  route_error: "Tuyến mô hình gặp lỗi nên lượt này dừng lại.",
  auth_unavailable: "Không kết nối được tới tuyến mô hình nên lượt này dừng lại.",
  tool_timeout: "Một bước đọc dữ liệu quá thời gian nên lượt này dừng lại.",
  model_refusal: "Mô hình đã từ chối trả lời câu hỏi này.",
  user_input_too_large: "Câu hỏi vượt quá giới hạn độ dài cho một lượt.",
}

const UNNAMED_REASON = "Lượt này dừng trước khi hoàn tất."

/** The sentence for a stable reason. Never the code, whatever the code is. */
export function terminalSentence(reason: string | null): string {
  return (reason && TERMINAL_REASONS[reason]) || UNNAMED_REASON
}

/** The stable reasons this surface has a sentence for. Exported for its test. */
export const KNOWN_TERMINAL_REASONS = Object.keys(TERMINAL_REASONS)

/**
 * The first-run empty state.
 *
 * Two things, both explicit, and neither of them a feature tour: the
 * Universe-vs-Watchlist rule, because a user who believes the Watchlist gates
 * the agent will spend a slot to ask one question; and the scope boundary in
 * user language, because "no ad-hoc computation" is the refusal they will
 * otherwise meet without warning.
 *
 * **The catalog is not published.** Listing what the agent can compute would
 * turn the empty state into a menu, and a menu is a promise about every item on
 * it. A refusal teaches the detail at the moment it matters (ADR-0011).
 */
export const FIRST_RUN = {
  question: "Hôm nay bạn muốn hỏi gì về danh mục của mình?",
  universeRule:
    "Bạn có thể hỏi về bất kỳ mã nào trong Universe. Watchlist chỉ quyết định mã nào được dựng Analysis mỗi phiên — nó không giới hạn câu hỏi.",
  scopeBoundary:
    "Phạm vi là phân tích bốn trục cho các mã trong Watchlist, dựa trên những chỉ số đã đăng ký. Hệ thống không tính toán tuỳ ý theo yêu cầu, và không đưa ra khuyến nghị phân bổ vốn hay đòn bẩy.",
  hint: "Ví dụ: hỏi vì sao một mã được đánh giá như vậy trong phiên gần nhất.",
} as const

/**
 * What the stop control says once it has been pressed.
 *
 * English, and the one string in this file that is: it is a button's own label,
 * not the system narrating, and it sits where `Stop` and `Send` sit. Shared
 * because the composer and the status line both say it, and a Turn that read
 * *Cancelling…* in one place and something else in the other would look like
 * two different things happening.
 */
export const CANCELLING_LABEL = "Cancelling…"

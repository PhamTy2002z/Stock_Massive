/**
 * Every sentence the conversation surface says on the system's behalf.
 *
 * In one file because each of them is a promise about what the user is *not*
 * shown: a Turn that stopped early must carry a sentence and never its stable
 * code, the same way the rail maps a `Signal Issue` code to prose. Spread
 * across the components that render them, that rule would be enforced by
 * whoever happened to write the JSX.
 *
 * Application chrome is English and narration is Vietnamese. Almost everything
 * here is the system narrating, so almost everything here is Vietnamese; the
 * one exception is named where it appears, and it is a control label rather
 * than a sentence.
 */

import type { FlagReason } from "./types"

/**
 * What the list of tool calls says: its own label, and one word per outcome.
 *
 * The sentence describing a call is the backend's `summary`, because only the
 * side that made the call knows what it was for. What is left here is the
 * chrome around it — which is why there are three words and not three
 * templates.
 */
export const TOOL_CALL_COPY = {
  label: "Công cụ đã dùng",
  running: "Đang chạy…",
  ok: "Xong",
  error: "Lỗi",
} as const

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
  llm_call_timeout: "Mô hình không trả lời kịp nên lượt này dừng lại.",
  answer_truncated: "Câu trả lời bị cắt giữa chừng vì vượt giới hạn độ dài cho một lượt.",
  gateway_timeout: "Tuyến mô hình không phản hồi nên lượt này dừng lại.",
  route_rate_limited:
    "Tuyến mô hình đã dùng hết lượt gọi được cấp nên lượt này dừng lại. Chờ hạn mức được cấp lại rồi thử lại.",
  route_error: "Tuyến mô hình gặp lỗi nên lượt này dừng lại.",
  context_overflow:
    "Cuộc hội thoại đã dài hơn mức tuyến mô hình nhận được nên lượt này dừng lại. Bạn thử mở luồng mới.",
  output_cap_exceeded:
    "Lượt này cần chỗ trả lời nhiều hơn mức tuyến mô hình cho phép nên dừng lại. Bạn thử hỏi hẹp hơn.",
  content_policy_blocked: "Tuyến mô hình từ chối câu hỏi này nên lượt này dừng lại.",
  model_unavailable:
    "Tuyến mô hình không còn phục vụ mô hình đang cấu hình nên lượt này dừng lại.",
  schema_rejected: "Tuyến mô hình không nhận được danh mục công cụ nên lượt này dừng lại.",
  auth_unavailable: "Không kết nối được tới tuyến mô hình nên lượt này dừng lại.",
  tool_timeout: "Một công cụ chạy quá thời gian nên lượt này dừng lại.",
  model_refusal: "Mô hình đã từ chối trả lời câu hỏi này.",
  user_input_too_large: "Câu hỏi vượt quá giới hạn độ dài cho một lượt.",
}

const UNNAMED_REASON = "Lượt này dừng trước khi hoàn tất."

/** The sentence for a stable reason. Never the code, whatever the code is. */
export function terminalSentence(reason: string | null): string {
  return (reason && TERMINAL_REASONS[reason]) || UNNAMED_REASON
}

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

/**
 * What flagging a message says, and — the load-bearing half — what it does not.
 *
 * V1 has **no dispute workflow** (`docs/adr/0016`). One action carries a
 * `message_id` and a reason label; it opens no ticket, notifies nobody and
 * suspends no account. So the acknowledgement states what was recorded and
 * stops there. A sentence like *"chúng tôi sẽ phản hồi"* would be a promise the
 * system has no mechanism to keep, and the reader would be waiting for a reply
 * that is never coming — which is worse than an action that admits its limit.
 *
 * What the flag is actually for is said plainly instead: it is read when the
 * answers are reviewed. That is true — a flag confirmed as a genuine failure
 * becomes a new Eval Case — and it promises this reader nothing.
 *
 * The four labels are the reader's vocabulary rather than the column's, so they
 * describe what went wrong in the answer and never name a mechanism: nobody
 * flags an answer for a validator's verdict, they flag it because the number is
 * wrong.
 */
export const FLAG_REASON_LABELS: Record<FlagReason, string> = {
  wrong_figure: "Số liệu sai",
  overreach: "Kết luận đi quá dữ liệu",
  wrongly_refused: "Từ chối trả lời không đúng",
  other: "Lý do khác",
}

/**
 * The reasons this surface offers, in the order it offers them.
 *
 * Derived from the labels rather than listed a second time: the vocabulary is
 * already spelled once in `FlagReason` and once by the backend on the column it
 * validates, and a third in-app copy is a third place the four can disagree.
 * Key order is insertion order, so the record above is also the running order.
 */
export const FLAG_REASONS = Object.keys(FLAG_REASON_LABELS) as FlagReason[]

export const FLAG_COPY = {
  /** The control itself. Deliberately quiet: it sits under an answer, not in it. */
  action: "Báo lỗi câu trả lời",
  prompt: "Phần nào chưa đúng?",
  /**
   * Said once the pair is written. It records, and it promises nothing —
   * no ticket number, no reply, no deadline.
   */
  acknowledged:
    "Đã ghi nhận đánh dấu này. Nó được đọc khi rà soát chất lượng trả lời, và không mở yêu cầu xử lý nào.",
  remove: "Bỏ đánh dấu",
  /**
   * Said when the write itself failed.
   *
   * The counterpart to the acknowledgement, and the reason the flag is never
   * shown optimistically: a mark that appeared and then quietly vanished would
   * tell the reader their objection was recorded when it was not. Silence here
   * is the same lie, so a rejected write says so.
   */
  failed: "Chưa ghi được đánh dấu. Bạn thử lại giúp nhé.",
} as const

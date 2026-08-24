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
  /** Ran, asked the store, and there was no number to give. */
  noFigure: "Không có số",
  /** Declined before asking: outside the Universe, or not this call's symbol. */
  outOfScope: "Ngoài phạm vi",
} as const

/**
 * What a failed call says, when the reason is not that anything failed.
 *
 * Keyed by the backend's stable `error` code. Every entry here shares one
 * property: the call was refused by our own ceilings and never dispatched, so
 * nothing outside this deployment was even asked. Calling that "Lỗi" tells the
 * reader to retry a search engine that is working perfectly well.
 *
 * A code with no entry keeps `TOOL_CALL_COPY.error`, which is the right default:
 * everything not listed here — a tool that threw, a page that would not load, a
 * name no tool answers to — really is a failure.
 */
const REFUSED_CALL_LABELS: Record<string, string> = {
  external_budget_exhausted: "Hết lượt tra",
  round_fanout_exceeded: "Không chạy",
  halted_turn: "Đã dừng",
}

/** The word shown beside a call that did not succeed. */
export function toolCallErrorLabel(error: string | null): string {
  if (error === null) return TOOL_CALL_COPY.error
  return REFUSED_CALL_LABELS[error] ?? TOOL_CALL_COPY.error
}

/**
 * The word shown beside a call that ran and came back with nothing.
 *
 * Deliberately not "Lỗi" and deliberately not "Xong". The call worked and the
 * question was well formed, so calling it a failure would send the reader to
 * retry something that is not broken; but the row drew identically to a call
 * that returned a number, and that is what made a third of the evidence path
 * invisible.
 *
 * Two words rather than one because two facts arrive here: the store was asked
 * and had no figure, or the tool declined the question before asking anything.
 * The specific **Signal Issue** behind the first is rendered from
 * `SIGNAL_ISSUE_SENTENCES`, which already owns one sentence per code — a second
 * table of them here would be the drift that module exists to prevent.
 */
export function toolCallEmptyLabel(outcome: string | null | undefined): string {
  return outcome === "cannot_read"
    ? TOOL_CALL_COPY.outOfScope
    : TOOL_CALL_COPY.noFigure
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
  llm_call_timeout: "Mô hình không trả lời kịp nên lượt này dừng lại.",
  answer_truncated: "Câu trả lời bị cắt giữa chừng vì vượt giới hạn độ dài cho một lượt.",
  empty_answer:
    "Tuyến mô hình không trả về câu trả lời nào cho lượt này. Bạn thử hỏi lại.",
  deadline_expired: "Không kết nối kịp tới tuyến mô hình nên lượt này dừng lại.",
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
 * What the send control is called.
 *
 * Vietnamese, following the design: the composer is the one place in the shell
 * a first-time reader has to act rather than read, and a control they are meant
 * to reach for should not be the one thing on screen in another language.
 *
 * It is never drawn as text — the button is an arrow — so this is what a screen
 * reader announces and what the tooltip says. Both need to be the same word,
 * which is why it is named once here rather than typed twice at the button.
 */
export const SEND_LABEL = "Gửi"

/**
 * What the stop control says once it has been pressed.
 *
 * Shared by the composer and status line so both places describe one state in
 * the product's Vietnamese-first operational language.
 */
export const CANCELLING_LABEL = "Đang dừng…"

/**
 * What flagging a message says, and — the load-bearing half — what it does not.
 *
 * V1 has **no dispute workflow**. One action carries a
 * `message_id` and a reason label; it opens no ticket, notifies nobody and
 * suspends no account. So the acknowledgement states what was recorded and
 * stops there. A sentence like *"chúng tôi sẽ phản hồi"* would be a promise the
 * system has no mechanism to keep, and the reader would be waiting for a reply
 * that is never coming — which is worse than an action that admits its limit.
 *
 * What the flag is actually for is said plainly instead: it is read when the
 * answers are reviewed. That is true — a flag confirmed as a genuine failure is
 * a defect somebody reads the transcript for — and it promises this reader
 * nothing.
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

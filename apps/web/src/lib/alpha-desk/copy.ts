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

import type { ActivityPhase, FlagReason } from "./types"

/**
 * What a phase says while it runs, once it is done, and when it is opened.
 *
 * The phase is the whole vocabulary — three sentences per phase, and there are
 * four phases. `summary` describes the *kind* of work in user language: it is
 * not a longer trace, and expanding it must never become the way a curious user
 * learns the catalog. The Tool Call Trace is where the detail lives, and it is
 * an audit surface rather than part of the answer.
 *
 * `done` is the same promise in the past tense. A finished step stays on screen
 * under the ones after it, so it has to read as a completed fact rather than as
 * a line that stopped moving — and it still names no tool, symbol, argument or
 * result, because the publisher never sent one.
 */
export const ACTIVITY_COPY: Record<
  ActivityPhase,
  { line: string; done: string; summary: string }
> = {
  searching: {
    line: "Đang tìm…",
    done: "Đã tìm trong các nguồn đã duyệt",
    summary: "Đang tìm trong các nguồn tin đã được duyệt cho câu hỏi này.",
  },
  reading_data: {
    line: "Đang đọc dữ liệu…",
    done: "Đã đọc dữ liệu đã lưu",
    summary: "Đang đọc số liệu phiên gần nhất và các chỉ số đã đăng ký.",
  },
  analyzing: {
    line: "Đang phân tích…",
    done: "Đã đối chiếu số liệu vừa đọc",
    summary: "Đang đối chiếu những gì vừa đọc trước khi trả lời.",
  },
  preparing_visual: {
    line: "Đang dựng hình…",
    done: "Đã dựng hình minh hoạ",
    summary: "Đang chuẩn bị một hình minh hoạ cho phần trả lời.",
  },
  found_sources: {
    line: "Đang đọc kết quả…",
    done: "Đã tìm thấy kết quả",
    summary: "Các trang công khai mà lượt này đã đọc để trả lời.",
  },
}

/**
 * The search-progress trail, as its header and its rows read.
 *
 * Vietnamese throughout, including the rows the reference design left in
 * English: `docs/specs/0002` §5 puts narration in Vietnamese and reserves
 * English for control chrome, and *Thinking…* beside *Hoàn thành* is the same
 * trail speaking two languages to one reader.
 *
 * `found` takes the count because it is the one row that is a *number* the
 * reader is being asked to weigh — how much was read, not how much is listed
 * under it.
 *
 * Every phase that can outlive its own execution comes in a pair, for the same
 * reason `ACTIVITY_COPY` does: a row saying *Đang tìm trên web…* under a
 * finished answer tells the reader the Turn is still going. The row that is
 * running says *Đang…*; every row above it says what it did. `thinking` has no
 * past tense on purpose — an analysis step is only ever on screen while it is
 * the thing happening, so there is no finished form of it to write.
 */
export const PROGRESS_COPY = {
  header: "Tiến trình tìm kiếm",
  thinking: "Đang suy nghĩ…",
  searching: "Đang tìm trên web…",
  searched: "Đã tìm trên web",
  readingData: "Đang đọc dữ liệu…",
  readData: "Đã đọc dữ liệu đã lưu",
  preparingVisual: "Đang dựng hình…",
  preparedVisual: "Đã dựng hình minh hoạ",
  queries: "Tìm kiếm",
  found: (count: number) => `Đã tìm thấy ${count} kết quả`,
  sourcesTitle: (count: number) => `Tổng hợp ${count} nguồn`,
  done: "Hoàn thành",
  stopped: "Đã dừng",
  sourcesLabel: (count: number) => `${count} nguồn`,
  drawerTitle: (count: number) => `${count} nguồn tham khảo`,
  drawerClose: "Đóng",
  updatedAt: (day: string) => `Cập nhật: ${day}`,
  suggestionsTitle: "Gợi ý",
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
 * user language, because the difference between registered analysis and a
 * derived calculation is important before either one appears in an answer.
 *
 * **The catalog is not published.** Listing what the agent can compute would
 * turn the empty state into a menu, and a menu is a promise about every item on
 * it. A refusal teaches the detail at the moment it matters (ADR-0019).
 */
export const FIRST_RUN = {
  question: "Hôm nay bạn muốn hỏi gì về danh mục của mình?",
  universeRule:
    "Bạn có thể hỏi về bất kỳ mã nào trong Universe. Watchlist chỉ quyết định mã nào được dựng Analysis mỗi phiên — nó không giới hạn câu hỏi.",
  scopeBoundary:
    "Phạm vi là phân tích bốn trục cho các mã trong Watchlist, dựa trên những chỉ số đã đăng ký. Phép tính tuỳ biến chỉ là dữ liệu dẫn xuất có cảnh báo, và hệ thống không đưa ra khuyến nghị phân bổ vốn hay đòn bẩy.",
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
 * flags an answer for *grounding failure*, they flag it because the number is
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

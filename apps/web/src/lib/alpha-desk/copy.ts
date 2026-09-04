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
  label: "Công cụ đã dùng", running: "Đang chạy…", ok: "Xong", error: "Lỗi",
  // A call written down before its effect ran, and one a permission rule
  // refused. Two more states, and each says something the other four cannot: a
  // pending call has not started yet, and a denied one never will.
  pending: "Chờ chạy", denied: "Không được phép",
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
  external_budget_exhausted: "Hết lượt tra", round_fanout_exceeded: "Không chạy", halted_turn: "Đã dừng",
  // Nothing ran and nothing will: the route is closed rather than broken, so the
  // word must not invite a retry.
  permission_denied: "Không được phép",
}

/** The word shown beside a call that did not succeed. */
export function toolCallErrorLabel(error: string | null): string {
  if (error === null) return TOOL_CALL_COPY.error
  return REFUSED_CALL_LABELS[error] ?? TOOL_CALL_COPY.error
}

/**
 * The words around one question card.
 *
 * The prompt, the options and the skip label are the backend's — a card is
 * written where the question is decided, and a client that composed any of them
 * would be asking something other than what was meant. What is here is the
 * frame: what the card is, and what each settled state means now that pressing
 * it is over. `skip` is a fallback for a stored card that carries no label of
 * its own, never a rewording of one that does.
 */
export const QUESTION_COPY = {
  region: "Câu hỏi cần bạn trả lời",
  skip: "Bỏ qua",
  answered: "Bạn đã chọn",
  skipped: "Bạn đã bỏ qua — phần sau chạy theo giả định mặc định.",
  superseded: "Bạn đã hỏi tiếp nên câu hỏi này không còn cần trả lời.",
  failed: "Chưa ghi được lựa chọn này. Bạn thử lại giúp nhé.",
} as const

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
 * Everything the Signal Desk says, and the one thing it deliberately does not.
 *
 * The workspace's name is a proper noun the client chose, so it is not
 * translated and not paraphrased: the pill in the composer, the pane it opens
 * and the tab a picture files itself under are one feature, and a reader who
 * met it under three names would count three.
 *
 * **There is no "Lưu".** The design draws a save control beside the export one,
 * and there is no endpoint behind it — the sidebar's own "Báo cáo đã lưu" still
 * says "Sắp ra mắt". A button that swallowed the press would promise a reader
 * their work was kept, which is the one failure this surface cannot recover
 * from, so the control is absent rather than inert.
 */
export const SIGNAL_DESK_COPY = {
  /** The feature, wherever it is named. */
  name: "Signal Desk",
  /**
   * What the pane says while the desk is on and nothing has been drawn yet.
   *
   * Four parts rather than one sentence, and still no button: the composer is
   * the call to action three hundred pixels to the left, and a second one here
   * would send the reader looking for a control already under their hands. What
   * the empty pane owes them instead is *what will appear* — which is why the
   * shape of a board is drawn above the words, unlabelled and inert.
   *
   * `emptyStatus` is the one line that reports rather than explains: the desk
   * being on is a state the reader switched into, and it is the fact they will
   * check first if nothing arrives.
   */
  emptyStatus: "Signal Desk đang bật",
  emptyTitle: "Bảng phân tích sẽ hiện ở đây",
  emptyBody:
    "Hỏi về một mã, một ngành hay cả thị trường — mỗi câu trả lời dựng một bảng có số liệu, nguồn và có thể xuất.",
  /**
   * The Universe, said where a reader is about to name a symbol.
   *
   * The count is written out rather than fetched. It is a deployment's own
   * declared Universe — thirty symbols, stated in the backend — and a figure
   * that arrived over the network would show a blank or a wrong number for the
   * first few hundred milliseconds of exactly the screen that exists to set an
   * expectation.
   *
   * No link under it. The design draws one to a list of the thirty, and there is
   * no page, popover or endpoint on this side that holds them — a link to
   * nothing teaches the reader that the product's links do not work, which
   * costs more than the list would have given them.
   */
  emptyUniverseHint: "Hiện hỗ trợ 30 mã VN30 — sẽ mở rộng dần.",
  /** What the pane says with the desk off and no picture in the conversation. */
  noDeskView: "Chưa có Signal Desk nào trong hội thoại này.",
  chatMode: "Chat",
  toggle: "Signal Desk",
  sources: "Nguồn",
  deskEmptyHeadline: "Signal on your Desk",
  blockNoData: "Phần này chưa có số liệu.",
  blockAsTable: "Hiển thị dạng bảng — bản này chưa vẽ được biểu đồ.",
} as const


/**
 * The three questions the desk offers before it has been asked anything.
 *
 * Written to the shape of question the desk is for — one figure, in context,
 * with its sources — because the point of the row is to teach that shape. The
 * empty column is the only place a reader has to learn it from.
 *
 * They are offered into the field **unsent**. Two of them name a symbol, and
 * which symbols exist is a deployment's Universe rather than something this
 * bundle can know — so the reader gets the sentence with the ticker selected to
 * change, which is the same contract every other offered question follows
 * (`shell-state`, `ask`). Sending on the press would spend a Turn on whichever
 * ticker happened to be written here.
 *
 * Neither starter asks whether to buy or sell. The lane's prompt states levels
 * and consequences and declines instructions for a position, so a starter that
 * asks for one would be teaching the reader to ask for a refusal.
 */
export const SIGNAL_DESK_STARTERS = [
  "Thanh khoản của VCB dồn về khung giờ nào trong phiên?",
  "VCB đang ở đâu trong dải 52 tuần và lợi nhuận quý đi hướng nào?",
  "Mã nào lợi nhuận quý tăng mạnh mà giá chưa theo?",
] as const

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
 * Everything the attachment path says, including every way it says no.
 *
 * The refusals are named by the reason the backend sends rather than by status
 * code, and each one names the action left to take. A reader who sees "413" has
 * been told what happened to the request; a reader who sees "tệp này lớn hơn
 * 4 MB" has been told what to do next.
 *
 * `unknown` exists because a refusal this build has never heard of is still a
 * refusal, and a blank space beside a file that did not upload is the one
 * outcome with no reading at all.
 */
export const ATTACHMENT_COPY = {
  add: "Thêm tệp hoặc ảnh",
  addHint: "⌘U",
  /** On the button that takes one chip back off the question. */
  remove: (filename: string) => `Bỏ ${filename}`,
  uploading: "Đang nạp…",
  failed: "Không nạp được",
  /** Read by a screen reader for the row of chips above the field. */
  region: "Tệp đính kèm của câu hỏi này",
  /**
   * Said once, beside the chips, when the route cannot read pictures.
   *
   * The file still uploads and still travels — this is a fact about what the
   * model will be able to do with it, not a refusal. Saying nothing would let a
   * reader attach a chart and read a generic answer as a wrong answer.
   */
  imagesNotRead: "Model của phiên này chưa đọc được ảnh — ảnh vẫn được lưu kèm câu hỏi.",
  refusals: {
    file_too_large: "Tệp này lớn hơn mức cho phép. Hãy chọn tệp nhỏ hơn.",
    media_type_not_allowed: "Chỉ nhận ảnh PNG, JPEG, WebP và tệp văn bản .txt, .csv.",
    empty_file: "Tệp này rỗng.",
    quota_rows: "Bạn đã lưu quá nhiều tệp. Hãy bỏ vài tệp cũ rồi thử lại.",
    quota_bytes: "Dung lượng tệp đã lưu đã đầy. Hãy bỏ vài tệp cũ rồi thử lại.",
    turn_image_budget: "Những ảnh này quá lớn để đi cùng một câu hỏi. Hãy bỏ một ảnh.",
    unknown: "Không nạp được tệp này. Hãy thử lại.",
  },
} as const

/**
 * What the screen capture says.
 *
 * The preview step has its own words because it is the one gate on a real
 * privacy risk: `getDisplayMedia` hands back everything the reader agreed to
 * share, which can include a tab, a message, an inbox. Once it is sent it is
 * sent, so the copy has to make "look before you attach" the obvious reading.
 */
export const CAPTURE_COPY = {
  /** The menu row. Not "chụp màn hình bảng giá" — it captures anything. */
  row: "Chụp màn hình",
  /** The preview dialog's accessible name. */
  title: "Xem lại ảnh chụp",
  explain: "Xem lại trước khi đính kèm. Ảnh này sẽ được gửi tới model.",
  accept: "Đính kèm",
  discard: "Bỏ",
  /** Said on the row when the browser cannot capture at all. */
  unsupported: "Trình duyệt này không cho chụp màn hình.",
  /** The capture came back empty — a stream with no frame in it. */
  failed: "Không chụp được. Hãy thử lại.",
} as const

/** The message for one refusal reason, falling back to the honest generic one. */
export function attachmentRefusal(reason: string | null | undefined): string {
  const table: Record<string, string> = ATTACHMENT_COPY.refusals
  return table[reason ?? ""] ?? ATTACHMENT_COPY.refusals.unknown
}

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

import type { FlagReason } from "./types"

export const TOOL_CALL_COPY = {
  label: "Công cụ đã dùng", running: "Đang chạy…", ok: "Xong", error: "Lỗi",
  // A call written down before its effect ran, and one a permission rule
  // refused. Two more states, and each says something the other four cannot: a
  // pending call has not started yet, and a denied one never will.
  pending: "Chờ chạy", denied: "Không được phép",
} as const

const REFUSED_CALL_LABELS: Record<string, string> = {
  external_budget_exhausted: "Hết lượt tra", round_fanout_exceeded: "Không chạy", halted_turn: "Đã dừng",
  // Nothing ran and nothing will: the route is closed rather than broken, so the
  // word must not invite a retry.
  permission_denied: "Không được phép",
}

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
  empty_answer: "Tuyến mô hình không trả về câu trả lời nào cho lượt này. Bạn thử hỏi lại.",
  deadline_expired: "Không kết nối kịp tới tuyến mô hình nên lượt này dừng lại.",
  gateway_timeout: "Tuyến mô hình không phản hồi nên lượt này dừng lại.",
  route_rate_limited: "Tuyến mô hình đã dùng hết lượt gọi được cấp nên lượt này dừng lại.",
  route_error: "Tuyến mô hình gặp lỗi nên lượt này dừng lại.",
  context_overflow: "Cuộc hội thoại quá dài cho tuyến mô hình. Bạn thử mở luồng mới.",
  output_cap_exceeded: "Lượt này vượt giới hạn độ dài. Bạn thử hỏi hẹp hơn.",
  content_policy_blocked: "Tuyến mô hình từ chối câu hỏi này nên lượt này dừng lại.",
  model_unavailable: "Mô hình đang cấu hình hiện không khả dụng.",
  schema_rejected: "Tuyến mô hình không nhận được danh mục công cụ.",
  auth_unavailable: "Không kết nối được tới tuyến mô hình.",
  tool_timeout: "Một công cụ chạy quá thời gian nên lượt này dừng lại.",
  model_refusal: "Mô hình đã từ chối trả lời câu hỏi này.",
  user_input_too_large: "Câu hỏi vượt quá giới hạn độ dài cho một lượt.",
}

export function terminalSentence(reason: string | null): string {
  return (reason && TERMINAL_REASONS[reason]) || "Lượt này dừng trước khi hoàn tất."
}

export const SEND_LABEL = "Gửi"
export const CANCELLING_LABEL = "Đang dừng…"

export const ATTACHMENT_COPY = {
  add: "Thêm tệp hoặc ảnh", addHint: "⌘U",
  remove: (filename: string) => `Bỏ ${filename}`,
  uploading: "Đang nạp…", failed: "Không nạp được", region: "Tệp đính kèm của câu hỏi này",
  imagesNotRead: "Model của phiên này chưa đọc được ảnh — ảnh vẫn được lưu kèm câu hỏi.",
  refusals: {
    file_too_large: "Tệp này lớn hơn mức cho phép. Hãy chọn tệp nhỏ hơn.",
    media_type_not_allowed: "Chỉ nhận ảnh PNG, JPEG, WebP và tệp văn bản .txt, .csv.",
    empty_file: "Tệp này rỗng.", quota_rows: "Bạn đã lưu quá nhiều tệp. Hãy bỏ vài tệp cũ rồi thử lại.",
    quota_bytes: "Dung lượng tệp đã lưu đã đầy. Hãy bỏ vài tệp cũ rồi thử lại.",
    turn_image_budget: "Những ảnh này quá lớn để đi cùng một câu hỏi. Hãy bỏ một ảnh.",
    unknown: "Không nạp được tệp này. Hãy thử lại.",
  },
} as const

export const CAPTURE_COPY = {
  row: "Chụp màn hình", title: "Xem lại ảnh chụp",
  explain: "Xem lại trước khi đính kèm. Ảnh này sẽ được gửi tới model.",
  accept: "Đính kèm", discard: "Bỏ",
  unsupported: "Trình duyệt này không cho chụp màn hình.", failed: "Không chụp được. Hãy thử lại.",
} as const

export function attachmentRefusal(reason: string | null | undefined): string {
  const table: Record<string, string> = ATTACHMENT_COPY.refusals
  return table[reason ?? ""] ?? ATTACHMENT_COPY.refusals.unknown
}

export const FLAG_REASON_LABELS: Record<FlagReason, string> = {
  wrong_figure: "Số liệu sai", overreach: "Kết luận đi quá dữ liệu",
  wrongly_refused: "Từ chối trả lời không đúng", other: "Lý do khác",
}
export const FLAG_REASONS = Object.keys(FLAG_REASON_LABELS) as FlagReason[]
export const FLAG_COPY = {
  action: "Báo lỗi câu trả lời", prompt: "Phần nào chưa đúng?",
  acknowledged: "Đã ghi nhận để rà soát chất lượng câu trả lời.",
  remove: "Bỏ đánh dấu", failed: "Chưa ghi được đánh dấu. Bạn thử lại giúp nhé.",
} as const

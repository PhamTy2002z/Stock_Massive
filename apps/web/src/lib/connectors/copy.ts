/**
 * The words the connectors surfaces say, in one place.
 *
 * The backend's refusals carry a stable `reason` and an English sentence meant
 * for logs; the reader is shown the Vietnamese line keyed by the reason, and the
 * backend's sentence only for a reason this client does not know yet.
 */

import { AlphaRefusalError } from "@/lib/alpha"
import { ApiUnavailableError } from "@/lib/connection-status"

import type { ConnectorAuth, ConnectorStatus, ToolAccess, ToolAction } from "./types"

export const STATUS_LABEL: Record<ConnectorStatus, string> = {
  connected: "Đã kết nối",
  needs_auth: "Cần đăng nhập lại",
  needs_reconsent: "Cần xác nhận thay đổi",
  error: "Lỗi",
}

export const AUTH_LABEL: Record<ConnectorAuth, string> = {
  none: "Không",
  header: "Khoá",
  oauth: "OAuth",
}

export const SOURCE_LABEL = { catalog: "Danh mục", custom: "Tuỳ chỉnh" } as const

export const ACTION_LABEL: Record<ToolAction, string> = {
  allow: "Cho phép",
  ask: "Cần duyệt",
  deny: "Chặn",
}

export const TOOL_ACCESS_COPY: Record<ToolAccess, { label: string; hint: string }> = {
  on_demand: {
    label: "Nạp khi cần",
    hint: "Ít phải nén hội thoại vì công cụ không nạp sẵn",
  },
  preloaded: {
    label: "Nạp sẵn",
    hint: "Nén hội thoại thường hơn vì công cụ đã nạp sẵn",
  },
}

export const WRITE_NEEDS_APPROVAL = "Công cụ ghi luôn cần duyệt"
export const SERVER_CLAIMED_READ_ONLY = "Máy chủ tự khai báo là chỉ đọc — chưa được kiểm chứng"
export const TOOL_LIMIT = 50

const REFUSAL: Record<string, string> = {
  connectors_disabled: "Tính năng Kết nối chưa được bật trên hệ thống này.",
  custom_url_not_allowed: "Tài khoản này chưa được phép thêm URL tuỳ chỉnh.",
  url_refused: "Địa chỉ máy chủ bị từ chối. Chỉ dùng được địa chỉ công khai, an toàn.",
  header_refused: "Tên header này không dùng để mang khoá được.",
  credential_required: "Kết nối này cần khoá truy cập.",
  name_required: "Hãy đặt tên cho kết nối.",
  write_needs_approval: `${WRITE_NEEDS_APPROVAL}.`,
  not_header_auth: "Kết nối này không dùng khoá.",
  not_oauth: "Kết nối này không đăng nhập bằng OAuth.",
  approve_once_only: "Công cụ này chỉ được duyệt từng lần một.",
}

/** What to tell the reader about a failed connectors call. */
export function refusalMessage(error: unknown): string {
  if (error instanceof ApiUnavailableError) return "Hệ thống đang không phản hồi. Hãy thử lại sau."
  if (error instanceof AlphaRefusalError) {
    const known = error.reason ? REFUSAL[error.reason] : undefined
    if (known) return known
    if (error.status === 404) return "Kết nối này không còn nữa."
    return `Không thực hiện được: ${error.message}`
  }
  return "Không thực hiện được. Hãy thử lại."
}

/** A dropped tool's reason, in words. `suspicious_text:…` and `unsupported_schema: …` carry details. */
export function droppedReason(reason: string): string {
  if (reason === "no_name") return "Không có tên"
  if (reason === "duplicate_name") return "Trùng tên với công cụ khác"
  if (reason === "over_tool_limit") return `Vượt giới hạn ${TOOL_LIMIT} công cụ`
  if (reason.startsWith("suspicious_text")) return "Mô tả chứa nội dung đáng ngờ nên không được nạp"
  if (reason.startsWith("unsupported_schema")) return "Tham số của công cụ không được hỗ trợ"
  return "Không dùng được"
}

/**
 * Every way a request can fail, said once, in the words a reader can act on.
 *
 * Eight surfaces used to answer the same question separately — the desk panel,
 * the thread rail, the transcript, the sources tab, both auth forms, the query
 * boundary and the connection veil — and they disagreed. The same expired
 * session was "Đã có lỗi xảy ra" in one place, a raw `Failed to fetch` in
 * another, and a spinner that never resolved in a third. A reader cannot learn
 * a system that describes one state three ways.
 *
 * So classification happens exactly once, here, and the surfaces differ only in
 * how much room they have to say it.
 *
 * This module is about transport, authorization and server failures. Empty
 * search or memory results are successful tool outcomes and do not enter this
 * classification path.
 *
 * **Every kind names one recovery, and only one.** A failure state offering two
 * routes out makes the reader choose between them with less information than
 * the interface has. Where genuinely nothing helps — a refusal that will refuse
 * again — the recovery is `none` and the state says so rather than showing a
 * button that lies.
 */

import { ApiUnavailableError } from "@/lib/connection-status"

export type FailureKind =
  | "not_found"
  | "forbidden"
  | "session_expired"
  | "offline"
  | "server"
  | "rate_limited"
  | "request_failed"

/**
 * The one way out, named rather than drawn.
 *
 * A kind rather than a rendered control, because the same failure is offered
 * differently at three densities: the page draws a filled button, a panel draws
 * a quiet one, and a line inside a block draws a word. Deciding the *route* here
 * and the *shape* at the call site is what keeps the two from drifting.
 */
export type RecoveryKind = "retry" | "signin" | "home" | "reload" | "none"

export interface Failure {
  kind: FailureKind
  /** The heading, where there is room for one. Sentence case, no full stop. */
  title: string
  /** What happened and what it means; empty when the title and action suffice. */
  detail: string
  recovery: RecoveryKind
  /** The label on the recovery control, or `null` when there is none. */
  action: string | null
  /** The status behind it, for a reader reporting the problem. `null` offline. */
  status: number | null
}

/** The label each route out carries, so two surfaces never word it differently. */
const ACTION_LABEL: Record<RecoveryKind, string | null> = {
  retry: "Thử lại",
  signin: "Đăng nhập lại",
  home: "Về màn hình chính",
  reload: "Tải lại trang",
  none: null,
}

function failure(
  kind: FailureKind,
  title: string,
  detail: string,
  recovery: RecoveryKind,
  status: number | null,
): Failure {
  return { kind, title, detail, recovery, action: ACTION_LABEL[recovery], status }
}

/**
 * One status, as the reader's situation rather than as a number.
 *
 * Split out from {@link describeFailure} because four error classes carry a
 * status and all four mean the same thing by it. The classes differ in what
 * they wrap, not in what a 403 is.
 */
function fromStatus(status: number, message: string | null): Failure {
  switch (status) {
    case 401:
      return failure(
        "session_expired",
        "Phiên đăng nhập đã hết hạn",
        "Vì lý do an toàn, phiên làm việc chỉ kéo dài một thời gian. Đăng nhập lại là bạn quay về đúng chỗ đang đọc.",
        "signin",
        status,
      )
    case 403:
      return failure(
        "forbidden",
        "Bạn không có quyền mở mục này",
        "Tài khoản đang đăng nhập không được cấp quyền với nội dung này. Nếu bạn cho rằng đây là nhầm lẫn, hãy liên hệ người quản trị không gian làm việc.",
        "none",
        status,
      )
    case 404:
      return failure(
        "not_found",
        "Không tìm thấy nội dung này",
        // The title says everything a reader can act on; guessing at why the
        // address is stale only adds a sentence to disbelieve.
        "",
        "none",
        status,
      )
    case 429:
      return failure(
        "rate_limited",
        "Bạn đang gửi quá nhanh",
        "Hệ thống tạm giới hạn số yêu cầu để giữ chỗ cho mọi người. Chờ một chút rồi thử lại là được.",
        "retry",
        status,
      )
    default:
      if (status >= 500) {
        return failure(
          "server",
          "Máy chủ gặp sự cố",
          // Named as the server's fault on purpose: a reader who believes they
          // broke something goes looking for what they did wrong.
          "Lỗi nằm ở phía chúng tôi, không phải ở thao tác của bạn. Yêu cầu này chưa được xử lý.",
          "retry",
          status,
        )
      }
      return failure(
        "request_failed",
        "Không thực hiện được yêu cầu",
        message && message.trim() !== ""
          ? message
          : "Yêu cầu bị từ chối và không có lý do nào kèm theo.",
        "retry",
        status,
      )
  }
}

/**
 * What went wrong, from whatever was thrown.
 *
 * Total by construction. Anything reaching a boundary is something a reader is
 * already looking at a broken screen over, and a classifier that threw on an
 * unfamiliar value would replace that screen with a worse one.
 */
export function describeFailure(error: unknown): Failure {
  // Silence, not an answer. `ApiUnavailableError` covers both the fetch that
  // never connected and the statuses the system recovers from on its own, so
  // the ones that are really the server failing are read out of it first.
  if (error instanceof ApiUnavailableError) {
    if (error.status !== undefined) return fromStatus(error.status, error.message)
    return offline()
  }

  // Read structurally rather than by class.
  //
  // Four layers throw four different classes — `ApiError`, `AuthApiError`,
  // `AlphaRefusalError` and the proxy's own — and every one of them means the
  // same thing by `status`. Naming them individually bought nothing and cost
  // real coupling: `AuthApiError` lives behind `server-only`, so importing it
  // here dragged server code into every client bundle that renders a failure,
  // and the build refused it. Asking for the field this module already claims
  // is its discriminator keeps the module honest and lets a fifth layer arrive
  // without editing this one.
  const status = statusOf(error)
  if (status !== null) {
    return fromStatus(status, error instanceof Error ? error.message : null)
  }

  // A `fetch` that never reached the network rejects with a bare TypeError, and
  // it is the single most common failure in this list.
  if (error instanceof TypeError) return offline()

  return failure(
    "request_failed",
    "Đã xảy ra lỗi ngoài dự kiến",
    "",
    "reload",
    null,
  )
}

/** The HTTP status an error carries, when it carries one. */
function statusOf(error: unknown): number | null {
  if (!(error instanceof Error)) return null
  const status = (error as { status?: unknown }).status
  return typeof status === "number" && Number.isFinite(status) ? status : null
}

function offline(): Failure {
  return failure(
    "offline",
    "Không kết nối được máy chủ",
    "Có thể mạng của bạn đã ngắt, hoặc hệ thống đang khởi động lại. Dữ liệu đã tải vẫn còn nguyên trên màn hình.",
    "retry",
    null,
  )
}

/**
 * Whether this failure will answer differently if asked again.
 *
 * The question every surface with a button has to settle, and the one it must
 * not settle by guessing: a retry on a 403 is a control that cannot work, and
 * offering it teaches the reader that the buttons here are decorative.
 */
export function isTransient(failure: Failure): boolean {
  return failure.recovery === "retry"
}

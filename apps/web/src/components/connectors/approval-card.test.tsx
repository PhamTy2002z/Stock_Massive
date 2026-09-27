// @vitest-environment jsdom
/** The in-chat approval card: which decision it sends, and what it offers. */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import type { ApprovalRequest } from "@/lib/alpha-desk/types"

import { ApprovalCard } from "./approval-card"
import { json } from "./test-fixtures"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function request(overrides: Partial<ApprovalRequest> = {}): ApprovalRequest {
  return {
    call_id: "call-1",
    connector: "Kho nội bộ",
    tool: "search_notes",
    display: "Tìm ghi chú",
    effect: "read",
    arguments_preview: '{"query":"VCB"}',
    can_always: true,
    expires_at: new Date(Date.now() + 120_000).toISOString(),
    ...overrides,
  }
}

function stub(response: () => Response) {
  const mock = vi.fn(async () => response())
  vi.stubGlobal("fetch", mock)
  return mock
}

describe("the approval card", () => {
  it.each([
    ["Cho phép một lần", "allow_once"],
    ["Luôn cho phép", "always"],
    ["Từ chối", "deny"],
  ])("sends %s as %s, then waits for the stream", async (label, decision) => {
    const mock = stub(() => new Response(null, { status: 204 }))
    render(<ApprovalCard turnId="turn-1" request={request()} />)

    fireEvent.click(screen.getByRole("button", { name: label }))

    await waitFor(() => expect(mock).toHaveBeenCalledOnce())
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe("/api/alpha-desk/turns/turn-1/approvals/call-1")
    expect(JSON.parse(init.body as string)).toEqual({ decision })
    // Inert until `approval.resolved` removes the card.
    expect(screen.getByRole("button", { name: "Từ chối" })).toBeDisabled()
    expect(await screen.findByText(/Đang chờ xác nhận/)).toBeInTheDocument()
  })

  it("names the connector and tool, labels a write, and shows the arguments in mono", () => {
    render(
      <ApprovalCard
        turnId="turn-1"
        request={request({ effect: "write", can_always: false, display: "Tạo ghi chú" })}
      />,
    )

    expect(screen.getByRole("region", { name: /Kho nội bộ muốn chạy Tạo ghi chú/ })).toBeInTheDocument()
    expect(screen.getByText("Ghi dữ liệu")).toBeInTheDocument()
    expect(screen.getByLabelText("Tham số của lệnh gọi")).toHaveTextContent('{"query":"VCB"}')
    // A write is approved one call at a time.
    expect(screen.queryByRole("button", { name: "Luôn cho phép" })).not.toBeInTheDocument()
    expect(screen.getByText(/Tự từ chối sau/)).toBeInTheDocument()
  })

  it("lets the reader try again after a refused 'always'", async () => {
    stub(() => json({ detail: { reason: "approve_once_only", message: "once" } }, 409))
    render(<ApprovalCard turnId="turn-1" request={request()} />)

    fireEvent.click(screen.getByRole("button", { name: "Luôn cho phép" }))

    expect(await screen.findByText(/chỉ được duyệt từng lần/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Cho phép một lần" })).toBeEnabled()
  })

  it("goes inert once the wait has run out", () => {
    render(
      <ApprovalCard
        turnId="turn-1"
        request={request({ expires_at: new Date(Date.now() - 1000).toISOString() })}
      />,
    )

    expect(screen.getByText("Đã hết hạn chờ")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Cho phép một lần" })).toBeDisabled()
  })
})

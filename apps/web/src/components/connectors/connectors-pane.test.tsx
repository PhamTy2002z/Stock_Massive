// @vitest-environment jsdom
/**
 * Settings › Kết nối, against a stubbed `fetch` so each assertion is about the
 * request that actually leaves the browser: path, method and body.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import { clearConnectorsPane, requestConnectorsPane } from "@/lib/connectors/open-pane"

import { ConnectorsPane } from "./connectors-pane"
import { connector, connectorsState, json, stubFetch, tool } from "./test-fixtures"

afterEach(() => {
  cleanup()
  clearConnectorsPane()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function open() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ConnectorsPane />
    </QueryClientProvider>,
  )
}

describe("the table", () => {
  it("lists each connector with its kind, auth and status in words", async () => {
    stubFetch(
      connectorsState({
        connectors: [
          connector(),
          connector({ id: "c-2", name: "Lịch", source: "catalog", catalog_id: 3, auth_type: "oauth", status: "needs_auth" }),
        ],
      }),
      () => json({}),
    )
    open()

    const rows = await screen.findAllByRole("row")
    expect(within(rows[1]).getByText("Kho nội bộ")).toBeInTheDocument()
    expect(within(rows[1]).getByText("Tuỳ chỉnh")).toBeInTheDocument()
    expect(within(rows[1]).getByText("Khoá")).toBeInTheDocument()
    expect(within(rows[1]).getByText("Đã kết nối")).toBeInTheDocument()
    expect(within(rows[2]).getByText("Danh mục")).toBeInTheDocument()
    expect(within(rows[2]).getByText("OAuth")).toBeInTheDocument()
    expect(within(rows[2]).getByText("Cần đăng nhập lại")).toBeInTheDocument()
  })

  it("says plainly that the feature is off, and offers nothing to press", async () => {
    stubFetch(connectorsState({ enabled: false }), () => json({}))
    open()

    expect(await screen.findByText(/chưa được bật/)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Thêm" })).not.toBeInTheDocument()
  })
})

describe("adding", () => {
  it("adds a custom URL with a key, and opens the new connector", async () => {
    const added = connector({ id: "c-new", name: "Máy chủ riêng" })
    const calls = stubFetch(connectorsState(), () => json(added, 201))
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Thêm" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "URL tuỳ chỉnh" }))
    fireEvent.change(screen.getByLabelText("Tên"), { target: { value: "Máy chủ riêng" } })
    fireEvent.change(screen.getByLabelText("URL máy chủ MCP"), {
      target: { value: "https://mcp.example.com/mcp" },
    })
    fireEvent.click(screen.getByRole("radio", { name: "Khoá" }))
    fireEvent.change(screen.getByLabelText("Khoá"), { target: { value: "bí-mật" } })
    fireEvent.click(screen.getByRole("button", { name: "Thêm kết nối" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({
      method: "POST",
      path: "/connectors",
      body: {
        name: "Máy chủ riêng",
        url: "https://mcp.example.com/mcp",
        header_name: "Authorization",
        header_value: "bí-mật",
      },
    })
    expect(await screen.findByRole("button", { name: "Kết nối của bạn" })).toBeInTheDocument()
  })

  it("does not offer a custom URL when this account may not add one", async () => {
    stubFetch(connectorsState({ custom_url_allowed: false }), () => json({}))
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Thêm" }))
    expect(screen.getByRole("menuitem", { name: "Từ danh mục" })).toBeInTheDocument()
    expect(screen.queryByRole("menuitem", { name: "URL tuỳ chỉnh" })).not.toBeInTheDocument()
  })

  it("adds a catalog entry by its id", async () => {
    const entry = { id: 7, slug: "tin", name: "Tin doanh nghiệp", description: "Tin tức", auth_type: "none" as const, trusted_data: false }
    const calls = stubFetch(connectorsState({ catalog: [entry] }), () =>
      json(connector({ id: "c-7", name: entry.name, source: "catalog", catalog_id: 7, auth_type: "none" }), 201),
    )
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Thêm" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "Từ danh mục" }))
    fireEvent.click(await screen.findByRole("button", { name: "Thêm Tin doanh nghiệp" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({ method: "POST", path: "/connectors", body: { catalog_id: 7 } })
  })

  it("shows the refusal in words when the server refuses the URL", async () => {
    stubFetch(connectorsState(), () =>
      json({ detail: { reason: "url_refused", message: "private address" } }, 422),
    )
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Thêm" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "URL tuỳ chỉnh" }))
    fireEvent.change(screen.getByLabelText("Tên"), { target: { value: "Nội bộ" } })
    fireEvent.change(screen.getByLabelText("URL máy chủ MCP"), { target: { value: "http://10.0.0.1/mcp" } })
    fireEvent.click(screen.getByRole("button", { name: "Thêm kết nối" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Địa chỉ máy chủ bị từ chối")
  })
})

describe("one connector", () => {
  const withTools = () =>
    connector({
      tools: [
        tool(),
        tool({
          name: "create_note",
          wire: "mcp__kho__create_note",
          title: "",
          effect: "write",
          action: "ask",
          allowed_actions: ["ask", "deny"],
        }),
        tool({ name: "list_tags", title: "Liệt kê nhãn", read_only_claimed_by_server: true }),
      ],
    })

  function openDetail() {
    requestConnectorsPane({ outcome: null, connectorId: "c-1" })
    open()
  }

  it("sends a PUT with the chosen action for one tool", async () => {
    const calls = stubFetch(connectorsState({ connectors: [withTools()] }), () => json(withTools()))
    openDetail()

    const group = await screen.findByRole("radiogroup", { name: "Quyền cho Tìm ghi chú" })
    fireEvent.click(within(group).getByRole("radio", { name: "Chặn" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({
      method: "PUT",
      path: "/connectors/c-1/tools/search_notes",
      body: { action: "deny" },
    })
  })

  it("never lets a write tool be set to Cho phép, and says why", async () => {
    stubFetch(connectorsState({ connectors: [withTools()] }), () => json(withTools()))
    openDetail()

    // No title: the row falls back to the tool's own name, never the wire name.
    const group = await screen.findByRole("radiogroup", { name: "Quyền cho create_note" })
    expect(within(group).getByRole("radio", { name: "Cho phép" })).toBeDisabled()
    expect(within(group).getByRole("radio", { name: "Cần duyệt" })).toBeEnabled()
    expect(group).toHaveAccessibleDescription("Công cụ ghi luôn cần duyệt")
    expect(screen.queryByText(/mcp__/)).not.toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Công cụ ghi" })).toHaveTextContent("1")
    expect(screen.getByText(/Máy chủ tự khai báo là chỉ đọc/)).toBeInTheDocument()
  })

  it("applies one action to a whole group, skipping tools that already have it", async () => {
    const calls = stubFetch(connectorsState({ connectors: [withTools()] }), () => json(withTools()))
    openDetail()

    fireEvent.change(await screen.findByLabelText("Đặt quyền cho tất cả công cụ chỉ đọc"), {
      target: { value: "ask" },
    })

    await waitFor(() => expect(calls).toHaveLength(2))
    expect(calls.map((call) => call.path)).toEqual([
      "/connectors/c-1/tools/search_notes",
      "/connectors/c-1/tools/list_tags",
    ])
  })

  it("disconnects only after an in-app confirmation, with a DELETE", async () => {
    const confirm = vi.spyOn(window, "confirm")
    const calls = stubFetch(connectorsState({ connectors: [withTools()] }), () => new Response(null, { status: 204 }))
    openDetail()

    fireEvent.click(await screen.findByRole("button", { name: "Ngắt kết nối" }))
    expect(calls).toHaveLength(0)
    const dialog = screen.getByRole("alertdialog")
    fireEvent.click(within(dialog).getByRole("button", { name: "Xác nhận ngắt kết nối" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ method: "DELETE", path: "/connectors/c-1" })
    expect(confirm).not.toHaveBeenCalled()
    // Back on the table, which no longer lists it.
    expect(await screen.findByText(/Chưa có kết nối nào/)).toBeInTheDocument()
  })

  it("shows a changed tool list and accepts it", async () => {
    const changed = withTools()
    changed.pending = { added: ["export_csv"], removed: ["list_tags"], changed: [], detected_at: null }
    changed.status = "needs_reconsent"
    changed.truncated = 3
    changed.dropped = [{ name: "evil", reason: "suspicious_text:instruction" }]
    const calls = stubFetch(connectorsState({ connectors: [changed] }), () => json(withTools()))
    openDetail()

    expect(await screen.findByText(/export_csv/)).toBeInTheDocument()
    expect(screen.getByText(/còn 3 công cụ vượt giới hạn 50/)).toBeInTheDocument()
    expect(screen.getByText(/nội dung đáng ngờ/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận thay đổi" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ method: "POST", path: "/connectors/c-1/accept" })
  })

  it("reports an OAuth return that failed", async () => {
    stubFetch(connectorsState({ connectors: [withTools()] }), () => json({}))
    requestConnectorsPane({ outcome: "failed", connectorId: "c-1" })
    open()

    expect(await screen.findByText("Đăng nhập không thành công. Hãy thử lại.")).toBeInTheDocument()
  })
})

// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import type { Thread } from "@/lib/alpha-desk/types"

const fixtures = vi.hoisted(() => ({
  threads: [] as Thread[],
  state: { sidebarOpen: true, viewport: 1440, inspector: null, overlay: null as string | null },
  dispatch: vi.fn(),
  openThread: vi.fn(),
  newThread: vi.fn(),
}))
vi.mock("@/hooks/use-threads", () => ({
  useThreads: () => ({ data: { threads: fixtures.threads }, isPending: false }),
  useUpdateThread: () => ({ mutate: vi.fn() }),
  useDeleteThread: () => ({ mutate: vi.fn() }),
}))
vi.mock("./desk-state", () => ({ useDesk: () => ({ threadId: null, ...fixtures }) }))
vi.mock("./shell-state", async (original) => ({
  ...(await original<typeof import("./shell-state")>()),
  useShell: () => ({ state: fixtures.state, dispatch: fixtures.dispatch }),
}))
vi.mock("./account-menu", () => ({ AccountMenu: () => null }))
import { Sidebar } from "./sidebar"
import { Overlays } from "./overlays"

beforeEach(() => {
  vi.clearAllMocks()
  fixtures.state = { sidebarOpen: true, viewport: 1440, inspector: null, overlay: null }
  fixtures.threads = ["VCB", "FPT"].map((title, i) => ({
    id: `thread-${i}`, title, symbols: [], pinned_at: null,
    created_at: "2026-09-27T02:00:00Z", updated_at: "2026-09-27T02:00:00Z",
  }))
})
afterEach(cleanup)

it("offers search and new chat without unavailable destinations or an empty pinned group", () => {
  render(<Sidebar />)
  expect(screen.queryByText("Đã ghim")).not.toBeInTheDocument()
  for (const label of ["Bộ lọc cổ phiếu", "Báo cáo đã lưu", "Danh mục theo dõi"]) {
    expect(screen.queryByText(label)).not.toBeInTheDocument()
  }
  fireEvent.click(screen.getByRole("button", { name: "Tìm hội thoại" }))
  expect(fixtures.dispatch).toHaveBeenCalledWith({ type: "overlay", overlay: "palette" })
  fireEvent.click(screen.getByRole("button", { name: "Trò chuyện mới" }))
  expect(fixtures.newThread).toHaveBeenCalledOnce()
})

it("keeps older conversations reachable through the complete search list", () => {
  fixtures.threads = Array.from({ length: 21 }, (_, i) => ({ ...fixtures.threads[0], id: `id-${i}`, title: `Hội thoại ${i}` }))
  const view = render(<Sidebar />)
  expect(screen.queryByRole("button", { name: "Hội thoại 20" })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Xem tất cả" }))
  expect(fixtures.dispatch).toHaveBeenCalledWith({ type: "overlay", overlay: "palette" })
  view.unmount()
  fixtures.state.overlay = "palette"
  render(<Overlays />)
  expect(screen.getAllByRole("option")).toHaveLength(21)
  fireEvent.click(screen.getByRole("option", { name: "Hội thoại 20" }))
  expect(fixtures.openThread).toHaveBeenCalledWith("id-20")
})

it("dismisses the floating sidebar after opening a conversation or starting a new one", () => {
  fixtures.state.viewport = 375
  render(<Sidebar />)
  fireEvent.click(screen.getByRole("button", { name: "VCB" }))
  expect(fixtures.openThread).toHaveBeenCalledWith("thread-0")
  expect(fixtures.dispatch).toHaveBeenCalledWith({ type: "toggle-sidebar" })
  fixtures.dispatch.mockClear()
  fireEvent.click(screen.getByRole("button", { name: "Trò chuyện mới" }))
  expect(fixtures.newThread).toHaveBeenCalledOnce()
  expect(fixtures.dispatch).toHaveBeenCalledWith({ type: "toggle-sidebar" })
})

it("opens the keyboard-selected search result and resets selection after filtering", () => {
  fixtures.state.overlay = "palette"
  render(<Overlays />)
  const input = screen.getByRole("combobox")
  fireEvent.keyDown(input, { key: "ArrowDown" })
  expect(screen.getByRole("option", { name: "FPT" })).toHaveAttribute("aria-selected", "true")
  fireEvent.keyDown(input, { key: "Enter" })
  expect(fixtures.openThread).toHaveBeenCalledWith("thread-1")
  fireEvent.change(input, { target: { value: "VCB" } })
  fireEvent.keyDown(input, { key: "Enter" })
  expect(fixtures.openThread).toHaveBeenLastCalledWith("thread-0")
})

it("recovers from an empty search without navigating on Enter", () => {
  fixtures.state.overlay = "palette"
  render(<Overlays />)
  const input = screen.getByRole("combobox")
  fireEvent.change(input, { target: { value: "missing" } })
  fireEvent.keyDown(input, { key: "ArrowDown" })
  fireEvent.keyDown(input, { key: "Enter" })
  expect(fixtures.openThread).not.toHaveBeenCalled()
  expect(screen.getByRole("status")).toHaveTextContent("Thử từ khóa khác")
  fireEvent.click(screen.getByRole("button", { name: "Xóa tìm kiếm" }))
  expect(screen.getAllByRole("option")).toHaveLength(2)
})

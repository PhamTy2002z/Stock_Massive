// @vitest-environment jsdom
/**
 * What the sidebar's per-Thread menu promises.
 *
 * Four writes and one link, and the interesting half of each is what it does
 * *not* do: pinning sends no title, a rename abandoned with Escape sends
 * nothing at all, and delete takes the Thread on the press itself.
 *
 * The list, the mutations and the conversation are mocked at their hook
 * boundaries. The ordering is the backend's and is tested there; this file is
 * about the control surface over it.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"

import type { Thread } from "@/lib/alpha-desk/types"

const update = { mutate: vi.fn() }
const remove = { mutate: vi.fn() }
const threads = { data: { threads: [] as Thread[] }, isPending: false }

vi.mock("@/hooks/use-threads", () => ({
  useThreads: () => threads,
  useUpdateThread: () => update,
  useDeleteThread: () => remove,
}))

const desk = { threadId: null as string | null, openThread: vi.fn(), newThread: vi.fn() }
vi.mock("./desk-state", () => ({ useDesk: () => desk }))

const dispatch = vi.fn()
vi.mock("./shell-state", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./shell-state")>()),
  useShell: () => ({ state: {}, dispatch }),
}))

import { Conversations } from "./sidebar"

function thread(overrides: Partial<Thread> = {}): Thread {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    title: "Xu hướng STB",
    symbols: [],
    pinned_at: null,
    created_at: "2026-08-16T02:00:00Z",
    updated_at: "2026-08-16T02:00:00Z",
    ...overrides,
  }
}

/** Open one row's menu the way a user does: press its ellipsis. */
function openMenu(name: string) {
  fireEvent.click(screen.getByRole("button", { name: `Tuỳ chọn cho ${name}` }))
  return screen.getByRole("menu")
}

afterEach(cleanup)

beforeEach(() => {
  update.mutate.mockClear()
  remove.mutate.mockClear()
  desk.threadId = null
  threads.isPending = false
  threads.data = { threads: [thread()] }
})

describe("the two groups", () => {
  it("puts a pinned Thread under Đã ghim and leaves it out of the other list", () => {
    threads.data = {
      threads: [
        thread({ id: "pinned-id", title: "Ghim", pinned_at: "2026-08-16T03:00:00Z" }),
        thread({ id: "plain-id", title: "Thường" }),
      ],
    }

    render(<Conversations />)

    // One row each, and neither name appears twice anywhere in the tree.
    expect(screen.getAllByText("Ghim")).toHaveLength(1)
    expect(screen.getAllByText("Thường")).toHaveLength(1)
  })

  it("says the list is empty only when nothing is pinned either", () => {
    threads.data = {
      threads: [thread({ title: "Ghim", pinned_at: "2026-08-16T03:00:00Z" })],
    }

    render(<Conversations />)

    expect(screen.getByText(/Tất cả hội thoại đang được ghim/)).toBeInTheDocument()
  })
})

describe("the menu", () => {
  it("pins without sending a title", () => {
    render(<Conversations />)

    fireEvent.click(within(openMenu("Xu hướng STB")).getByRole("menuitem", { name: "Ghim" }))

    expect(update.mutate).toHaveBeenCalledWith({
      threadId: "11111111-1111-4111-8111-111111111111",
      pinned: true,
    })
  })

  it("offers the opposite action on a Thread that is already pinned", () => {
    threads.data = { threads: [thread({ pinned_at: "2026-08-16T03:00:00Z" })] }
    render(<Conversations />)

    fireEvent.click(within(openMenu("Xu hướng STB")).getByRole("menuitem", { name: "Bỏ ghim" }))

    expect(update.mutate).toHaveBeenCalledWith({
      threadId: "11111111-1111-4111-8111-111111111111",
      pinned: false,
    })
  })

  it("links a new tab at the Thread's own deep link", () => {
    render(<Conversations />)

    const link = within(openMenu("Xu hướng STB")).getByRole("link", { name: /Mở ở tab mới/ })

    expect(link).toHaveAttribute("href", "/?thread=11111111-1111-4111-8111-111111111111")
    expect(link).toHaveAttribute("target", "_blank")
  })

  it("deletes on the press, without a second confirmation", () => {
    render(<Conversations />)

    fireEvent.click(within(openMenu("Xu hướng STB")).getByRole("menuitem", { name: "Xoá" }))

    expect(remove.mutate).toHaveBeenCalledWith(
      "11111111-1111-4111-8111-111111111111",
      expect.anything(),
    )
  })

  it("closes on Escape without writing anything", () => {
    render(<Conversations />)
    openMenu("Xu hướng STB")

    fireEvent.keyDown(document, { key: "Escape" })

    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(update.mutate).not.toHaveBeenCalled()
    expect(remove.mutate).not.toHaveBeenCalled()
  })
})

describe("renaming in place", () => {
  it("commits what was typed on Enter", () => {
    render(<Conversations />)
    fireEvent.click(within(openMenu("Xu hướng STB")).getByRole("menuitem", { name: "Đổi tên" }))

    const field = screen.getByRole("textbox")
    fireEvent.change(field, { target: { value: "  Cổ phiếu STB  " } })
    fireEvent.keyDown(field, { key: "Enter" })
    fireEvent.blur(field)

    expect(update.mutate).toHaveBeenCalledWith({
      threadId: "11111111-1111-4111-8111-111111111111",
      title: "Cổ phiếu STB",
    })
  })

  it("writes nothing when Escape abandons it", () => {
    render(<Conversations />)
    fireEvent.click(within(openMenu("Xu hướng STB")).getByRole("menuitem", { name: "Đổi tên" }))

    const field = screen.getByRole("textbox")
    fireEvent.change(field, { target: { value: "bỏ đi" } })
    fireEvent.keyDown(field, { key: "Escape" })
    fireEvent.blur(field)

    expect(update.mutate).not.toHaveBeenCalled()
    expect(screen.getByText("Xu hướng STB")).toBeInTheDocument()
  })

  it("writes nothing when the name was not actually changed", () => {
    render(<Conversations />)
    fireEvent.click(within(openMenu("Xu hướng STB")).getByRole("menuitem", { name: "Đổi tên" }))

    fireEvent.blur(screen.getByRole("textbox"))

    expect(update.mutate).not.toHaveBeenCalled()
  })
})

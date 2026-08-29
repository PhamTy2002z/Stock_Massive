// @vitest-environment jsdom
/**
 * What the bar above the conversation promises.
 *
 * The menu behind the chevron used to be drawn and inert. It now writes to the
 * same three endpoints the sidebar's per-Thread menu writes to, so the tests
 * that matter are the ones saying the two menus mean the same thing: a pin
 * carries no title, a rename abandoned with Escape sends nothing, and delete
 * takes the Thread on the press and leaves the reader in an empty composer.
 *
 * The list, the mutations and the conversation are mocked at their hook
 * boundaries; this file is about the control surface over them.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { Thread } from "@/lib/alpha-desk/types"

const update = { mutate: vi.fn() }
const remove = { mutate: vi.fn() }
const threads = { data: { threads: [] as Thread[] } }

vi.mock("@/hooks/use-threads", () => ({
  useThreads: () => threads,
  useUpdateThread: () => update,
  useDeleteThread: () => remove,
}))

const desk = { threadId: null as string | null, openThread: vi.fn(), newThread: vi.fn() }
vi.mock("./desk-state", () => ({ useDesk: () => desk }))

const dispatch = vi.fn()
const state = {
  view: "chat",
  sidebarOpen: true,
  signalDesk: false,
  inspector: null as string | null,
  overlay: null as string | null,
}
vi.mock("./shell-state", () => ({ useShell: () => ({ state, dispatch }) }))

import { TopBar } from "./top-bar"

const THREAD_ID = "11111111-1111-4111-8111-111111111111"

function thread(overrides: Partial<Thread> = {}): Thread {
  return {
    id: THREAD_ID,
    title: "Xu hướng STB",
    symbols: [],
    pinned_at: null,
    created_at: "2026-08-16T02:00:00Z",
    updated_at: "2026-08-16T02:00:00Z",
    ...overrides,
  }
}

/** The bar with the menu already down, which is the only state it acts in. */
function openMenu() {
  state.overlay = "thread"
  render(<TopBar />)
  return screen.getByRole("menu")
}

afterEach(cleanup)

beforeEach(() => {
  update.mutate.mockClear()
  remove.mutate.mockClear()
  desk.newThread.mockClear()
  desk.threadId = THREAD_ID
  threads.data = { threads: [thread()] }
  state.overlay = null
  state.signalDesk = false
})

describe("the name", () => {
  it("keeps the first few words of a long one and hands over the rest as a tooltip", () => {
    threads.data = { threads: [thread({ title: "Trong ảnh này VCB đóng cửa bao nhiêu và vì sao" })] }

    render(<TopBar />)

    const heading = screen.getByRole("heading", { level: 1 })
    expect(heading).toHaveTextContent("Trong ảnh này VCB đóng cửa…")
    expect(heading).toHaveAttribute("title", "Trong ảnh này VCB đóng cửa bao nhiêu và vì sao")
  })

  it("leaves a short name whole and gives it no tooltip", () => {
    render(<TopBar />)

    const heading = screen.getByRole("heading", { level: 1 })
    expect(heading).toHaveTextContent("Xu hướng STB")
    expect(heading).not.toHaveAttribute("title")
  })
})

describe("pin", () => {
  it("sends the flag and nothing else", () => {
    openMenu()

    fireEvent.click(screen.getByRole("menuitem", { name: /Ghim/ }))

    expect(update.mutate).toHaveBeenCalledWith({ threadId: THREAD_ID, pinned: true })
  })

  it("offers to undo it once the Thread is pinned", () => {
    threads.data = { threads: [thread({ pinned_at: "2026-08-16T03:00:00Z" })] }
    openMenu()

    fireEvent.click(screen.getByRole("menuitem", { name: /Bỏ ghim/ }))

    expect(update.mutate).toHaveBeenCalledWith({ threadId: THREAD_ID, pinned: false })
  })
})

describe("rename", () => {
  it("puts a field where the name was and writes what was typed", () => {
    openMenu()

    fireEvent.click(screen.getByRole("menuitem", { name: /Đổi tên/ }))
    const field = screen.getByRole("textbox")
    fireEvent.change(field, { target: { value: "Định giá STB" } })
    fireEvent.blur(field)

    expect(update.mutate).toHaveBeenCalledWith({ threadId: THREAD_ID, title: "Định giá STB" })
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Xu hướng STB")
  })

  it("writes nothing when the field is abandoned with Escape", () => {
    openMenu()

    fireEvent.click(screen.getByRole("menuitem", { name: /Đổi tên/ }))
    const field = screen.getByRole("textbox")
    fireEvent.change(field, { target: { value: "Bỏ đi" } })
    fireEvent.keyDown(field, { key: "Escape" })
    fireEvent.blur(field)

    expect(update.mutate).not.toHaveBeenCalled()
  })
})

describe("delete", () => {
  it("takes the Thread on the press and leaves an empty composer behind", () => {
    openMenu()

    fireEvent.click(screen.getByRole("menuitem", { name: /Xoá/ }))

    expect(remove.mutate).toHaveBeenCalledTimes(1)
    const [id, options] = remove.mutate.mock.calls[0]
    expect(id).toBe(THREAD_ID)
    options.onSuccess()
    expect(desk.newThread).toHaveBeenCalled()
  })
})

describe("the letters printed on the rows", () => {
  it("act while the menu is down", () => {
    openMenu()

    fireEvent.keyDown(window, { key: "p" })

    expect(update.mutate).toHaveBeenCalledWith({ threadId: THREAD_ID, pinned: true })
  })

  it("stay out of the way of the shortcuts that carry a modifier", () => {
    openMenu()

    fireEvent.keyDown(window, { key: "d", metaKey: true })

    expect(remove.mutate).not.toHaveBeenCalled()
  })
})

describe("what the menu cannot do", () => {
  it("badges the read flag as unavailable rather than pretending to keep one", () => {
    openMenu()

    expect(screen.getByRole("menuitem", { name: /Đánh dấu chưa đọc/ })).toBeDisabled()
  })

  it("deadens every write while the bar names a Thread the server has not seen", () => {
    desk.threadId = null
    threads.data = { threads: [] }
    openMenu()

    for (const name of [/Ghim/, /Đổi tên/, /Xoá/]) {
      expect(screen.getByRole("menuitem", { name })).toBeDisabled()
    }
    fireEvent.keyDown(window, { key: "d" })
    expect(remove.mutate).not.toHaveBeenCalled()
  })
})

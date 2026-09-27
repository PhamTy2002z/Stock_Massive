// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { Composer } from "./composer"
import { ShellProvider } from "./shell-state"
import { SEND_LABEL } from "@/lib/alpha-desk/copy"

const desk = {
  attachments: [], canCancel: false, isSubmitting: false, isCancelling: false,
  submit: vi.fn(), cancel: vi.fn(),
}
vi.mock("./desk-state", () => ({ useDesk: () => desk }))
afterEach(() => {
  cleanup()
  Object.assign(desk, { canCancel: false, isSubmitting: false, isCancelling: false })
  vi.clearAllMocks()
})

it("keeps one fixed-size control through Enter, admission, stop and completion", () => {
  const ui = <ShellProvider><Composer /></ShellProvider>
  const view = render(ui)
  const field = screen.getByRole("textbox")
  fireEvent.change(field, { target: { value: "VCB thế nào?" } })
  const button = screen.getByRole("button", { name: SEND_LABEL })
  fireEvent.keyDown(field, { key: "Enter", shiftKey: true })
  fireEvent.keyDown(field, { key: "Enter", isComposing: true })
  expect(desk.submit).not.toHaveBeenCalled()
  fireEvent.keyDown(field, { key: "Enter" })
  expect(desk.submit).toHaveBeenCalledExactlyOnceWith("VCB thế nào?")
  desk.isSubmitting = true
  view.rerender(<ShellProvider><Composer /></ShellProvider>)
  expect(screen.getByRole("button", { name: "Đang gửi…" })).toBe(button)
  expect(button).toBeDisabled()
  desk.isSubmitting = false
  desk.canCancel = true
  view.rerender(<ShellProvider><Composer /></ShellProvider>)
  expect(screen.getByRole("button", { name: "Dừng" })).toBe(button)
  expect(button).toHaveClass("size-9")
  fireEvent.click(button)
  expect(desk.cancel).toHaveBeenCalledOnce()
  desk.canCancel = false
  desk.isCancelling = true
  view.rerender(<ShellProvider><Composer /></ShellProvider>)
  expect(button).toBeDisabled()
  fireEvent.change(field, { target: { value: "Câu hỏi tiếp theo" } })
  fireEvent.keyDown(field, { key: "Enter" })
  expect(desk.submit).toHaveBeenCalledOnce()
  desk.isCancelling = false
  desk.canCancel = false
  view.rerender(<ShellProvider><Composer /></ShellProvider>)
  expect(screen.getByRole("button", { name: SEND_LABEL })).toBe(button)
})

// @vitest-environment jsdom
/**
 * The rule the whole failure system rests on: a control that appears can work.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FailureState } from "@/components/ui/failure-state"
import { ApiError } from "@/lib/api"
import { describeFailure } from "@/lib/failure"

afterEach(cleanup)

const forbidden = describeFailure(new ApiError(403, "no"))
const offline = describeFailure(new TypeError("Failed to fetch"))
const expired = describeFailure(new ApiError(401, "no"))

describe("the recovery control", () => {
  it("is absent when nothing would change by pressing it", () => {
    render(<FailureState failure={forbidden} onRetry={() => {}} />)

    // A retry handler is passed and still no button appears: the failure, not
    // the call site, decides whether there is a way out.
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.getByText(forbidden.title)).toBeInTheDocument()
  })

  it("is absent when the way out exists but nothing was wired to it", () => {
    // Better a sentence with no button than a button with no effect.
    render(<FailureState failure={offline} />)
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("runs the caller's recovery when there is one", () => {
    const retry = vi.fn()
    render(<FailureState failure={offline} onRetry={retry} />)

    fireEvent.click(screen.getByRole("button", { name: /Thử lại/ }))
    expect(retry).toHaveBeenCalledTimes(1)
  })

  it("sends an expired session to sign in, without needing a handler", () => {
    render(<FailureState failure={expired} />)

    const link = screen.getByRole("link", { name: "Đăng nhập lại" })
    expect(link).toHaveAttribute("href", "/login")
  })
})

describe("density", () => {
  it("announces a failure that replaced content, so it is not silent", () => {
    render(<FailureState failure={offline} density="inline" onRetry={() => {}} />)
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })

  it("carries the heading only where there is room for one", () => {
    const { rerender } = render(<FailureState failure={offline} density="inline" />)
    expect(screen.queryByText(offline.title)).not.toBeInTheDocument()

    rerender(<FailureState failure={offline} density="region" />)
    expect(screen.getByText(offline.title)).toBeInTheDocument()
  })

  it("spends the filled accent only on the page, where nothing competes", () => {
    // The rationed-amber rule is per view: a pane inside the shell sits beside
    // a composer that already spends the view's one filled control.
    const { container, rerender } = render(
      <FailureState failure={offline} density="page" onRetry={() => {}} />,
    )
    expect(container.querySelector("button")?.className).toContain("bg-primary")

    rerender(<FailureState failure={offline} density="region" onRetry={() => {}} />)
    expect(container.querySelector("button")?.className).not.toContain("bg-primary")
  })

  it("omits empty explanatory copy from the unexpected-error page", () => {
    const unexpected = describeFailure({})
    const { container } = render(
      <FailureState failure={unexpected} density="page" onRetry={() => {}} />,
    )

    expect(unexpected.detail).toBe("")
    expect(container.querySelector("p")).toBeNull()
    expect(screen.getByRole("heading", { name: unexpected.title })).toBeInTheDocument()
  })
})

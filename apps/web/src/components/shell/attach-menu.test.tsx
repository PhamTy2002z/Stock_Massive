// @vitest-environment jsdom
/**
 * The attach menu's first test, and what it is guarding.
 *
 * This menu shipped with six rows, all of them inert, and **no test at all** —
 * `AttachMenu|Thêm tệp|attachOpen` matched nothing outside `composer.tsx`. So
 * nothing below is a regression net over old behaviour; all of it is new ground
 * for a menu that now has two rows that do something and one that says plainly
 * that they do not.
 *
 * The one property worth the most here is the count of badges. `MenuItem` draws
 * the badge automatically from `disabled`, so a row that stops working starts
 * promising — and a `getByText` would not notice, because the badge would still
 * be found. Counting is what catches it.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import { ATTACHMENT_COPY, CAPTURE_COPY } from "@/lib/alpha-desk/copy"

import { AttachMenu } from "./composer"
import { COMING_SOON } from "./primitives"

afterEach(cleanup)

function open(overrides: Partial<Parameters<typeof AttachMenu>[0]> = {}) {
  const onPickFile = vi.fn()
  const onCapture = vi.fn()
  const view = render(
    <AttachMenu onPickFile={onPickFile} onCapture={onCapture} supported {...overrides} />,
  )
  return { view, onPickFile, onCapture }
}

describe("the shape the menu settled on", () => {
  it("offers exactly three rows", () => {
    open()

    expect(screen.getAllByRole("menuitem")).toHaveLength(3)
  })

  it("names them in the agreed order", () => {
    open()

    expect(
      screen.getAllByRole("menuitem").map((row) => row.textContent?.replace(COMING_SOON, "").trim()),
    ).toEqual([
      `${ATTACHMENT_COPY.add}${ATTACHMENT_COPY.addHint}`,
      CAPTURE_COPY.row,
      "Thêm vào danh mục",
    ])
  })

  it("has no row about looking up the news", () => {
    // Removed rather than left inert: `web_search` and `fetch_url` are in the
    // chat lane's toolset on every Turn, so a badge over them read as a false
    // statement, and a switch for something already running misleads. Where the
    // reader sees what was looked up is the Sources panel.
    open()

    for (const word of ["tin tức", "web", "tìm kiếm"]) {
      expect(screen.queryByText(new RegExp(word, "i"))).not.toBeInTheDocument()
    }
  })
})

describe("which rows promise and which deliver", () => {
  it("puts a badge on exactly the one row that does nothing yet", () => {
    // Counted, not merely found. The badge is drawn from `disabled`, so one
    // spreading to a working row is a promise nobody made — and a `getByText`
    // would still pass, because it would still find a badge.
    open()

    expect(screen.getAllByText(COMING_SOON)).toHaveLength(1)
  })

  it("leaves the two working rows with no badge at all", () => {
    open()

    for (const name of [ATTACHMENT_COPY.add, CAPTURE_COPY.row]) {
      const row = screen.getByRole("menuitem", { name: new RegExp(name) })
      expect(row).not.toBeDisabled()
      expect(within(row).queryByText(COMING_SOON)).not.toBeInTheDocument()
    }
  })

  it("opens the file picker from the first row", () => {
    const { onPickFile } = open()

    fireEvent.click(screen.getByRole("menuitem", { name: new RegExp(ATTACHMENT_COPY.add) }))

    expect(onPickFile).toHaveBeenCalledTimes(1)
  })

  it("starts a capture from the second row", () => {
    const { onCapture } = open()

    fireEvent.click(screen.getByRole("menuitem", { name: new RegExp(CAPTURE_COPY.row) }))

    expect(onCapture).toHaveBeenCalledTimes(1)
  })

  it("keeps the capture row inert, badge and all, where the browser cannot", () => {
    open({ supported: false })

    const row = screen.getByRole("menuitem", { name: new RegExp(CAPTURE_COPY.row) })
    expect(row).toBeDisabled()
    expect(screen.getAllByText(COMING_SOON)).toHaveLength(2)
  })
})

describe("what a screen reader is told about a row it cannot press", () => {
  it("points every inert row at a description that exists", () => {
    // A badge only the eye can see says nothing about *why* a row is inert. This
    // is also the contract `260827-2325/phase-02` narrowed to: a disabled control
    // must be described, rather than not exist.
    open()

    const inert = screen.getAllByRole("menuitem").filter((row) => (row as HTMLButtonElement).disabled)
    expect(inert).toHaveLength(1)
    for (const row of inert) {
      const describedBy = row.getAttribute("aria-describedby")
      expect(describedBy).toBeTruthy()
      expect(document.getElementById(describedBy as string)).toHaveTextContent(COMING_SOON)
    }
  })

  it("says nothing extra about a row that works", () => {
    open()

    for (const name of [ATTACHMENT_COPY.add, CAPTURE_COPY.row]) {
      const row = screen.getByRole("menuitem", { name: new RegExp(name) })
      expect(row).not.toHaveAttribute("aria-describedby")
    }
  })

  it("gives two menus on one page ids that do not collide", () => {
    // `useId` rather than a label-derived key: two rows can carry the same words.
    render(
      <>
        <AttachMenu onPickFile={vi.fn()} onCapture={vi.fn()} supported />
        <AttachMenu onPickFile={vi.fn()} onCapture={vi.fn()} supported />
      </>,
    )

    const ids = screen
      .getAllByRole("menuitem")
      .map((row) => row.getAttribute("aria-describedby"))
      .filter((id): id is string => id !== null)

    expect(ids).toHaveLength(2)
    expect(new Set(ids).size).toBe(2)
  })
})

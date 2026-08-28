// @vitest-environment jsdom
/**
 * The ranking, and the two things it must not do quietly.
 *
 * **A top eight is not a list.** Cutting at eight rows is right — beyond that a
 * ranking is a table — but a cut nobody is told about makes a complete list of
 * six and a truncated list of thirty look like the same claim.
 *
 * **The leader is the only accent.** It is the row the ranking exists to name;
 * a second accented bar spends the mark that means "this one".
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { RankedBarsWidget } from "./ranked-bars"

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 30,
  health: "normal",
  reason: null,
}

beforeEach(() => {
  // ResizeObserver is what recharts measures its container with, and jsdom has
  // none. The assertions here are about the words on the page.
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function frame(count: number): Frame {
  return {
    kind: "table",
    columns: ["bucket", "share"],
    rows: Array.from({ length: count }, (_, index) => [
      `09:${String(index).padStart(2, "0")}`,
      (count - index) / 100,
    ]),
    unit: "share",
    labels: { bucket: "Khung giờ", share: "Tỷ trọng trong phiên" },
  }
}

function draw(count: number) {
  return render(
    <RankedBarsWidget
      frame={frame(count)}
      options={{ label: "bucket", value: "share", valueFormat: "percent" }}
      provenance={PROVENANCE}
    />,
  )
}

describe("what the ranking leaves out", () => {
  it("counts the rows it did not show, so a top eight is not read as a list", () => {
    const { container } = draw(30)

    expect(container.textContent).toContain("Còn 22 mục")
  })

  it("says nothing when it showed everything", () => {
    const { container } = draw(6)

    expect(container.textContent).not.toContain("Còn")
  })

  it("says there is nothing to rank rather than drawing an empty axis", () => {
    const { container } = render(
      <RankedBarsWidget
        frame={{ ...frame(1), rows: [["09:00", null]] }}
        options={{ label: "bucket", value: "share" }}
        provenance={PROVENANCE}
      />,
    )

    expect(container.textContent).toContain("Không có hạng nào")
  })
})

// @vitest-environment jsdom
/**
 * What a block does when the widget drawing it throws.
 *
 * The registry degrades on what it can see before rendering — a version this
 * build does not know, a kind the widget does not accept. What it cannot see is
 * a frame that satisfies the contract and still breaks the chart runtime, and
 * that throw does not stay in the block: React unmounts every ancestor up to
 * the nearest boundary, so one unlucky block would take the whole desk and the
 * answer beside it.
 *
 * The registry is mocked rather than a real widget, because the point under
 * test is the block's own containment and not any particular chart's arithmetic
 * — and a test that had to find a frame that genuinely breaks recharts would be
 * pinned to the version of recharts that broke on it.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SignalDeskBlock, Frame, Provenance } from "@/lib/alpha-desk/types"

import { DataTableWidget } from "./widgets/data-table"

vi.mock("./widget-registry", async () => {
  const actual = await vi.importActual<typeof import("./widget-registry")>(
    "./widget-registry",
  )
  return {
    ...actual,
    resolveWidget: () => ({
      component: function Exploding(): never {
        throw new Error("recharts could not build a scale for this domain")
      },
      degraded: false,
    }),
  }
})

const { SignalDeskBlockView } = await import("./signal-desk-block")

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 30,
  health: "normal",
  reason: null,
}

const FRAME: Frame = {
  kind: "table",
  columns: ["label", "value"],
  rows: [["Khối lượng trung bình", 380_000]],
  unit: null,
  labels: { label: "Chỉ số", value: "Giá trị" },
}

const BLOCK: SignalDeskBlock = {
  widget: "bar_series",
  widgetVersion: 1,
  frame: "buckets",
  options: {},
}

describe("a widget that throws", () => {
  it("is contained, and leaves the numbers on screen as a table", () => {
    // React reports a caught render error on `console.error` regardless of the
    // boundary. Silenced so a passing test does not read as a failing one.
    const quiet = vi.spyOn(console, "error").mockImplementation(() => {})

    expect(() =>
      render(
        <SignalDeskBlockView block={BLOCK} frame={FRAME} provenance={PROVENANCE} />,
      ),
    ).not.toThrow()

    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByText("Khối lượng trung bình")).toBeInTheDocument()
    expect(screen.getByText(/không vẽ được bar_series/)).toBeInTheDocument()

    quiet.mockRestore()
  })

  it("renders the same frame the widget was handed", () => {
    const quiet = vi.spyOn(console, "error").mockImplementation(() => {})

    const { container } = render(
      <SignalDeskBlockView block={BLOCK} frame={FRAME} provenance={PROVENANCE} />,
    )
    const table = render(
      <DataTableWidget frame={FRAME} options={{}} provenance={PROVENANCE} />,
    )

    // The fallback is not a summary or a placeholder: it is the frame, whole,
    // through the widget every viewer is required to have.
    expect(container.querySelector("tbody")?.textContent).toBe(
      table.container.querySelector("tbody")?.textContent,
    )

    quiet.mockRestore()
  })
})

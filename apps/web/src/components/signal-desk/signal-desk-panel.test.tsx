// @vitest-environment jsdom

/**
 * The pane's four states, and the two failures it has to contain.
 *
 * jsdom draws nothing, so `vitest.setup.ts` gives every test a no-op 2D context
 * and ECharts runs to completion against it. It was left unstubbed once, on the
 * reading that a renderer failing here proved the pane contains its failures —
 * it proved the opposite: the paint happens on an animation frame after the
 * test returns, so the throw arrived as an uncaught exception outside every
 * catch in the tree, and the run failed while this file passed.
 *
 * What Flint does with an input is proved against the pinned package in
 * `lib/flint/compile-visual.test.ts`, and that the compiled option reaches the
 * renderer exactly once and unedited is proved by the phase's own `rg` gate.
 * What is left for this file is everything around the paint: which state is
 * drawn, and what a reader on a screen reader is told.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import type { VisualPart } from "@/lib/alpha-desk/types"

import { SignalDeskPanel } from "./signal-desk-panel"

/** jsdom has no `matchMedia`; the panel asks it whether to keep still. */
const matchMedia = vi.fn(() => ({ matches: false }) as unknown as MediaQueryList)
Object.defineProperty(window, "matchMedia", { configurable: true, value: matchMedia })

afterEach(() => {
  cleanup()
  matchMedia.mockClear()
})

/** One row in the shape the assembler sends: short label, whole dong. */
const ROWS = [
  {
    "Phiên": "24/08",
    "Mở": 72_500,
    "Cao": 72_700,
    "Thấp": 71_400,
    "Đóng": 71_400,
    "Khối lượng": 4_611_900,
  },
]

const VISUAL: VisualPart = {
  version: 1,
  renderer: "flint-echarts",
  flintVersion: "0.5.1",
  asOf: "2026-09-04T17:00:00+07:00",
  title: "FPT · nến ngày · 24/08/2026",
  assemblies: [
    {
      data: { values: ROWS },
      chart_spec: {
        chartType: "Candlestick Chart",
        encodings: { x: "Phiên", open: "Mở", high: "Cao", low: "Thấp", close: "Đóng" },
        baseSize: { width: 420, height: 260 },
      },
    },
    {
      data: { values: ROWS },
      chart_spec: {
        chartType: "Bar Chart",
        encodings: { x: "Phiên", y: "Khối lượng" },
        baseSize: { width: 420, height: 190 },
      },
    },
  ],
  evidenceIds: ["ev_1"],
  sourceCallIds: ["call_1"],
}

describe("the four states of the pane", () => {
  it("draws the opening board before anything has been asked", () => {
    render(<SignalDeskPanel view={{ state: "empty" }} />)

    expect(screen.getByText(SIGNAL_DESK_COPY.emptyTitle)).toBeDefined()
  })

  it("announces that a chart is being worked out, and shows no old chart", () => {
    render(<SignalDeskPanel view={{ state: "working" }} />)

    const status = screen.getByRole("status")
    expect(status.getAttribute("aria-busy")).toBe("true")
    expect(status.getAttribute("aria-live")).toBe("polite")
    expect(screen.queryByRole("figure")).toBeNull()
  })

  it("says in one line when a settled answer has no chart", () => {
    render(<SignalDeskPanel view={{ state: "none" }} />)

    // One line and no reason: the reason is the ledger's gaps, and it is
    // already written out in the column to the left.
    expect(screen.getByText(SIGNAL_DESK_COPY.chartAbsent)).toBeDefined()
  })

  it("draws the compiled chart with a label and its provenance", async () => {
    render(<SignalDeskPanel view={{ state: "chart", visual: VISUAL }} />)

    const figure = await screen.findByRole("figure")
    expect(figure.getAttribute("aria-label")).toBe(VISUAL.title)
    expect(screen.getByText(VISUAL.title)).toBeDefined()
    expect(
      screen.getByText(SIGNAL_DESK_COPY.chartProvenance(1, VISUAL.asOf)),
    ).toBeDefined()
  })

  it("gives the stacked pair one box each, at the heights the host chose", async () => {
    const { container } = render(
      <SignalDeskPanel view={{ state: "chart", visual: VISUAL }} />,
    )

    await screen.findByRole("figure")
    const boxes = [...container.querySelectorAll("figure > div")]
    expect(boxes.map((box) => (box as HTMLElement).style.height)).toEqual([
      "260px",
      "190px",
    ])
  })
})

describe("a failure stays inside the pane", () => {
  it("says so when the payload cannot be compiled", async () => {
    const broken: VisualPart = {
      ...VISUAL,
      assemblies: [
        {
          ...VISUAL.assemblies[0],
          chart_spec: {
            ...VISUAL.assemblies[0].chart_spec,
            encodings: { x: "Phiên", open: "Mở", high: "Cao", low: "Thấp" },
          },
        },
      ],
    }

    render(<SignalDeskPanel view={{ state: "chart", visual: broken }} />)

    expect(await screen.findByText(SIGNAL_DESK_COPY.chartFailed)).toBeDefined()
  })

  it("says so for a part written by a build it does not know", async () => {
    render(<SignalDeskPanel view={{ state: "chart", visual: { ...VISUAL, version: 99 } }} />)

    expect(await screen.findByText(SIGNAL_DESK_COPY.chartFailed)).toBeDefined()
  })

  it("goes back to the skeleton when the part changes", async () => {
    const { rerender } = render(
      <SignalDeskPanel view={{ state: "chart", visual: VISUAL }} />,
    )
    await screen.findByRole("figure")

    rerender(<SignalDeskPanel view={{ state: "working" }} />)

    await waitFor(() => expect(screen.queryByRole("figure")).toBeNull())
    expect(screen.getByRole("status").getAttribute("aria-busy")).toBe("true")
  })
})


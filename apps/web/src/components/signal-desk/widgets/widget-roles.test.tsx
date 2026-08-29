// @vitest-environment jsdom
/**
 * What a widget does with the meaning a frame declares, and what it never says.
 *
 * **The engine names, the widget draws.** A frame may say that a quarter fell or
 * that one bucket is the answer, and the widget's whole job is to paint that. A
 * frame that says nothing is drawn the way it has always been drawn, which is
 * what keeps every artifact written before any of this from changing.
 *
 * **None of it reaches the page in words.** A reader asked about a company. The
 * vocabulary this system uses about itself — what a picture is filed as, which
 * component drew it, which build of it — is plumbing, and a chart that prints
 * any of it has answered a question nobody asked. Colour is never the only
 * carrier either: every one of these numbers is also in the table under the
 * block, in the same order.
 *
 * The chart widgets go through recharts, which measures its container and so
 * draws nothing under jsdom. What is asserted here is therefore what survives
 * that: the words on the page, and the tiles, which are laid out by hand.
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { BarSeriesWidget } from "./bar-series"
import { LineSeriesWidget } from "./line-series"
import { RankedBarsWidget } from "./ranked-bars"
import { ScatterQuadrantWidget } from "./scatter-quadrant"
import { StatTilesWidget } from "./stat-tiles"

afterEach(cleanup)

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 30,
  health: "normal",
  reason: null,
}

const TILES: Frame = {
  kind: "table",
  columns: ["label", "value", "unit"],
  rows: [
    ["Khung giờ đỉnh", "14:15", null],
    ["Tỷ trọng thanh khoản", 18.4, "%"],
    ["Lợi nhuận 12 tháng", -10.8, "%"],
  ],
  unit: null,
  labels: { label: "Chỉ số", value: "Giá trị", unit: "Đơn vị" },
  pointRoles: ["focus", null, "down"],
}

function tiles(frame: Frame) {
  return render(
    <StatTilesWidget
      frame={frame}
      options={{ label: "label", value: "value", unit: "unit" }}
      provenance={PROVENANCE}
    />,
  )
}

/** The colour on one tile's figure, or `""` where it kept the page's ink. */
function inks(container: HTMLElement): string[] {
  return [...container.querySelectorAll("dd span span")]
    .filter((node) => node.className.includes("font-semibold"))
    .map((node) => node.getAttribute("style") ?? "")
}

describe("a tile with a claim on it", () => {
  it("paints the figure the engine named and leaves the rest as page ink", () => {
    const { container } = tiles(TILES)
    const painted = inks(container)

    expect(painted[0]).toContain("--widget-focus")
    expect(painted[1]).toBe("")
    expect(painted[2]).toContain("--widget-down")
  })

  it("keeps the figure legible as text, so the colour is never the whole claim", () => {
    const { container } = tiles(TILES)

    expect(container.textContent).toContain("14:15")
    expect(container.textContent).toContain("Lợi nhuận 12 tháng")
  })

  it("draws a frame that claims nothing exactly as it drew it before", () => {
    const { container } = tiles({ ...TILES, pointRoles: undefined })

    expect(inks(container)).toEqual(["", "", ""])
  })

  it("paints nothing when a frame marked two tiles as the one that matters", () => {
    const { container } = tiles({ ...TILES, pointRoles: ["focus", "focus", null] })

    // Every figure back to page ink: two marks are not two answers.
    expect(inks(container)).toEqual(["", "", ""])
  })
})

describe("a bar chart with a claim on it", () => {
  const frame = (roles?: (string | null)[]): Frame => ({
    kind: "series",
    columns: ["bucket", "share"],
    rows: [
      ["09:15", 0.02],
      ["11:15", 0.02],
      ["14:15", 0.4],
    ],
    unit: null,
    labels: { bucket: "Khung giờ", share: "Tỷ trọng trong phiên" },
    pointRoles: roles,
  })

  function draw(roles?: (string | null)[]) {
    return render(
      <BarSeriesWidget
        frame={frame(roles)}
        options={{ x: "bucket", y: "share", yFormat: "percent" }}
        provenance={PROVENANCE}
      />,
    )
  }

  it("stops claiming it accented a clipped bar once the frame does the naming", () => {
    // The note is about the axis, not about the colour, the moment the colour
    // is somebody else's decision.
    const { container } = draw(["neutral", "neutral", "focus"])

    expect(container.textContent).toContain("Trục dừng ở")
    expect(container.textContent).toContain("bị cắt tại đó")
    expect(container.textContent).not.toContain("tô màu nhấn")
  })

  it("still names its own peak when the frame says nothing", () => {
    const { container } = draw()

    expect(container.textContent).toContain("được tô màu nhấn")
  })

  it("draws the numbers it has when a role is one this build cannot paint", () => {
    const { container } = draw(["category:9", null, null])

    expect(container.textContent).toContain("Trục dừng ở")
  })
})

describe("nothing a reader meets is written in this system's own words", () => {
  //: What this system calls its own parts. None of it is about a company.
  const PLUMBING = [
    "frame",
    "role",
    "widget",
    "store",
    "artifact",
    "kind",
    "version",
    "category:",
    "run_study",
    "get_series",
    "render_signal_desk",
    "stat_tiles",
    "bar_series",
    "ranked_bars",
    "line_series",
    "scatter_quadrant",
    "data_table",
    "intraday_liquidity_profile",
  ]

  const RANKING: Frame = {
    kind: "table",
    columns: ["bucket", "share"],
    rows: [
      ["14:15", 0.4],
      ["09:15", 0.02],
    ],
    unit: null,
    labels: { bucket: "Khung giờ", share: "Tỷ trọng trong phiên" },
    pointRoles: ["focus", null],
  }

  const PATH: Frame = {
    kind: "series",
    columns: ["session", "close", "index"],
    rows: [
      ["2026-08-20", 71000, 1280],
      ["2026-08-21", 71350, 1284],
    ],
    unit: "VND",
    labels: { session: "Phiên", close: "Giá đóng cửa", index: "VN-Index" },
    columnRoles: { close: "up", index: "muted" },
  }

  const CLOUD: Frame = {
    kind: "table",
    columns: ["symbol", "growth_pct", "rel_return_pct"],
    rows: [
      ["STB", 32.5, -15.5],
      ["VCB", 12.0, 4.0],
    ],
    unit: "%",
    labels: {
      symbol: "Mã",
      growth_pct: "Tăng trưởng lợi nhuận so cùng kỳ (%)",
      rel_return_pct: "Lợi suất 20 phiên so VN-Index (%)",
    },
    pointRoles: ["category:1", "category:3"],
  }

  const DRAWINGS = {
    tiles: (
      <StatTilesWidget
        frame={TILES}
        options={{ label: "label", value: "value", unit: "unit" }}
        provenance={PROVENANCE}
      />
    ),
    bars: (
      <BarSeriesWidget
        frame={PATH}
        options={{ x: "session", y: "close", secondary: "index" }}
        provenance={PROVENANCE}
      />
    ),
    ranking: (
      <RankedBarsWidget
        frame={RANKING}
        options={{ label: "bucket", value: "share", valueFormat: "percent" }}
        provenance={PROVENANCE}
      />
    ),
    line: (
      <LineSeriesWidget
        frame={PATH}
        options={{ x: "session", y: "close", secondary: "index" }}
        provenance={PROVENANCE}
      />
    ),
    cloud: (
      <ScatterQuadrantWidget
        frame={CLOUD}
        options={{ label: "symbol", x: "growth_pct", y: "rel_return_pct" }}
        provenance={PROVENANCE}
      />
    ),
  }

  it.each(Object.entries(DRAWINGS))(
    "prints none of it: %s",
    (_name, drawing) => {
      const { container } = render(drawing)
      const text = (container.textContent ?? "").toLowerCase()

      for (const word of PLUMBING) {
        expect(text).not.toContain(word)
      }
    },
  )
})

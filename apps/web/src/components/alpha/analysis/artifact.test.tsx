// @vitest-environment jsdom
/**
 * How an Analysis reads, in both treatments.
 *
 * Every claim here is one the artifact would be dishonest without: the four
 * axes in one order whatever the payload said, a refused figure visible with
 * its reason in both treatments rather than deferred to the expanded one, a
 * `Signal Issue` code never on screen, and the price-zone band as the only
 * inline graphic.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { buildArtifact, type AnalysisPayload } from "@/lib/alpha-desk/analysis"
import type { AnalysisDetail } from "@/lib/alpha"
import { AnalysisArtifact } from "./analysis-artifact"
import { Briefing } from "./briefing"
import { RISK_NOTICE_TEXT } from "./risk-notice"

vi.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => mobile.value }))

const mobile = { value: false }

afterEach(() => {
  cleanup()
  mobile.value = false
})

function figure(overrides: Record<string, unknown> = {}) {
  return {
    fieldId: "indicator_pack.rsi_14",
    label: "RSI (14)",
    value: 58.2,
    unit: "index_0_100",
    kind: "indicator",
    source: "computed",
    interpretation: "Where the symbol sits between oversold and overbought.",
    health: "ok",
    reasonCode: null,
    reason: null,
    asOf: "2026-08-12",
    sessionsUsed: 250,
    windowDays: 14,
    extras: {},
    ...overrides,
  }
}

const PAYLOAD = {
  audit: {
    schemaVersion: 1,
    fieldProfileVersion: "v1",
    promptVersion: "analysis@1",
    model: "batch-model",
    route: "https://llm.example/v1",
    generatedAt: "2026-08-12T18:00:00+00:00",
    inputFingerprint: "abc123",
  },
  evidence: {
    schemaVersion: 1,
    fieldProfileVersion: "v1",
    symbol: "FPT",
    companyName: "FPT Corporation",
    exchange: "HOSE",
    industry: "other",
    tradingDay: "2026-08-12",
    priceZone: figure({
      fieldId: "price_zone.ordinary_range_pct",
      label: "Ordinary daily range",
      value: 2.1,
      unit: "percent",
      extras: {
        anchor_close: 100_000,
        lower_price: 97_900,
        upper_price: 102_100,
        anchor_session: "2026-08-12",
      },
    }),
    // Deliberately out of template order, and money_flow before fundamental.
    sections: [
      { axis: "news", health: "refused", figures: [] },
      {
        axis: "money_flow",
        health: "degraded",
        figures: [
          figure({
            fieldId: "liquidity_profile.adtv_vnd",
            label: "ADTV",
            unit: "vnd",
            value: 320_000_000_000,
            health: "degraded",
            reasonCode: "volume_basis_break",
            reason: "An English sentence written for the model.",
          }),
        ],
      },
      { axis: "technical", health: "ok", figures: [figure()] },
      {
        axis: "fundamental",
        health: "refused",
        figures: [
          figure({
            fieldId: "factor_percentiles.roe_percentile",
            label: "ROE percentile",
            unit: "percentile",
            value: null,
            health: "refused",
            reasonCode: "insufficient_history",
            reason: "An English sentence written for the model.",
            asOf: null,
          }),
        ],
      },
    ],
    windowHealth: { windowDays: 20, sessionsUsed: 20 },
  },
  judgment: {
    verdictLine: "Vùng giá ổn định, dòng tiền chưa xác nhận.",
    thesis: "Luận điểm bằng tiếng Việt về mã này.",
    leadAxis: "money_flow",
    axes: [
      {
        axis: "technical",
        emphasis: "support",
        emphasisReason: "Đà giá chỉ để đối chiếu.",
        read: "Đà giá còn giữ.",
      },
      {
        axis: "fundamental",
        emphasis: "context",
        emphasisReason: "Chưa đủ lịch sử để xếp phân vị.",
        read: "Chưa đọc được nền cơ bản.",
      },
      {
        axis: "money_flow",
        emphasis: "lead",
        emphasisReason: "Trục duy nhất vượt ngưỡng hiệu chuẩn hôm nay.",
        read: "Dòng tiền là trục dẫn dắt phiên này.",
      },
      {
        axis: "news",
        emphasis: "context",
        emphasisReason: "Chưa có nguồn tin nào được duyệt.",
        read: "Chưa có tin.",
      },
    ],
  },
  citedFieldIds: [
    "indicator_pack.rsi_14",
    "liquidity_profile.adtv_vnd",
    "factor_percentiles.roe_percentile",
  ],
} as unknown as AnalysisPayload

function detail(payload: unknown = PAYLOAD): AnalysisDetail {
  return {
    symbol: "FPT",
    trading_day: "2026-08-12",
    verdict: "hold",
    schema_version: 1,
    created_at: "2026-08-12T18:00:00+00:00",
    payload: payload as Record<string, unknown>,
  }
}

function artifact(payload?: unknown) {
  return buildArtifact(detail(payload))
}

const TAB_ORDER = ["Technical", "Fundamental", "Money flow", "News"]

describe("the inline treatment", () => {
  it("pins the verdict and shows the four axes as tabs in template order", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    expect(screen.getByText("hold")).toBeInTheDocument()
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(TAB_ORDER)
  })

  it("opens on the lead axis", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    const selected = screen.getAllByRole("tab", { selected: true })
    expect(selected).toHaveLength(1)
    expect(selected[0]).toHaveTextContent("Money flow")
  })

  it("shows the citation count rather than the ids", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    // Two, not three: the refused ROE percentile cannot support the verdict.
    expect(screen.getByText(/Citations 2/)).toBeInTheDocument()
    expect(screen.queryByText("indicator_pack.rsi_14")).toBeNull()
  })

  it("draws the price-zone band and no other graphic", () => {
    const { container } = render(<AnalysisArtifact artifact={artifact()} />)

    // Lucide's control icons are SVG too, and they are chrome rather than a
    // picture of data — the count that matters is graphics, not elements.
    const graphics = container.querySelectorAll("svg:not([class*='lucide'])")
    expect(graphics).toHaveLength(1)
    expect(screen.getByText("Ordinary daily range")).toBeInTheDocument()
  })

  it("stays bounded so ten of them are still scrollable", () => {
    const { container } = render(<AnalysisArtifact artifact={artifact()} />)

    expect(container.querySelector("[class*='max-h-']")).not.toBeNull()
  })

  it("gives the lead axis more of that height than the others", () => {
    // The other half of what emphasis buys: which tab opens, and how much space
    // an axis gets. Never a reordering.
    render(<AnalysisArtifact artifact={artifact()} />)

    const lead = screen.getByRole("tabpanel").firstElementChild
    expect(lead?.className).toContain("max-h-96")

    fireEvent.focus(screen.getByRole("tab", { name: "Technical" }))
    expect(screen.getByRole("tabpanel").firstElementChild?.className).toContain(
      "max-h-64",
    )
  })

  it("carries the Risk Notice without being asked", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    const notice = screen.getByRole("note", { name: "Risk notice" })
    expect(notice).toHaveTextContent(RISK_NOTICE_TEXT)
  })

  it("deep-links to the screen that owns every other chart", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    expect(screen.getByRole("link", { name: /deep dive/i })).toHaveAttribute(
      "href",
      "/analytics/deep-dive?symbol=FPT",
    )
  })

  it("keeps a refused figure visible with its reason, not behind a tooltip", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    // Radix activates a tab on focus, which is also how a keyboard reader
    // reaches it.
    fireEvent.focus(screen.getByRole("tab", { name: "Fundamental" }))
    const panel = screen.getByRole("tabpanel")

    expect(within(panel).getByText("ROE percentile")).toBeInTheDocument()
    // A dash where the value would be, and another where its `asOf` would be:
    // a refused figure has no reading for a date to belong to either.
    expect(within(panel).getAllByText("—")).toHaveLength(2)
    expect(
      within(panel).getByText(/Chưa đủ số phiên tối thiểu/),
    ).toBeInTheDocument()
    expect(within(panel).getByText(/Không dùng được để chống đỡ/)).toBeInTheDocument()
  })

  it("shows every figure with its unit, kind, source, interpretation and stamp", () => {
    render(<AnalysisArtifact artifact={artifact()} />)

    const panel = screen.getByRole("tabpanel")
    expect(within(panel).getByText("ADTV")).toBeInTheDocument()
    expect(within(panel).getByText("đồng")).toBeInTheDocument()
    expect(within(panel).getByText("indicator")).toBeInTheDocument()
    expect(within(panel).getByText("· computed")).toBeInTheDocument()
    expect(within(panel).getByText(/oversold and overbought/)).toBeInTheDocument()
    expect(within(panel).getByText(/as of/)).toBeInTheDocument()
    // The figure's own health and its section's, which is the honest reading
    // of a degraded figure sitting in a section that has one.
    expect(within(panel).getAllByText("degraded")).toHaveLength(2)
  })

  it("never renders a Signal Issue code verbatim", () => {
    const { container } = render(<AnalysisArtifact artifact={artifact()} />)

    for (const tab of TAB_ORDER) {
      fireEvent.focus(screen.getByRole("tab", { name: tab }))
      expect(container.textContent).not.toContain("insufficient_history")
      expect(container.textContent).not.toContain("volume_basis_break")
    }
  })
})

describe("the expanded treatment", () => {
  it("gives the briefing in place on a wide viewport", () => {
    mobile.value = false
    render(<AnalysisArtifact artifact={artifact()} />)

    fireEvent.click(screen.getByRole("button", { name: /Expand/ }))

    expect(screen.queryByRole("dialog")).toBeNull()
    expect(screen.getByText("Luận điểm bằng tiếng Việt về mã này.")).toBeInTheDocument()
    expect(screen.queryAllByRole("tab")).toHaveLength(0)
  })

  it("is a modal overlay on a narrow viewport", () => {
    mobile.value = true
    render(<AnalysisArtifact artifact={artifact()} />)

    fireEvent.click(screen.getByRole("button", { name: /Expand/ }))

    const dialog = screen.getByRole("dialog")
    expect(within(dialog).getByText(/Luận điểm bằng tiếng Việt/)).toBeInTheDocument()
    mobile.value = false
  })

  it("shows all four axes at once, in template order", () => {
    render(<Briefing artifact={artifact()} />)

    const headings = screen.getAllByRole("heading", { level: 4 })
    expect(headings.map((heading) => heading.textContent)).toEqual(TAB_ORDER)
  })

  it("exposes the registered field ids the verdict rests on", () => {
    render(<Briefing artifact={artifact()} />)

    const ids = screen.getByLabelText("Registered field ids")

    expect(within(ids).getByText("indicator_pack.rsi_14")).toBeInTheDocument()
    expect(within(ids).getByText("liquidity_profile.adtv_vnd")).toBeInTheDocument()
    // Refused, so it is not a citation in either treatment. The field id still
    // appears beside its own figure — what it may not do is stand as support.
    expect(within(ids).queryByText("factor_percentiles.roe_percentile")).toBeNull()
  })

  it("gives the lead axis the full width", () => {
    render(<Briefing artifact={artifact()} />)

    const lead = screen.getByRole("region", { name: "Money flow" })
    expect(lead.className).toContain("sm:col-span-2")
    expect(
      screen.getByRole("region", { name: "Technical" }).className,
    ).not.toContain("col-span-2")
  })

  it("shows the window the price zone was read over", () => {
    render(<Briefing artifact={artifact()} />)

    expect(screen.getByText("Window health")).toBeInTheDocument()
    expect(screen.getByText(/20 \/ 20 sessions/)).toBeInTheDocument()
  })

  it("carries the Risk Notice here too", () => {
    render(<Briefing artifact={artifact()} />)

    expect(screen.getByRole("note", { name: "Risk notice" })).toHaveTextContent(
      RISK_NOTICE_TEXT,
    )
  })

  it("keeps the honesty states visible here too", () => {
    render(<Briefing artifact={artifact()} />)

    expect(screen.getByText(/Chưa đủ số phiên tối thiểu/)).toBeInTheDocument()
    expect(
      screen.getByText(/Khối lượng qua ngày thay đổi số cổ phiếu/),
    ).toBeInTheDocument()
  })

  it("deep-links every other chart to the screen that owns it", () => {
    render(<Briefing artifact={artifact()} />)

    expect(screen.getByRole("link", { name: /deep dive/i })).toHaveAttribute(
      "href",
      "/analytics/deep-dive?symbol=FPT",
    )
  })
})

describe("the language split", () => {
  it("keeps chrome and field labels English while narration is Vietnamese", () => {
    render(<Briefing artifact={artifact()} />)

    for (const label of TAB_ORDER) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.getByText("Registered field ids")).toBeInTheDocument()
    expect(screen.getByText(/Dòng tiền là trục dẫn dắt/)).toBeInTheDocument()
  })
})

describe("several schema versions at once", () => {
  it("renders a payload from an older template", () => {
    const older = {
      evidence: {
        symbol: "FPT",
        tradingDay: "2026-08-12",
        sections: [{ axis: "technical", health: "ok", figures: [figure()] }],
      },
      citedFieldIds: ["indicator_pack.rsi_14"],
    }

    render(
      <AnalysisArtifact
        artifact={buildArtifact({ ...detail(older), schema_version: 0 })}
      />,
    )

    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(TAB_ORDER)
    expect(screen.getByText(/template v0/)).toBeInTheDocument()
    // No price zone in that payload, so the band says so rather than drawing one.
    expect(screen.getByText(/Chưa dựng được vùng giá/)).toBeInTheDocument()
  })
})

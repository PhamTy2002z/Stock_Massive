import { describe, expect, it } from "vitest"

import {
  AXIS_ORDER,
  buildArtifact,
  priceZoneBand,
  type AnalysisPayload,
  type PayloadFigure,
} from "./analysis"

function figure(overrides: Partial<PayloadFigure> = {}): PayloadFigure {
  return {
    fieldId: "indicator_pack.rsi_14",
    label: "RSI (14)",
    value: 58.2,
    unit: "index",
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

function payload(overrides: Partial<AnalysisPayload> = {}): AnalysisPayload {
  return {
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
      sections: [
        { axis: "news", health: "refused", figures: [] },
        { axis: "technical", health: "ok", figures: [figure()] },
        {
          axis: "money_flow",
          health: "degraded",
          figures: [
            figure({
              fieldId: "liquidity_profile.adtv_vnd",
              label: "ADTV",
              health: "degraded",
              reasonCode: "volume_basis_break",
              reason: "An English sentence written for the model.",
            }),
          ],
        },
        {
          axis: "fundamental",
          health: "refused",
          figures: [
            figure({
              fieldId: "factor_percentiles.roe_percentile",
              label: "ROE percentile",
              value: null,
              health: "refused",
              reasonCode: "fundamental_not_stored",
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
      thesis: "Luận điểm bằng tiếng Việt.",
      leadAxis: "technical",
      axes: [
        {
          axis: "technical",
          emphasis: "lead",
          emphasisReason: "Trục duy nhất vượt ngưỡng hiệu chuẩn.",
          read: "Đà giá còn giữ.",
        },
        {
          axis: "fundamental",
          emphasis: "context",
          emphasisReason: "Không có báo cáo quý nào để đọc.",
          read: "Chưa đọc được.",
        },
        {
          axis: "money_flow",
          emphasis: "support",
          emphasisReason: "Thanh khoản đủ để đối chiếu.",
          read: "Dòng tiền đi ngang.",
        },
        {
          axis: "news",
          emphasis: "context",
          emphasisReason: "Chưa có nguồn tin nào được duyệt.",
          read: "Chưa có tin.",
        },
      ],
    },
    citedFieldIds: ["indicator_pack.rsi_14", "price_zone.ordinary_range_pct"],
    ...overrides,
  }
}

function detail(overrides: Partial<AnalysisPayload> = {}) {
  return {
    symbol: "FPT",
    trading_day: "2026-08-12",
    verdict: "hold",
    schema_version: 1,
    created_at: "2026-08-12T18:00:00+00:00",
    payload: payload(overrides) as unknown as Record<string, unknown>,
  }
}

describe("the fixed template", () => {
  it("orders the axes technical → fundamental → money_flow → news whatever the payload says", () => {
    const artifact = buildArtifact(detail())

    expect(artifact.axes.map((axis) => axis.axis)).toEqual([...AXIS_ORDER])
  })

  it("carries all four axes even when the payload is missing one", () => {
    const base = payload()
    const artifact = buildArtifact(
      detail({
        evidence: {
          ...base.evidence,
          sections: base.evidence.sections.filter(
            (section) => section.axis !== "news",
          ),
        },
      }),
    )

    const news = artifact.axes.find((axis) => axis.axis === "news")
    expect(news).toBeDefined()
    expect(news?.health).toBe("refused")
    expect(news?.figures).toEqual([])
  })

  it("ignores a section the payload names that is not one of the four", () => {
    const base = payload()
    const artifact = buildArtifact(
      detail({
        evidence: {
          ...base.evidence,
          sections: [
            ...base.evidence.sections,
            { axis: "sentiment", health: "ok", figures: [figure()] },
          ] as AnalysisPayload["evidence"]["sections"],
        },
      }),
    )

    expect(artifact.axes).toHaveLength(AXIS_ORDER.length)
    expect(artifact.axes.map((axis) => axis.axis)).toEqual([...AXIS_ORDER])
  })
})

describe("exactly one lead", () => {
  it("takes the lead the model chose", () => {
    const artifact = buildArtifact(detail())

    expect(artifact.leadAxis).toBe("technical")
    expect(artifact.axes.filter((axis) => axis.emphasis === "lead")).toHaveLength(1)
  })

  it("demotes every extra lead a payload carries", () => {
    const base = payload()
    const artifact = buildArtifact(
      detail({
        judgment: {
          ...base.judgment,
          leadAxis: "money_flow",
          axes: base.judgment.axes.map((axis) => ({ ...axis, emphasis: "lead" })),
        },
      }),
    )

    expect(artifact.leadAxis).toBe("money_flow")
    expect(artifact.axes.filter((axis) => axis.emphasis === "lead")).toHaveLength(1)
    expect(
      artifact.axes.filter((axis) => axis.axis !== "money_flow").map((a) => a.emphasis),
    ).toEqual(["support", "support", "support"])
  })

  it("names a lead when the payload names none", () => {
    const base = payload()
    const artifact = buildArtifact(
      detail({
        judgment: {
          ...base.judgment,
          leadAxis: "nonsense" as unknown as AnalysisPayload["judgment"]["leadAxis"],
          axes: base.judgment.axes.map((axis) => ({
            ...axis,
            emphasis: "support" as const,
          })),
        },
      }),
    )

    expect(artifact.axes.filter((axis) => axis.emphasis === "lead")).toHaveLength(1)
    expect(artifact.leadAxis).toBe(artifact.axes[0].axis)
  })
})

describe("honesty states", () => {
  it("keeps a refused figure with a null value and a Vietnamese reason", () => {
    const artifact = buildArtifact(detail())
    const fundamental = artifact.axes.find((axis) => axis.axis === "fundamental")!
    const [roe] = fundamental.figures

    expect(roe.value).toBeNull()
    expect(roe.health).toBe("refused")
    expect(roe.reason).toBe("Chưa có báo cáo quý nào được lưu tính đến ngày này")
  })

  it("translates the code rather than passing the payload's English sentence through", () => {
    const artifact = buildArtifact(detail())
    const moneyFlow = artifact.axes.find((axis) => axis.axis === "money_flow")!

    expect(moneyFlow.figures[0].reason).toBe(
      "Khối lượng qua ngày thay đổi số cổ phiếu không cùng cơ sở so sánh",
    )
  })

  it("never lets a refused field support the verdict", () => {
    const base = payload()
    const artifact = buildArtifact(
      detail({
        citedFieldIds: [
          "indicator_pack.rsi_14",
          "factor_percentiles.roe_percentile",
        ],
        judgment: base.judgment,
      }),
    )

    expect(artifact.citedFieldIds).toEqual(["indicator_pack.rsi_14"])
    expect(artifact.citationCount).toBe(1)

    const fundamental = artifact.axes.find((axis) => axis.axis === "fundamental")!
    expect(fundamental.figures[0].cited).toBe(false)
  })

  it("reports a figure with no reason code as having no reason at all", () => {
    const artifact = buildArtifact(detail())
    const technical = artifact.axes.find((axis) => axis.axis === "technical")!

    expect(technical.figures[0].reason).toBeNull()
  })
})

describe("older schema versions still render", () => {
  it("renders a payload carrying no judgment at all", () => {
    const artifact = buildArtifact(
      detail({ judgment: undefined as unknown as AnalysisPayload["judgment"] }),
    )

    expect(artifact.verdictLine).toBeNull()
    expect(artifact.thesis).toBeNull()
    expect(artifact.axes).toHaveLength(AXIS_ORDER.length)
    expect(artifact.axes.filter((axis) => axis.emphasis === "lead")).toHaveLength(1)
  })

  it("renders a payload whose evidence is missing entirely", () => {
    const artifact = buildArtifact(
      detail({ evidence: undefined as unknown as AnalysisPayload["evidence"] }),
    )

    expect(artifact.priceZone).toBeNull()
    expect(artifact.axes.every((axis) => axis.health === "refused")).toBe(true)
    expect(artifact.symbol).toBe("FPT")
    expect(artifact.tradingDay).toBe("2026-08-12")
  })

  it("keeps the row's own schema version rather than assuming the newest", () => {
    const artifact = buildArtifact({ ...detail(), schema_version: 0 })

    expect(artifact.schemaVersion).toBe(0)
  })
})

describe("the price-zone band", () => {
  it("reads the two prices and the anchor off the figure's extras", () => {
    const artifact = buildArtifact(detail())
    const band = priceZoneBand(artifact.priceZone)

    expect(band).toEqual({
      lower: 97_900,
      upper: 102_100,
      anchor: 100_000,
      halfWidthPct: 2.1,
    })
  })

  it("has no band to draw when the zone was refused", () => {
    const base = payload()
    const artifact = buildArtifact(
      detail({
        evidence: {
          ...base.evidence,
          priceZone: figure({
            fieldId: "price_zone.ordinary_range_pct",
            value: null,
            health: "refused",
            reasonCode: "insufficient_history",
            extras: {},
          }),
        },
      }),
    )

    expect(artifact.priceZone?.health).toBe("refused")
    expect(priceZoneBand(artifact.priceZone)).toBeNull()
  })
})

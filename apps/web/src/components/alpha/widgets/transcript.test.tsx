// @vitest-environment jsdom
/**
 * What the transcript does with a persisted Widget spec (#91).
 *
 * The second half of ADR-0012's double validation. Everything here is about
 * what happens when the spec and the build disagree — an unknown version, a
 * malformed descriptor, a slice that will not resolve — and the answer is
 * always the same: the text answer survives, and nothing throws.
 */

import * as React from "react"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { crossSymbol, periods, quarterlySpec, ranking, spec } from "./fixtures"
import { MAX_WIDGETS_PER_ANSWER, MessageWidgets } from "./message-widgets"
import { lookupWidget, supportedWidgets } from "./registry"
import { parseWidgetRefusals, parseWidgetSpec, parseWidgetSpecs } from "./spec"
import type { WidgetData, WidgetSpec } from "./types"
import { WidgetSlot } from "./widget-slot"

afterEach(cleanup)

/** The transcript around a Widget, so "the text survives" is testable. */
function Answer({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div>
      <ul>
        <li>FPT dẫn đầu động lượng trong nhóm được so sánh.</li>
        <li>VCB ở giữa nhóm.</li>
        <li>HPG yếu nhất.</li>
      </ul>
      {children}
    </div>
  )
}

function resolvesTo(data: WidgetData) {
  return vi.fn(async () => data)
}

const TEXT = /FPT dẫn đầu động lượng/

describe("validating the persisted spec before the registry is asked", () => {
  it("accepts a spec this build ships", () => {
    const parsed = parseWidgetSpec(spec())

    expect(parsed).not.toBeNull()
    expect(lookupWidget(parsed as WidgetSpec)).toBeDefined()
  })

  it("accepts the periods spec the quarterly table is persisted as", () => {
    // Its name is in `WIDGET_NAMES` and its descriptor kind is a string, which
    // is all the parser is entitled to check — the pairing of `periods` data to
    // the table component is the slot's, one step later.
    const parsed = parseWidgetSpec(quarterlySpec())

    expect(parsed?.name).toBe("quarterly_financials")
    expect(lookupWidget(parsed as WidgetSpec)?.kind).toBe("periods")
  })

  it.each([
    ["an unknown name", { name: "candlestick" }],
    ["a non-integer version", { version: 1.5 }],
    ["a missing data date", { as_of: "" }],
    ["a descriptor that is not an object", { descriptor: "cross_symbol" }],
    ["a descriptor with no kind", { descriptor: { field: "x" } }],
    ["fields that are not strings", { fields: [1, 2] }],
  ])("rejects %s", (_case, override) => {
    expect(parseWidgetSpec({ ...spec(), ...override })).toBeNull()
  })

  it("misses an unsupported version rather than guessing at it", () => {
    const future = parseWidgetSpec(spec({ version: 99 }))

    expect(future).not.toBeNull()
    expect(lookupWidget(future as WidgetSpec)).toBeUndefined()
    // The registry is keyed on the pair, so version 1 keeps working while a
    // message written for version 99 simply is not drawn.
    expect(supportedWidgets()).toEqual([
      "metric_comparison@1",
      "metric_trend@1",
      "quarterly_financials@1",
      "ranked_symbols@1",
      "relative_position@1",
    ])
  })

  it("keeps only the specs it understands out of a mixed message", () => {
    const kept = parseWidgetSpecs([spec(), { name: "candlestick" }, null, 7])

    expect(kept).toHaveLength(1)
  })
})

describe("the slot", () => {
  it("holds its position while the data loads, then swaps", async () => {
    render(
      <Answer>
        <WidgetSlot spec={spec()} resolve={resolvesTo(crossSymbol())} />
      </Answer>
    )

    // Text is already there; the picture is not, and its placeholder is.
    expect(screen.getByText(TEXT)).toBeInTheDocument()
    expect(screen.getByTestId("widget-placeholder")).toBeInTheDocument()

    expect(await screen.findByRole("figure")).toBeInTheDocument()
    expect(screen.queryByTestId("widget-placeholder")).not.toBeInTheDocument()
    expect(screen.getByText(TEXT)).toBeInTheDocument()
  })

  it("draws a periods slice as the table the registry pairs it with", async () => {
    render(
      <Answer>
        <WidgetSlot spec={quarterlySpec()} resolve={resolvesTo(periods())} />
      </Answer>
    )

    expect(await screen.findByRole("figure")).toBeInTheDocument()
    // The table is the Widget here, so it is present without a disclosure being
    // opened first — eight quarters and a header.
    expect(screen.getAllByRole("row")).toHaveLength(9)
    expect(screen.getByText(TEXT)).toBeInTheDocument()
  })

  it("leaves the answer intact and throws nothing when the component is missing", () => {
    render(
      <Answer>
        <WidgetSlot spec={spec({ version: 99 })} resolve={resolvesTo(crossSymbol())} />
      </Answer>
    )

    expect(screen.getByText(TEXT)).toBeInTheDocument()
    expect(screen.queryByRole("figure")).not.toBeInTheDocument()
    expect(screen.queryByTestId("widget-placeholder")).not.toBeInTheDocument()
  })

  it("leaves the answer intact when the spec is malformed", () => {
    render(
      <Answer>
        <WidgetSlot spec={{ nonsense: true }} resolve={resolvesTo(crossSymbol())} />
      </Answer>
    )

    expect(screen.getByText(TEXT)).toBeInTheDocument()
    expect(screen.queryByRole("figure")).not.toBeInTheDocument()
  })

  it("refuses to draw data whose kind does not match the component", async () => {
    render(
      <Answer>
        {/* A ranking resolved under a comparison spec: the two disagree, and
            drawing it anyway is how a ranking ends up as a bar comparison. */}
        <WidgetSlot spec={spec()} resolve={resolvesTo(ranking())} />
      </Answer>
    )

    await waitFor(() =>
      expect(screen.queryByTestId("widget-placeholder")).not.toBeInTheDocument()
    )
    expect(screen.queryByRole("figure")).not.toBeInTheDocument()
    expect(screen.getByText(TEXT)).toBeInTheDocument()
  })

  it("disappears without noise when the agent offered it and it failed", async () => {
    const failing = vi.fn(async () => {
      throw new Error("upstream is gone")
    })
    const { container } = render(
      <Answer>
        <WidgetSlot spec={spec({ requested: false })} resolve={failing} />
      </Answer>
    )

    await waitFor(() =>
      expect(screen.queryByTestId("widget-placeholder")).not.toBeInTheDocument()
    )
    expect(screen.queryByRole("status")).not.toBeInTheDocument()
    expect(container.querySelector("figure")).toBeNull()
    expect(screen.getByText(TEXT)).toBeInTheDocument()
  })

  it("says so, with a retry, when the user asked for it and it failed", async () => {
    let attempts = 0
    const flaky = vi.fn(async () => {
      attempts += 1
      if (attempts === 1) throw new Error("upstream blinked")
      return crossSymbol()
    })
    render(
      <Answer>
        <WidgetSlot spec={spec({ requested: true })} resolve={flaky} />
      </Answer>
    )

    expect(
      await screen.findByText("Không hiển thị được biểu đồ này.")
    ).toBeInTheDocument()
    expect(screen.getByText(TEXT)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }))

    expect(await screen.findByRole("figure")).toBeInTheDocument()
    expect(attempts).toBe(2)
  })

  it("resolves once even when the caller rebuilds its resolver every render", async () => {
    const calls = { count: 0 }
    function Host() {
      const [, bump] = React.useState(0)
      React.useEffect(() => {
        // A parent that re-renders for its own reasons — a streaming
        // transcript does this constantly.
        bump(1)
      }, [])
      // Built inline, which is the natural way to write it. Keyed on the
      // function's identity, this would refetch on its own result forever.
      const resolve = async (): Promise<WidgetData> => {
        calls.count += 1
        return crossSymbol()
      }
      return <WidgetSlot spec={spec()} resolve={resolve} />
    }
    render(<Host />)

    await screen.findByRole("figure")
    await waitFor(() => expect(calls.count).toBe(1))
  })

  it("resolves the spec's own descriptor, so a reopened Thread is a record", async () => {
    const resolve = resolvesTo(crossSymbol({ as_of: "2025-01-06" }))
    render(
      <WidgetSlot
        spec={spec({ as_of: "2025-01-06", descriptor_id: "old-slice" })}
        resolve={resolve}
      />
    )

    await screen.findByRole("figure")

    // The slot hands the resolver the persisted spec and nothing of its own,
    // so there is no parameter through which today could be asked for.
    expect(resolve).toHaveBeenCalledWith(
      expect.objectContaining({ descriptor_id: "old-slice", as_of: "2025-01-06" })
    )
    expect(screen.getByText("Dữ liệu ngày 6/1/2025")).toBeInTheDocument()
  })
})

describe("the answer's Widgets", () => {
  it("renders every Widget the server admitted, up to the ceiling it allows", async () => {
    // Three per answer, and a fourth only where the user asked for more, is
    // decided by `apps/api` before anything is persisted — it is the only side
    // holding the user's text. A message carrying four carries four because the
    // user asked; the transcript does not re-litigate that, which is why the
    // backstop below sits at four rather than at the default of three.
    render(
      <MessageWidgets
        messageId={1}
        widgets={[
          spec(),
          spec({ descriptor_id: "second" }),
          spec({ descriptor_id: "third" }),
          spec({ descriptor_id: "fourth" }),
        ]}
        resolve={resolvesTo(crossSymbol())}
      />
    )

    await waitFor(() => expect(screen.getAllByRole("figure")).toHaveLength(4))
  })

  it("bounds an absurd message rather than spraying the transcript", async () => {
    render(
      <MessageWidgets
        messageId={1}
        widgets={Array.from({ length: 9 }, (_unused, index) =>
          spec({ descriptor_id: `slice-${index}` })
        )}
        resolve={resolvesTo(crossSymbol())}
      />
    )

    await screen.findAllByRole("figure")
    expect(screen.getAllByRole("figure")).toHaveLength(MAX_WIDGETS_PER_ANSWER)
    expect(MAX_WIDGETS_PER_ANSWER).toBe(4)
  })

  it("offers the existing screen when the chart is one Stock 360 owns", () => {
    render(
      <MessageWidgets
        messageId={1}
        widgets={[]}
        refusals={[
          { code: "owned_by_stock_360", deep_link: "/analytics/deep-dive?symbol=FPT" },
        ]}
        resolve={resolvesTo(crossSymbol())}
      />
    )

    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/analytics/deep-dive?symbol=FPT"
    )
  })

  it("ignores a refusal pointing anywhere but at this app", () => {
    expect(
      parseWidgetRefusals([
        { code: "owned_by_stock_360", deep_link: "https://elsewhere.example/x" },
        { code: "unknown_widget", deep_link: null },
      ])
    ).toEqual([])
  })

  it("renders nothing at all when there is nothing to render", () => {
    const { container } = render(
      <MessageWidgets messageId={1} widgets={[]} resolve={resolvesTo(crossSymbol())} />
    )

    expect(container).toBeEmptyDOMElement()
  })
})

describe("expand", () => {
  it("opens the same fixed data full-screen, with its date and a calculation disclosure", async () => {
    render(
      <MessageWidgets
        messageId={1}
        widgets={[spec()]}
        resolve={resolvesTo(crossSymbol())}
      />
    )
    fireEvent.click(await screen.findByRole("button", { name: "Mở rộng" }))

    const dialog = await screen.findByRole("dialog")
    expect(dialog).toHaveTextContent("Dữ liệu ngày 14/8/2026")
    expect(dialog).toHaveTextContent("Xem cách tính")
    // The expanded view opens with its table already showing — that is what
    // makes it the readable form rather than a bigger picture.
    expect(screen.getAllByRole("table").length).toBeGreaterThan(0)
    expect(screen.getByText("d3adb33fd3adb33fd3adb33f")).toBeInTheDocument()
  })
})

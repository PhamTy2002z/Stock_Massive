// @vitest-environment jsdom
/**
 * The caption over a picture, and the two things it refuses to become.
 *
 * It refuses to become a paragraph: whatever the run has to say about itself,
 * the line above the chart stays one line. And it refuses to become a log: a
 * reason written for whoever wrote the Study reaches the reader in Vietnamese
 * or does not reach them at all.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Provenance } from "@/lib/alpha-desk/types"
import { SIGNAL_ISSUE_SENTENCES } from "@/lib/signal-issues"

import { ProvenanceStrip, readableReason } from "./provenance-strip"

afterEach(cleanup)

function provenance(overrides: Partial<Provenance> = {}): Provenance {
  return {
    source: "vnstock",
    asOf: "2026-08-28T09:00:00+07:00",
    sessionsUsed: 21,
    health: "degraded",
    reason: null,
    ...overrides,
  }
}

describe("what the strip says", () => {
  it("gives the day, the window and how whole it is", () => {
    render(<ProvenanceStrip provenance={provenance()} />)

    expect(screen.getByText(/dữ liệu 28\/08\/2026/)).toBeInTheDocument()
    expect(screen.getByText("21 phiên")).toBeInTheDocument()
    expect(screen.getByText("thiếu một phần")).toBeInTheDocument()
  })

  it("does not name the provider or the layer the numbers came out of", () => {
    const { container } = render(<ProvenanceStrip provenance={provenance()} />)

    expect(container.textContent).not.toContain("vnstock")
    expect(container.textContent).not.toContain("store")
  })
})

describe("the reason behind a thin window", () => {
  it("drops an internal sentence rather than printing it at the reader", () => {
    const { container } = render(
      <ProvenanceStrip
        provenance={provenance({ reason: "store holds 21 of 30 sessions" })}
      />,
    )

    expect(container.textContent).not.toContain("store holds")
    // The fact itself is not lost: the health word already carries it.
    expect(screen.getByText("thiếu một phần")).toBeInTheDocument()
  })

  it("shows a coded reason in the words the rest of the product uses", () => {
    render(<ProvenanceStrip provenance={provenance({ reason: "insufficient_sessions" })} />)

    expect(screen.getByText(SIGNAL_ISSUE_SENTENCES.insufficient_sessions)).toBeInTheDocument()
  })

  it("is all or nothing, so half a translation never reaches the line", () => {
    expect(readableReason("insufficient_sessions; store holds 21 of 30 sessions")).toBeNull()
    expect(readableReason("insufficient_sessions; stale_reference_reading")).toBe(
      `${SIGNAL_ISSUE_SENTENCES.insufficient_sessions} · ${SIGNAL_ISSUE_SENTENCES.stale_reference_reading}`,
    )
    expect(readableReason("Có báo cáo quý II/2026 cho 1.124/1.523 mã")).toBe(
      "Có báo cáo quý II/2026 cho 1.124/1.523 mã",
    )
    expect(readableReason("store holds 21 of 30 sessions")).toBeNull()
    expect(readableReason("dislocation_rank tính trên 300 mã")).toBeNull()
    expect(readableReason(null)).toBeNull()
    expect(readableReason("  ")).toBeNull()
  })

  it("stays on one line however long the reason is", () => {
    const { container } = render(
      <ProvenanceStrip provenance={provenance({ reason: "insufficient_sessions" })} />,
    )

    const line = container.querySelector("p")
    expect(line?.className).toContain("whitespace-nowrap")
    expect(line?.className).not.toContain("flex-wrap")
    expect(
      screen.getByText(SIGNAL_ISSUE_SENTENCES.insufficient_sessions).className,
    ).toContain("truncate")
  })
})

describe("how the numbers were arrived at", () => {
  const notes = ["Khối lượng gộp theo khung 15 phút", "Bỏ phiên có nghỉ giữa giờ"]

  it("is folded away until the reader asks", () => {
    render(<ProvenanceStrip provenance={provenance({ methodNotes: notes })} />)

    expect(screen.getByText("Cách tính")).toBeInTheDocument()
    expect(screen.queryByText(notes[0])).toBeNull()
  })

  it("opens on the disclosure", () => {
    render(<ProvenanceStrip provenance={provenance({ methodNotes: notes })} />)
    const details = document.querySelector("details")!

    details.open = true
    fireEvent(details, new Event("toggle", { bubbles: false }))

    expect(screen.getByText(notes[0])).toBeInTheDocument()
    expect(screen.getByText(notes[1])).toBeInTheDocument()
  })

  it("offers nothing to open for a run frozen before the field existed", () => {
    render(<ProvenanceStrip provenance={provenance()} />)

    expect(screen.queryByText("Cách tính")).toBeNull()
  })
})

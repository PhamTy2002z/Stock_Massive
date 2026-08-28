import { describe, expect, it } from "vitest"

import type { ArtifactPayload, Frame } from "@/lib/alpha-desk/types"

import { csvFilename, frameToCsv, primaryFrame } from "./signal-desk-export"

function frame(overrides: Partial<Frame> = {}): Frame {
  return {
    kind: "table",
    columns: ["bucket", "volume"],
    rows: [
      ["09:15", 1_240_000],
      ["09:30", 812_000],
    ],
    unit: "shares",
    labels: { bucket: "Khung giờ", volume: "Khối lượng" },
    ...overrides,
  }
}

describe("a desk view leaving as a file", () => {
  it("writes the reader's column names over the Study's own values", () => {
    // The header is for a person and the cells are for a spreadsheet. A file
    // that abbreviated 1.240.000 to "1,24 tr" would be a picture of data.
    const csv = frameToCsv(frame())

    expect(csv.split("\r\n")).toEqual([
      "Khung giờ,Khối lượng",
      "09:15,1240000",
      "09:30,812000",
    ])
  })

  it("falls back to the column's own name where the server labelled nothing", () => {
    const csv = frameToCsv(frame({ labels: {} }))

    expect(csv.split("\r\n")[0]).toBe("bucket,volume")
  })

  it("wraps a cell that would otherwise end the field early", () => {
    const csv = frameToCsv(
      frame({
        columns: ["note"],
        labels: {},
        rows: [['ĐHĐCĐ, thường niên'], ['nói "được"'], ["hai\ndòng"]],
      }),
    )

    // The record separator is CRLF, so a newline *inside* a quoted field stays
    // where it was rather than becoming a fourth row.
    expect(csv.split("\r\n").slice(1)).toEqual([
      '"ĐHĐCĐ, thường niên"',
      '"nói ""được"""',
      '"hai\ndòng"',
    ])
  })

  it("leaves a cell the Study could not fill empty rather than zero", () => {
    // The distinction every widget draws: no value is not a value of nothing.
    const csv = frameToCsv(frame({ rows: [["09:15", null]] }))

    expect(csv.split("\r\n")[1]).toBe("09:15,")
  })

  it("keeps a short row lined up against its header", () => {
    const csv = frameToCsv(frame({ rows: [["09:15"]] }))

    expect(csv.split("\r\n")[1]).toBe("09:15,")
  })

  it("names the file after the desk view and the day it was frozen at", () => {
    expect(csvFilename("STB — Thanh khoản trong phiên", "2026-08-14T09:00:00Z")).toBe(
      "stb-thanh-khoan-trong-phien-2026-08-14.csv",
    )
  })

  it("still produces a filename for a desk view with no title", () => {
    expect(csvFilename("", "2026-08-14")).toBe("signal-desk-2026-08-14.csv")
  })

  it("exports the frame the first block draws", () => {
    // The headline picture is what a reader asking for "the data behind this"
    // means, and the spec puts it first.
    const artifact = {
      signal_desk_spec: {
        title: "t",
        blocks: [
          { widget: "bar_series", widgetVersion: 1, frame: "profile", options: {} },
        ],
      },
      frames: { other: frame(), profile: frame({ unit: "vnd" }) },
    } as unknown as ArtifactPayload

    expect(primaryFrame(artifact)?.unit).toBe("vnd")
  })

  it("falls back to any frame when the spec names one that is not there", () => {
    const artifact = {
      signal_desk_spec: { title: "t", blocks: [{ widget: "x", widgetVersion: 1, frame: "gone", options: {} }] },
      frames: { only: frame() },
    } as unknown as ArtifactPayload

    expect(primaryFrame(artifact)).not.toBeNull()
  })

  it("refuses rather than writing an empty file", () => {
    const artifact = {
      signal_desk_spec: { title: "t", blocks: [] },
      frames: {},
    } as unknown as ArtifactPayload

    expect(primaryFrame(artifact)).toBeNull()
  })
})

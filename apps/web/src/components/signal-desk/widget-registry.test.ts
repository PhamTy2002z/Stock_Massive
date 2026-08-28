/**
 * The two halves of the drawing contract, held to the server's own catalog.
 *
 * **Nothing is promised that cannot be drawn.** The catalog is generated from
 * `src/studies/widgets.py`, and a Study may only emit a widget the catalog
 * holds. If this build implements a smaller set than the catalog names, a real
 * question produces a block nobody can draw — and the first person to find out
 * is a reader looking at a table where a heatmap should be.
 *
 * **Degrading never fails.** A version this build has not met, a frame kind the
 * chosen widget cannot take, a name that has been retired: all three end at the
 * table, and none of them throws. That is the property the persisted-version
 * scheme rests on — an artifact written last month keeps asking for the version
 * it was written against, and the answer has to be a picture or a table, never
 * a blank panel.
 */

import { describe, expect, it } from "vitest"

import catalog from "../../../../../contracts/signal-desk-widget-catalog.json"

import { DataTableWidget } from "./widgets/data-table"
import { acceptedKinds, knownWidgets, resolveWidget, widgetKey } from "./widget-registry"

const CATALOG = catalog as {
  fallback: { widget: string; version: number }
  widgets: { name: string; version: number; frameKinds: string[] }[]
}

describe("the registry against the server's catalog", () => {
  it("implements every widget the server may send, and nothing it may not", () => {
    const promised = CATALOG.widgets
      .map((widget) => widgetKey(widget.name, widget.version))
      .sort()

    expect(knownWidgets()).toEqual(promised)
  })

  it("accepts the same frame kinds the server checks a Study's blocks against", () => {
    for (const widget of CATALOG.widgets) {
      expect(acceptedKinds(widget.name, widget.version)).toEqual(widget.frameKinds)
    }
  })

  it("falls back to the widget the catalog names as the fallback", () => {
    expect(CATALOG.fallback).toEqual({ widget: "data_table", version: 1 })
  })
})

describe("degrading", () => {
  it("draws a table for a version this build has never met", () => {
    const resolved = resolveWidget("session_heatmap", 99, "matrix")

    expect(resolved.component).toBe(DataTableWidget)
    expect(resolved.degraded).toBe(true)
  })

  it("draws a table for a widget that cannot take this frame's kind", () => {
    // The server checks this on every run, so reaching it means two builds
    // disagree — and a table is the honest thing to show while they do.
    const resolved = resolveWidget("session_heatmap", 1, "series")

    expect(resolved.component).toBe(DataTableWidget)
    expect(resolved.degraded).toBe(true)
  })

  it("draws a table for a name nothing registers, rather than throwing", () => {
    const resolved = resolveWidget("candlestick", 1, "series")

    expect(resolved.component).toBe(DataTableWidget)
    expect(resolved.degraded).toBe(true)
  })

  it("draws a table when the frame kind is unreadable", () => {
    const resolved = resolveWidget("bar_series", 1, undefined)

    expect(resolved.component).toBe(DataTableWidget)
    expect(resolved.degraded).toBe(true)
  })

  it("says nothing is degraded when the widget is the one that was asked for", () => {
    expect(resolveWidget("bar_series", 1, "series").degraded).toBe(false)
    expect(resolveWidget("data_table", 1, "matrix").degraded).toBe(false)
  })
})

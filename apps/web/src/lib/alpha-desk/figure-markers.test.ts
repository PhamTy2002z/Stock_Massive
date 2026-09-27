import { describe, expect, it } from "vitest"

import { readMarker, readSources, splitMarkers } from "./figure-markers"

describe("readMarker", () => {
  it("reads the three labels the host writes", () => {
    expect(readMarker("[1 · phiên 25/09/2026]")).toEqual({ kind: "cited", source: 1, label: "phiên 25/09/2026" })
    expect(readMarker("[2 · 07/01/2026 · nguồn cũ]")).toEqual({ kind: "stale", source: 2, label: "07/01/2026 · nguồn cũ" })
    expect(readMarker("[chưa kiểm chứng]")).toEqual({ kind: "unverified", source: null, label: "chưa kiểm chứng" })
  })

  it("leaves brackets that are not labels alone", () => {
    expect(readMarker("[xem thêm]")).toBeNull()
    expect(readMarker("[1]")).toBeNull()
  })
})

describe("splitMarkers", () => {
  it("keeps every character of the prose around the chips", () => {
    const nodes = splitMarkers("Giá 76.500 đồng [1 · phiên 25/09/2026], ROE 9% [chưa kiểm chứng].")
    const text = nodes
      .map((node) =>
        node.type === "text"
          ? (node as { value: string }).value
          : `<${((node as { children: { value: string }[] }).children[0]).value}>`,
      )
      .join("")
    // Neither a cited nor an unverified figure draws anything on screen.
    expect(text).toBe("Giá 76.500 đồng, ROE 9%.")
  })

  it("titles a stale chip with its source line", () => {
    const [, chip] = splitMarkers("6,31% [2 · 07/01/2026 · nguồn cũ]", new Map([[2, "cafef.vn — Sacombank"]]))
    expect((chip as { properties: Record<string, unknown> }).properties).toMatchObject({
      "data-figure": "stale",
      "data-source": "2",
      title: "[2] cafef.vn — Sacombank · 07/01/2026 · nguồn cũ",
    })
  })
})

describe("readSources", () => {
  it("reads the dated source list and drops the raw link", () => {
    const text = [
      "Trả lời.",
      "",
      "---",
      "",
      "**Nguồn số liệu**",
      "",
      "- [1] KB Securities — STB · nến ngày · 26/06/2026–25/09/2026",
      "- [2] cafef.vn — Sacombank — đăng 20/08/2026 — <https://cafef.vn/a.chn>",
    ].join("\n")

    expect(readSources(text)).toEqual(
      new Map([
        [1, "KB Securities — STB · nến ngày · 26/06/2026–25/09/2026"],
        [2, "cafef.vn — Sacombank — đăng 20/08/2026"],
      ]),
    )
  })
})

import { describe, expect, it } from "vitest"

import { readMarker, readSources, rehypeFigureMarkers, splitMarkers, splitSources, withoutUnverifiedNote } from "./figure-markers"

describe("readMarker", () => {
  it("reads the three labels the host writes", () => {
    expect(readMarker("[1 · phiên 25/09/2026]")).toEqual({ kind: "cited", source: 1, label: "phiên 25/09/2026" })
    expect(readMarker("[2 · 07/01/2026 · nguồn cũ]")).toEqual({ kind: "stale", source: 2, label: "07/01/2026 · nguồn cũ" })
    expect(readMarker("[chưa kiểm chứng]")).toEqual({ kind: "unverified", source: null, label: "chưa kiểm chứng" })
  })

  it("reads the English labels the host writes into an English answer", () => {
    expect(readMarker("[2 · 07/01/2026 · stale source]")).toEqual({ kind: "stale", source: 2, label: "07/01/2026 · stale source" })
    expect(readMarker("[unverified]")).toEqual({ kind: "unverified", source: null, label: "unverified" })
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

describe("splitSources", () => {
  const answer = [
    "Đóng cửa 76.900đ [1 · phiên 24/09/2026], P/E 45,17 lần [2].",
    "",
    "Nguồn:",
    "",
    "[1] KB Securities — STB · nến ngày · phiên 24/09/2026",
    "[2] KB Securities — STB · chỉ số tài chính · Quý 2/2026",
    "",
    "---",
    "",
    "**Nguồn số liệu**",
    "",
    "- [1] KB Securities — STB · nến ngày · phiên 24/09/2026",
    "- [2] cafef.vn — Sacombank — đăng 20/08/2026 — <https://cafef.vn/stb.chn>",
  ].join("\n")

  it("cuts both closing lists and keeps the host's lines", () => {
    const { body, sources } = splitSources(answer)
    expect(body).toBe("Đóng cửa 76.900đ [1 · phiên 24/09/2026], P/E 45,17 lần [2].")
    expect(sources).toEqual([
      { label: "KB Securities — STB · nến ngày · phiên 24/09/2026", url: null },
      { label: "cafef.vn — Sacombank — đăng 20/08/2026", url: "https://cafef.vn/stb.chn" },
    ])
  })

  it("reads the model's list when the host wrote none", () => {
    const { sources } = splitSources("Giá 76.900đ [1].\n\nNguồn:\n\n[1] Vietcap — STB · tin doanh nghiệp")
    expect(sources).toEqual([{ label: "Vietcap — STB · tin doanh nghiệp", url: null }])
  })

  it("leaves a Nguồn heading followed by prose alone", () => {
    const text = "Nguồn:\n\nTheo báo cáo quý."
    expect(splitSources(text)).toEqual({ body: text, sources: [] })
  })
})

describe("bare citations", () => {
  it("drops the model's own [n] numbers from the prose", () => {
    const tree = { type: "root", children: [{ type: "text", value: "P/E 45,17 lần [2], ROE 4,99% [2, 3]." }] }
    rehypeFigureMarkers()(tree)
    expect(tree.children).toEqual([{ type: "text", value: "P/E 45,17 lần, ROE 4,99%." }])
  })
})

describe("an English answer", () => {
  const answer = [
    "Closed at 76,900 VND [1 · session 24/09/2026], ROE 9% [unverified].",
    "",
    "Figures labelled [unverified] are not in this turn's tool data, or don't match the time the sentence refers to.",
    "",
    "---",
    "",
    "**Sources**",
    "",
    "- [1] KB Securities — STB · daily candles · session 24/09/2026",
    "- [2] cafef.vn — Sacombank — published 20/08/2026 — <https://cafef.vn/stb.chn>",
  ].join("\n")

  it("reads the host's English source list", () => {
    expect(readSources(answer).get(2)).toBe("cafef.vn — Sacombank — published 20/08/2026")
  })

  it("cuts the English note and list off the body", () => {
    const { body, sources } = splitSources(withoutUnverifiedNote(answer))
    expect(body).toBe("Closed at 76,900 VND [1 · session 24/09/2026], ROE 9% [unverified].")
    expect(sources.map((source) => source.url)).toEqual([null, "https://cafef.vn/stb.chn"])
  })

  it("reads the model's own Sources: heading", () => {
    const { sources } = splitSources("Price 76,900 VND [1].\n\nSources:\n\n[1] Vietcap — STB")
    expect(sources).toEqual([{ label: "Vietcap — STB", url: null }])
  })
})

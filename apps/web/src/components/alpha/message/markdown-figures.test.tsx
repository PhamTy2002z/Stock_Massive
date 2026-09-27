// @vitest-environment jsdom
import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Markdown } from "./markdown"

const ANSWER = [
  "| Mã | Giá | ROE |",
  "|---|---|---|",
  "| STB | **76.500 đồng [1 · phiên 25/09/2026]** | 21,35% [chưa kiểm chứng] |",
  "",
  "NPL 6,31% [2 · 07/01/2026 · nguồn cũ].",
  "",
  "---",
  "",
  "**Nguồn số liệu**",
  "",
  "- [1] KB Securities — STB · nến ngày · 26/06/2026–25/09/2026",
  "- [2] cafef.vn — Sacombank — đăng 07/01/2026 — <https://cafef.vn/a.chn>",
  "",
  "Số có nhãn [chưa kiểm chứng] không có trong dữ liệu công cụ của lượt này, hoặc không khớp mốc thời gian câu đó nói tới.",
].join("\n")

describe("figure labels in an answer", () => {
  it("draws each label as a chip, in tables and in bold alike", () => {
    const { container } = render(<Markdown text={ANSWER} />)

    const chips = Array.from(container.querySelectorAll("[data-figure]"))
    // A cited figure draws nothing, and neither does an unverified one (owner
    // decision 2026-09-27: the words cost more reading than they told); only an
    // old source is marked in the prose.
    expect(chips.map((chip) => chip.getAttribute("data-figure"))).toEqual(["stale"])
    expect(chips.map((chip) => chip.textContent)).toEqual(["nguồn cũ"])
    expect(chips[0].getAttribute("title")).toContain("07/01/2026")
    expect(container.textContent).not.toContain("chưa kiểm chứng")
    expect(container.textContent).toContain("21,35%")
    expect(container.querySelector("strong")?.textContent).toBe("76.500 đồng")
    expect(container.textContent).not.toContain("[1 · phiên")
  })

  it("renders the source list as a list, one source per item", () => {
    const { container } = render(<Markdown text={ANSWER} />)

    const items = Array.from(container.querySelectorAll("li")).map((item) => item.textContent)
    expect(items).toHaveLength(2)
    expect(items[1]).toContain("cafef.vn — Sacombank — đăng 07/01/2026")
  })
})

// @vitest-environment jsdom
/**
 * The sources panel: one row per source, and a click on a row opens it.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import type { ToolCall } from "@/lib/alpha-desk/types"

const MESSAGE_ID = 7

// Mocked at the hook boundary, the way the other shell suites do it.
const desk = { entries: [] as unknown[] }

vi.mock("./desk-state", () => ({ useDesk: () => desk }))
vi.mock("./shell-state", () => ({
  useShell: () => ({
    state: { inspector: "sources", sourcesMessageId: MESSAGE_ID },
    dispatch: () => {},
  }),
}))

import { SourcesTab } from "./sources-tab"

afterEach(cleanup)

const ANSWER = [
  "Đóng cửa 76.900đ [1 · phiên 24/09/2026].",
  "",
  "---",
  "",
  "**Nguồn số liệu**",
  "",
  "- [1] KB Securities — STB · nến ngày · phiên 24/09/2026",
  "- [2] Vietcap — STB · chỉ số tài chính · Quý 2/2026",
  "- [3] cafef.vn — Sacombank — đăng 20/08/2026 — <https://cafef.vn/stb.chn>",
].join("\n")

const SEARCH: ToolCall = {
  id: "call-1",
  name: "web_search",
  status: "ok",
  summary: "Tìm trên web: STB",
  round: 0,
  error: null,
  result_count: 2,
  results: [
    { title: "Sacombank", url: "https://cafef.vn/stb.chn", source: "cafef.vn", snippet: "" },
    { title: "STB quý 2", url: "https://vneconomy.vn/stb.htm", source: "vneconomy.vn", snippet: "" },
  ],
  kind: "external",
}

function show(text: string, toolCalls: ToolCall[] = []) {
  desk.entries = [{ kind: "assistant", messageId: MESSAGE_ID, view: { thoughts: [], toolCalls, text } }]
  render(<SourcesTab />)
}

describe("the sources panel", () => {
  it("lists each source once, cited ones first, each a link", () => {
    show(ANSWER, [SEARCH])

    const links = screen.getAllByRole("link")
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "https://www.kbsec.com.vn/",
      "https://trading.vietcap.com.vn/iq/company?ticker=STB",
      "https://cafef.vn/stb.chn",
      "https://vneconomy.vn/stb.htm",
    ])
    expect(links[0].textContent).toContain("KB Securities")
    expect(links[0].textContent).toContain("STB · nến ngày · phiên 24/09/2026")
    expect(links[0].getAttribute("target")).toBe("_blank")
  })

  it("draws no row for the lookups themselves", () => {
    show(ANSWER, [SEARCH])
    expect(screen.queryByText("Tìm trên web: STB")).toBeNull()
  })

  it("says so when the answer rested on nothing", () => {
    show("Xin chào.")
    expect(screen.getByText("Câu trả lời này không dựa trên nguồn nào.")).toBeTruthy()
  })
})

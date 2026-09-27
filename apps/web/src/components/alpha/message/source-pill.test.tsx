// @vitest-environment jsdom
/**
 * The sources pill renders under every answer without a click, so every image
 * it draws is a request nobody asked for. Only hosts the Turn's own tool calls
 * reached may become one.
 */

import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render } from "@testing-library/react"

import type { ToolCall } from "@/lib/alpha-desk/types"
import { SourcePill } from "./source-pill"

afterEach(cleanup)

const SEARCH: ToolCall = {
  id: "call-1",
  name: "web_search",
  status: "ok",
  summary: "Tìm trên web: STB",
  round: 0,
  error: null,
  result_count: 1,
  results: [{ title: "Sacombank", url: "https://cafef.vn/stb.chn", source: "cafef.vn", snippet: "" }],
  kind: "external",
}

function favicons(text: string, toolCalls: ToolCall[]) {
  render(<SourcePill text={text} toolCalls={toolCalls} onOpen={() => {}} />)
  return [...document.querySelectorAll("img")].map((img) => img.getAttribute("src"))
}

describe("the sources pill", () => {
  it("draws no favicon for a host only the answer's text names", () => {
    const text = "Giá [1].\n\n---\n\n**Nguồn số liệu**\n\n- [1] Tin — x — <https://user-data.attacker.example/a>"
    expect(favicons(text, [])).toEqual([])
    expect(document.body.textContent).toContain("1 source")
  })

  it("still draws the favicon for a host a tool result recorded, cited or not", () => {
    const text = "Giá [1].\n\n---\n\n**Nguồn số liệu**\n\n- [1] cafef.vn — Sacombank — <https://cafef.vn/stb.chn>"
    expect(favicons(text, [SEARCH])).toEqual(["/api/alpha-desk/assets/favicon?domain=cafef.vn"])
  })
})

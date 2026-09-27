// @vitest-environment jsdom
/**
 * An answer's Markdown can be written out of a page an attacker controls, so
 * nothing in it may make the reader's browser fetch anything.
 */

import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { Markdown } from "./markdown"

afterEach(cleanup)

describe("images in an answer", () => {
  it("draws an image as its alt text and requests nothing", () => {
    const { container } = render(
      <Markdown text="Xem biểu đồ ![bảng giá](https://evil.example/p.png?d=1) ở đây." />,
    )
    expect(container.querySelector("img")).toBeNull()
    expect(container.innerHTML).not.toContain("evil.example")
    expect(container.textContent).toContain("bảng giá")
  })

  it("draws nothing for an image with no alt text", () => {
    const { container } = render(<Markdown text="![](https://evil.example/p.png?d=1)" />)
    expect(container.querySelector("img")).toBeNull()
    expect(container.innerHTML).not.toContain("evil.example")
  })

  it("leaves a linked image as a working link to its target", () => {
    render(<Markdown text="[![logo](https://evil.example/l.png)](https://cafef.vn/a.chn)" />)
    const link = screen.getByRole("link", { name: "logo" })
    expect(link.getAttribute("href")).toBe("https://cafef.vn/a.chn")
    expect(link.querySelector("img")).toBeNull()
  })

  it("keeps ordinary links working", () => {
    render(<Markdown text="Nguồn: [CafeF](https://cafef.vn/stb.chn)" />)
    const link = screen.getByRole("link", { name: "CafeF" })
    expect(link.getAttribute("href")).toBe("https://cafef.vn/stb.chn")
    expect(link.getAttribute("rel")).toBe("noopener noreferrer")
  })
})

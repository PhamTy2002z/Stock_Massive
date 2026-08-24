// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Button } from "./button"

describe("Button", () => {
  it("provides the shared high-emphasis action size", () => {
    render(<Button size="action">Hỏi VisgniteAI</Button>)

    expect(screen.getByRole("button", { name: "Hỏi VisgniteAI" })).toHaveClass(
      "h-10",
      "px-3.5",
      "py-2",
    )
  })
})

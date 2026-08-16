/**
 * The artifact's Risk Notice is the backend's, word for word.
 *
 * The nightly payload carries no notice — the pipeline owns evidence, not the
 * rendering contract — so this surface supplies one. That is only honest while
 * the two texts are the same text: a paraphrase on one screen and the canonical
 * wording on another is exactly the drift the notice exists to prevent.
 *
 * So the assertion reads `manifest.py` rather than restating it.
 */

import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import { RISK_NOTICE_TEXT, RISK_NOTICE_VERSION } from "./risk-notice"

const MANIFEST = join(
  process.cwd(),
  "..",
  "api",
  "src",
  "agent",
  "manifest.py",
)

/** The canonical text, reassembled from the backend's implicit concatenation. */
function backendNotice(): string {
  const source = readFileSync(MANIFEST, "utf8")
  const block = source.match(/CANONICAL_RISK_NOTICE = \(([\s\S]*?)\n\)/)
  expect(block, "manifest.py should define CANONICAL_RISK_NOTICE").not.toBeNull()
  return [...block![1].matchAll(/"([^"]*)"/g)].map((part) => part[1]).join("")
}

function backendVersion(): string {
  const match = readFileSync(MANIFEST, "utf8").match(
    /RISK_NOTICE_VERSION = "([^"]+)"/,
  )
  expect(match, "manifest.py should define RISK_NOTICE_VERSION").not.toBeNull()
  return match![1]
}

describe("the Risk Notice the artifact renders", () => {
  it("is the backend's canonical text, unchanged", () => {
    expect(RISK_NOTICE_TEXT).toBe(backendNotice())
  })

  it("declares the version the backend stamps on it", () => {
    expect(RISK_NOTICE_VERSION).toBe(backendVersion())
  })

  it("keeps all four meanings a Risk Notice must retain", () => {
    // Checked as prose here rather than as an enum, because this copy has no
    // structure to declare — the backend's `RiskNotice` refuses a rendering
    // that drops one, and this is the same sentence it accepted.
    expect(RISK_NOTICE_TEXT).toMatch(/phân tích và tham khảo/)
    expect(RISK_NOTICE_TEXT).toMatch(/không phải tư vấn đầu tư/)
    expect(RISK_NOTICE_TEXT).toMatch(/cam kết lợi nhuận/)
    expect(RISK_NOTICE_TEXT).toMatch(/tự chịu trách nhiệm/)
  })
})

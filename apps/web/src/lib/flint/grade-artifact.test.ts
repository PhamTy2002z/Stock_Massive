/**
 * Every chart a golden run persisted, compiled again by the pinned package.
 *
 * This is the Flint-validity gate, and it lives here rather than in a Python
 * grader for the plainest possible reason: Flint runs in the browser and the
 * grader would have to guess what it does. Guessing is exactly what the contract
 * test proved is unsafe — the package accepts inputs that draw nothing and
 * inputs that draw nonsense — so the only honest way to say "this payload is a
 * chart" is to compile it.
 *
 * It costs nothing. The artifacts were written by a paid run; grading one again
 * is reading a file. So this runs in the ordinary suite, and a payload that
 * stopped compiling under a package bump fails here before anybody pays to find
 * out in a canary.
 *
 * The output is thrown away on purpose. A compiled ECharts option that survived
 * this file would be a second copy of an answer that could drift from the
 * evidence its part names.
 */

import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import { readVisual } from "@/lib/alpha-desk/read-content"

import { compileVisual } from "./compile-visual"

const ARTIFACTS = join(process.cwd(), "..", "api", "golden", "artifacts")

/** One chart out of one artifact, with enough context to name it in a failure. */
interface Persisted {
  artifact: string
  caseId: string
  trial: number
  payload: unknown
}

function persistedVisuals(): Persisted[] {
  let files: string[]
  try {
    files = readdirSync(ARTIFACTS).filter(
      (name) => name.endsWith(".json") && !name.endsWith("-tape.json"),
    )
  } catch {
    // The harness is a sibling package and its artifacts are not committed on
    // every branch. An absent directory is nothing to grade, not a failure.
    return []
  }
  const found: Persisted[] = []
  for (const file of files) {
    let body: unknown
    try {
      body = JSON.parse(readFileSync(join(ARTIFACTS, file), "utf-8"))
    } catch {
      continue
    }
    const cases = (body as { cases?: unknown }).cases
    if (!Array.isArray(cases)) continue
    for (const entry of cases) {
      const record = entry as Record<string, unknown>
      if (record.visual === undefined || record.visual === null) continue
      found.push({
        artifact: file,
        caseId: String(record.id ?? "?"),
        trial: Number(record.trial ?? 1),
        payload: record.visual,
      })
    }
  }
  return found
}

const VISUALS = persistedVisuals()

describe("every persisted chart still compiles", () => {
  it("finds the artifacts directory, or has nothing to grade", () => {
    // Stated so an empty run reads as "no charts recorded yet" rather than as a
    // green gate that quietly stopped looking at anything.
    expect(Array.isArray(VISUALS)).toBe(true)
  })

  it.runIf(VISUALS.length > 0)("reads and compiles all of them", () => {
    const failed: string[] = []
    for (const found of VISUALS) {
      const part = readVisual(found.payload)
      const compiled = part === null ? null : compileVisual(part)
      if (compiled === null || compiled.charts.length === 0) {
        failed.push(`${found.artifact}:${found.caseId} t${found.trial}`)
      }
    }
    expect(failed).toEqual([])
  })

  it.runIf(VISUALS.length > 0)("draws every row each chart carries", () => {
    // A chart compiled with fewer points than its payload holds is a wrong
    // chart rather than a missing one, and it fails silently in the package.
    for (const found of VISUALS) {
      const part = readVisual(found.payload)
      const compiled = compileVisual(part)
      if (compiled === null || part === null) continue
      compiled.charts.forEach((chart, index) => {
        expect(chart.option._dataLength).toBe(part.assemblies[index].data.values.length)
      })
    }
  })
})

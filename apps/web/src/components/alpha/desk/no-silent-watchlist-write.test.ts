/**
 * Arriving at Alpha Desk never changes the Watchlist.
 *
 * `?symbol=HPG` from Stock 360 carries the symbol into context as the active
 * lens and **never silently adds HPG to the Watchlist** (`docs/specs/0002` §7).
 * A Watchlist slot is one of ten, an addition can produce an Analysis against a
 * daily allowance, and neither is a thing to spend on someone following a link.
 *
 * A source scan rather than a render assertion, because the failure it guards
 * against is a helpful edit rather than a broken one: an effect that "makes
 * sure the symbol is on the rail" would be invisible in every test that renders
 * the surface without one. The rail itself still mutates — from its own form,
 * behind the dock's disclosure, where the user asked.
 */

import { readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

const DESK_ROOT = join(process.cwd(), "src/components/alpha/desk")

// Every way the client can change the Watchlist. `retryAnalysis` is included
// because a retry is production too, and it is charged the same way.
const MUTATIONS = [
  "addWatchlistSymbol",
  "removeWatchlistSymbol",
  "retryAnalysis",
  "useRailMutations",
]

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : []
  })
}

describe("the deep link", () => {
  it("gives the desk no way to write to the Watchlist at all", () => {
    const offenders = sourceFiles(DESK_ROOT).filter((path) => {
      const source = readFileSync(path, "utf8")
      return MUTATIONS.some((token) => source.includes(token))
    })

    expect(offenders).toEqual([])
  })
})

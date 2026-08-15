/**
 * The rail keeps itself current with what the app already has.
 *
 * Email needs SMTP credentials, web push needs VAPID keys plus a service
 * worker, and both are new infrastructure for an unmeasured problem: a handful
 * of internal users who all open the app in the evening. The badge already
 * persists the data email would need if anyone is later observed missing an
 * Analysis, so the cheapest next step stays available without being paid for
 * now.
 *
 * A test rather than a note in a document, because "we did not add a transport"
 * is the kind of decision that erodes by accident — one `EventSource` for one
 * screen, and the service worker follows.
 */

import { readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import { RAIL_POLL_MS } from "@/hooks/use-watchlist-rail"

const SOURCE_ROOT = join(process.cwd(), "src")

// The three channels this ticket declined, and nothing else. Notably absent:
// `EventSource`. ADR-0013 *mandates* a native same-origin EventSource for the
// Turn stream, so banning it here would turn this test red the day that
// transport lands — a decision test that contradicts an ADR is worse than none.
const DECLINED_CHANNELS = [
  "serviceWorker",
  "ServiceWorker",
  "PushManager",
  "pushManager",
  "Notification.requestPermission",
  "nodemailer",
]

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.tsx?$/.test(entry.name) && !entry.name.endsWith(".test.ts") &&
      !entry.name.endsWith(".test.tsx")
      ? [path]
      : []
  })
}

describe("how the rail learns that an Analysis is ready", () => {
  it("polls on an interval rather than waiting to be pushed to", () => {
    expect(Number.isFinite(RAIL_POLL_MS)).toBe(true)
    expect(RAIL_POLL_MS).toBeGreaterThan(0)
  })

  it("adds no push channel, no service worker, and no mail", () => {
    const offenders = sourceFiles(SOURCE_ROOT).filter((path) => {
      const source = readFileSync(path, "utf8")
      return DECLINED_CHANNELS.some((token) => source.includes(token))
    })

    expect(offenders).toEqual([])
  })
})

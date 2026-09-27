// @vitest-environment jsdom
/**
 * An answer is announced only to a reader who looked away and asked to be told.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { announceSettledTurn } from "./answer-alert"
import { writePreferences } from "./preferences"

const created: { title: string; options: NotificationOptions }[] = []

class FakeNotification {
  static permission: NotificationPermission = "granted"
  onclick: (() => void) | null = null
  constructor(title: string, options: NotificationOptions) {
    created.push({ title, options })
  }
  close() {}
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden })
}

beforeEach(() => {
  created.length = 0
  FakeNotification.permission = "granted"
  vi.stubGlobal("Notification", FakeNotification)
  writePreferences({ notifyOnAnswer: true })
})

afterEach(() => {
  vi.unstubAllGlobals()
  setHidden(false)
})

describe("announcing a settled Turn", () => {
  it("raises one notification, tagged by the Turn, when the tab is hidden", () => {
    setHidden(true)

    announceSettledTurn({ turnId: "turn-1", title: "Cổ tức VNM", answered: true })

    expect(created).toEqual([
      { title: "Cổ tức VNM", options: { body: "Your answer is ready.", tag: "turn-1" } },
    ])
  })

  it("stays quiet for a reader who is watching", () => {
    setHidden(false)

    announceSettledTurn({ turnId: "turn-1", title: null, answered: true })

    expect(created).toHaveLength(0)
  })

  it("stays quiet when the reader did not ask, or the browser refused", () => {
    setHidden(true)
    writePreferences({ notifyOnAnswer: false })
    announceSettledTurn({ turnId: "turn-1", title: null, answered: true })

    writePreferences({ notifyOnAnswer: true })
    FakeNotification.permission = "denied"
    announceSettledTurn({ turnId: "turn-2", title: null, answered: true })

    expect(created).toHaveLength(0)
  })

  it("falls back to the product name for an untitled conversation", () => {
    setHidden(true)

    announceSettledTurn({ turnId: "turn-1", title: "  ", answered: false })

    expect(created[0].title).toBe("VisgniteAI")
  })
})

// @vitest-environment jsdom
/**
 * Whether a reload can find the Turn again.
 *
 * The Turn survives the browser regardless — this only decides whether the tab
 * that started it can still point at it. Everything here is about the failure
 * modes of storage rather than about the happy path: a value another build
 * wrote, and a browser that refuses storage entirely.
 */

import { beforeEach, describe, expect, it } from "vitest"

import {
  deepLinkedSymbol,
  openingState,
  readDeskSession,
  writeDeskSession,
} from "./desk-session"

const KEY = "alpha-desk.session"

beforeEach(() => {
  window.sessionStorage.clear()
})

describe("what the tab remembers", () => {
  it("hands back the Thread and the Turn it was showing", () => {
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: null })

    expect(readDeskSession()).toEqual({
      threadId: "thread-1",
      turnId: "turn-1",
      activeSymbol: null,
    })
  })

  it("starts empty when nothing was stored", () => {
    expect(readDeskSession()).toEqual({ threadId: null, turnId: null, activeSymbol: null })
  })

  it("forgets the Turn on its own, keeping the Thread, once it settles", () => {
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: null })
    writeDeskSession({ threadId: "thread-1", turnId: null, activeSymbol: null })

    expect(readDeskSession()).toEqual({
      threadId: "thread-1",
      turnId: null,
      activeSymbol: null,
    })
  })

  it("clears the key entirely rather than leaving an empty record", () => {
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: null })
    writeDeskSession({ threadId: null, turnId: null, activeSymbol: null })

    expect(window.sessionStorage.getItem(KEY)).toBeNull()
  })
})

describe("what the surface opens onto", () => {
  const remembered = { threadId: "thread-1", turnId: "turn-1", activeSymbol: "FPT" }

  it("reattaches to a Turn that was still running when the tab last rendered", () => {
    // A reload, a route change and a dropped network all end the subscriber and
    // nothing else. The Turn belongs to the backend.
    expect(openingState(null, remembered)).toEqual({
      threadId: "thread-1",
      turnId: "turn-1",
      activeSymbol: "FPT",
    })
  })

  it("opens a new free-roaming Thread for a deep link rather than the remembered one", () => {
    expect(openingState("HPG", remembered)).toEqual({
      threadId: null,
      turnId: null,
      activeSymbol: "HPG",
    })
  })

  it("carries the deep-linked symbol as the lens and nothing more", () => {
    // Not onto the Watchlist. Arriving from Stock 360 is a question, not a
    // decision about what gets analysed every night.
    expect(openingState("HPG", { threadId: null, turnId: null, activeSymbol: null }).activeSymbol).toBe("HPG")
  })

  it("reattaches on the reload after a deep link, once the parameter is consumed", () => {
    // The caller strips `?symbol=` from the URL as soon as this has read it.
    // Left in place, every later reload would look like a fresh arrival, open
    // yet another Thread, and abandon the Turn the user is watching.
    expect(openingState(null, { ...remembered, activeSymbol: "HPG" })).toEqual({
      threadId: "thread-1",
      turnId: "turn-1",
      activeSymbol: "HPG",
    })
  })

  it("drops a remembered Turn whose Thread is gone", () => {
    expect(openingState(null, { threadId: null, turnId: "turn-1", activeSymbol: null }).turnId).toBeNull()
  })
})

describe("the deep-linked symbol", () => {
  it("normalises what arrived in the query string", () => {
    expect(deepLinkedSymbol(" hpg ")).toBe("HPG")
  })

  it("ignores anything that is not shaped like a symbol", () => {
    expect(deepLinkedSymbol(null)).toBeNull()
    expect(deepLinkedSymbol("")).toBeNull()
    expect(deepLinkedSymbol("../admin")).toBeNull()
  })
})

describe("a value this build cannot read", () => {
  it("starts fresh rather than throwing on the way to a render", () => {
    window.sessionStorage.setItem(KEY, "not json at all")

    expect(readDeskSession()).toEqual({ threadId: null, turnId: null, activeSymbol: null })
  })

  it("ignores fields of the wrong shape", () => {
    window.sessionStorage.setItem(KEY, JSON.stringify({ threadId: 7, turnId: null }))

    expect(readDeskSession().threadId).toBeNull()
  })
})

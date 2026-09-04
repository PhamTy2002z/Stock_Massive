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
  clearDeskSession,
  deepLinkedSymbol,
  deepLinkedThread,
  openingState,
  readDeskSession,
  readPinnedBoards,
  writeDeskSession,
  writePinnedBoards,
} from "./desk-session"

const KEY = "alpha-desk.session"
const PINS_KEY = "alpha-desk.board-pins"

beforeEach(() => {
  window.sessionStorage.clear()
  window.localStorage.clear()
})

describe("what the tab remembers", () => {
  it("hands back the Thread and the Turn it was showing", () => {
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: null })

    expect(readDeskSession()).toEqual({
      threadId: "thread-1",
      turnId: "turn-1",
      activeSymbol: null,
      signalDeskThreads: [],
      pendingAttachments: [],
    })
  })

  it("starts empty when nothing was stored", () => {
    expect(readDeskSession()).toEqual({
      threadId: null,
      turnId: null,
      activeSymbol: null,
      signalDeskThreads: [],
      pendingAttachments: [],
    })
  })

  it("forgets the Turn on its own, keeping the Thread, once it settles", () => {
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: null })
    writeDeskSession({ threadId: "thread-1", turnId: null, activeSymbol: null })

    expect(readDeskSession()).toEqual({
      threadId: "thread-1",
      turnId: null,
      activeSymbol: null,
      signalDeskThreads: [],
      pendingAttachments: [],
    })
  })

  it("clears the key entirely rather than leaving an empty record", () => {
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: null })
    writeDeskSession({ threadId: null, turnId: null, activeSymbol: null })

    expect(window.sessionStorage.getItem(KEY)).toBeNull()
  })

  it("forgets everything when the way in asks it to", () => {
    // What signing in opens onto. A remembered Thread is for a reload of the
    // desk, not for a return across a sign-in: whoever just gave their password
    // gets the empty question, not this tab's last conversation.
    writeDeskSession({ threadId: "thread-1", turnId: "turn-1", activeSymbol: "STB" })

    clearDeskSession()

    expect(readDeskSession()).toEqual({
      threadId: null,
      turnId: null,
      activeSymbol: null,
      signalDeskThreads: [],
      pendingAttachments: [],
    })
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

  it("opens the Thread a `?thread=` link names, over what this tab remembered", () => {
    // *Open in new tab* from the sidebar menu. The new tab has subscribed to
    // nothing, so it carries no Turn — but the lens is a workspace setting and
    // survives.
    expect(openingState(null, remembered, "thread-2")).toEqual({
      threadId: "thread-2",
      turnId: null,
      activeSymbol: "FPT",
    })
  })

  it("lets a named Thread outrank a deep-linked symbol", () => {
    // A link that says which conversation to show is not asking for a new one.
    expect(openingState("HPG", remembered, "thread-2").threadId).toBe("thread-2")
  })
})

describe("the deep-linked Thread", () => {
  it("takes an id shaped like one, however it was cased", () => {
    expect(deepLinkedThread(" 6F1C2B84-9A0D-4E77-B3F5-2C8A1D4E7B90 ")).toBe(
      "6f1c2b84-9a0d-4e77-b3f5-2c8a1d4e7b90",
    )
  })

  it("ignores anything else, so a hand-edited URL is simply not a deep link", () => {
    expect(deepLinkedThread(null)).toBeNull()
    expect(deepLinkedThread("")).toBeNull()
    expect(deepLinkedThread("../admin")).toBeNull()
    expect(deepLinkedThread("thread-1")).toBeNull()
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

    expect(readDeskSession()).toEqual({
      threadId: null,
      turnId: null,
      activeSymbol: null,
      signalDeskThreads: [],
      pendingAttachments: [],
    })
  })

  it("ignores fields of the wrong shape", () => {
    window.sessionStorage.setItem(KEY, JSON.stringify({ threadId: 7, turnId: null }))

    expect(readDeskSession().threadId).toBeNull()
  })
})

describe("the boards a conversation keeps on its strip", () => {
  it("hands back what was pinned in that conversation and nothing else", () => {
    writePinnedBoards("thread-1", ["a1", "a2"])
    writePinnedBoards("thread-2", ["b1"])

    expect(readPinnedBoards("thread-1")).toEqual(["a1", "a2"])
    expect(readPinnedBoards("thread-2")).toEqual(["b1"])
  })

  it("has no answer for a conversation nothing was pinned in", () => {
    expect(readPinnedBoards("thread-9")).toEqual([])
    expect(readPinnedBoards(null)).toEqual([])
  })

  it("outlives the tab, unlike the Turn above", () => {
    // `localStorage` on purpose: which two boards a reader works from is a
    // decision about the conversation, not about the window it was made in.
    writePinnedBoards("thread-1", ["a1"])

    expect(window.sessionStorage.getItem(PINS_KEY)).toBeNull()
    expect(window.localStorage.getItem(PINS_KEY)).not.toBeNull()
  })

  it("records an unpin rather than leaving the old answer standing", () => {
    writePinnedBoards("thread-1", ["a1", "a2"])

    writePinnedBoards("thread-1", ["a2"])

    expect(readPinnedBoards("thread-1")).toEqual(["a2"])
  })

  it("keeps no more than the strip has slots for", () => {
    writePinnedBoards("thread-1", ["a1", "a2", "a3", "a4", "a5", "a6", "a7"])

    expect(readPinnedBoards("thread-1")).toHaveLength(5)
  })

  it("forgets the conversations it has gone longest without", () => {
    for (let index = 0; index < 30; index += 1) {
      writePinnedBoards(`thread-${index}`, [`a${index}`])
    }

    expect(readPinnedBoards("thread-29")).toEqual(["a29"])
    expect(readPinnedBoards("thread-0")).toEqual([])
  })

  it("reads a record it cannot parse as no pins rather than throwing", () => {
    window.localStorage.setItem(PINS_KEY, "not json at all")

    expect(readPinnedBoards("thread-1")).toEqual([])
  })

  it("ignores entries of the wrong shape", () => {
    window.localStorage.setItem(
      PINS_KEY,
      JSON.stringify({ "thread-1": "a1", "thread-2": ["b1", 7] }),
    )

    expect(readPinnedBoards("thread-1")).toEqual([])
    expect(readPinnedBoards("thread-2")).toEqual(["b1"])
  })

  it("writes nothing for a conversation that does not exist yet", () => {
    writePinnedBoards(null, ["a1"])

    expect(window.localStorage.getItem(PINS_KEY)).toBeNull()
  })
})

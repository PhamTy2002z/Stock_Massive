// @vitest-environment jsdom
/**
 * When the answer is allowed on screen, which is where the last bug lived.
 *
 * The transcript's pin and its spacer are built on one rule — every way the
 * transcript can change height is a commit — and the first version of this
 * reveal broke it by laying the whole answer out invisibly and letting CSS
 * change the height afterwards. The result was a blank region the view scrolled
 * to, and a height that moved twice with nothing to absorb it.
 *
 * So the assertions here are about *steps*: the answer grows a piece at a time,
 * it does not start until the rows above it have finished folding, and the
 * canonical message does not take over until the last word has arrived.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"

import { IDLE, type LiveTurn } from "@/lib/alpha-desk/live-turn"
import { TIMELINE_FOLD_MS } from "@/lib/alpha-desk/reveal"
import { CHUNK_FADE_MS } from "@/lib/alpha-desk/word-cadence"
import { useAnswerReveal } from "./use-answer-reveal"

const TURN = "22222222-2222-4222-8222-222222222222"

function live(overrides: Partial<LiveTurn> = {}): LiveTurn {
  return {
    ...IDLE,
    turnId: TURN,
    threadId: "11111111-1111-4111-8111-111111111111",
    phase: "running",
    subscribable: true,
    ...overrides,
  }
}

/** Two sentences, enough that no single step can carry all of it. */
const ANSWER = "Phiên hôm nay STB tăng nhẹ 0,27% với thanh khoản trên trung bình 20 phiên. " +
  "Dòng tiền tập trung vào nhóm ngân hàng trong phiên chiều, và khối ngoại mua ròng."

/** Drives frames the way a browser would, at 60Hz. */
function frames(count: number): void {
  act(() => {
    for (let index = 0; index < count; index += 1) vi.advanceTimersByTime(16)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  // jsdom has no frame loop, and the pacer is driven by one.
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
    window.setTimeout(() => callback(performance.now()), 16),
  )
  vi.stubGlobal("cancelAnimationFrame", (handle: number) => window.clearTimeout(handle))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("the answer arriving", () => {
  it("grows a piece at a time rather than landing whole", () => {
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live(),
    })

    view.rerender(live({ text: ANSWER }))
    expect(view.result.current.text).toBe("")

    frames(8)
    const early = view.result.current.text
    expect(early.length).toBeGreaterThan(0)
    expect(early.length).toBeLessThan(ANSWER.length)

    frames(8)
    expect(view.result.current.text.length).toBeGreaterThan(early.length)

    frames(200)
    expect(view.result.current.text).toBe(ANSWER)
  })

  it("puts no word on screen in halves", () => {
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live(),
    })
    view.rerender(live({ text: ANSWER }))

    for (let step = 0; step < 30; step += 1) {
      frames(2)
      const shown = view.result.current.text
      if (shown === "" || shown === ANSWER) continue
      // What is on screen ends where a word ends: the next character is either
      // whitespace or the end of what has arrived.
      expect(ANSWER.charAt(shown.length - 1)).toMatch(/\s/)
    }
  })

  it("waits for the rows above it to finish folding", () => {
    const working = live({ toolCalls: [] , thoughts: [{ round: 0, text: "Tôi sẽ tra dữ liệu" }] })
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: working,
    })

    // The work is over — the timeline is folding — and nothing of the answer is
    // in the layout yet, so the fold has the page to itself.
    view.rerender({ ...working, text: ANSWER })
    frames(6)
    expect(view.result.current.text).toBe("")
    expect(view.result.current.working).toBe(false)

    act(() => vi.advanceTimersByTime(TIMELINE_FOLD_MS))
    frames(4)
    expect(view.result.current.text.length).toBeGreaterThan(0)
  })

  it("starts at once when there was nothing above it to fold", () => {
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live(),
    })

    view.rerender(live({ text: ANSWER }))
    frames(6)

    expect(view.result.current.text.length).toBeGreaterThan(0)
  })

  it("holds the canonical message back until the last word has faded in", () => {
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live(),
    })

    // The delta, then the terminal event: two events, two commits, which is how
    // the stream delivers them.
    view.rerender(live({ text: ANSWER }))
    frames(20)
    expect(view.result.current.handedOver).toBe(false)

    view.rerender(live({ text: ANSWER, phase: "completed", messageId: 7 }))
    expect(view.result.current.handedOver).toBe(false)

    frames(200)
    expect(view.result.current.text).toBe(ANSWER)
    // Still not: the last word is in the DOM and is a quarter of a second from
    // being fully on screen.
    expect(view.result.current.handedOver).toBe(false)

    act(() => vi.advanceTimersByTime(CHUNK_FADE_MS))
    expect(view.result.current.handedOver).toBe(true)
  })

  it("draws a Turn that was already over when it was first seen, unpaced", () => {
    // A reload, or a tab opened late. Pacing it would replay an answer as if it
    // were arriving, and would hold the canonical message back for no reason.
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live({ phase: "completed", messageId: 7, text: ANSWER }),
    })
    frames(1)

    expect(view.result.current.text).toBe(ANSWER)
  })

  it("says the work is running only while there is nothing to read", () => {
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live(),
    })
    expect(view.result.current.working).toBe(true)

    view.rerender(live({ text: ANSWER }))
    expect(view.result.current.working).toBe(false)
  })

  it("starts over for the next Turn rather than continuing the last one", () => {
    const view = renderHook((state: LiveTurn) => useAnswerReveal(state), {
      initialProps: live({ text: ANSWER, phase: "completed" }),
    })
    frames(200)
    expect(view.result.current.text).toBe(ANSWER)

    view.rerender(live({ turnId: "33333333-3333-4333-8333-333333333333", text: "" }))
    expect(view.result.current.text).toBe("")
  })
})

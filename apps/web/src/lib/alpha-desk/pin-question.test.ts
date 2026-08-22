/**
 * Whether a new question actually reaches the top of the screen.
 *
 * Both ways this has broken are in here as cases, because neither was visible
 * from the view: the component rendered fine, the tests passed, and the question
 * simply sat where it was with the previous answer still on screen.
 */

import { describe, expect, it } from "vitest"

import { pinStep } from "./pin-question"

/** One landing, run to convergence the way the commits would run it. */
function land(layout: { target: number; base: number; clientHeight: number }, steps = 5) {
  let tail = 0
  const taken: number[] = []
  for (let step = 0; step < steps; step += 1) {
    const result = pinStep({
      target: layout.target,
      // What the DOM would report: the content plus whatever spacer is in it.
      scrollHeight: layout.base + tail,
      clientHeight: layout.clientHeight,
      tail,
    })
    taken.push(result.tail)
    tail = result.tail
    if (result.scroll !== null) return { scroll: result.scroll, tail, steps: taken }
  }
  return { scroll: null, tail, steps: taken }
}

describe("landing a question at the top", () => {
  it("makes room first and scrolls on the next step", () => {
    // A question asked into a screen with nothing under it yet: 900 of content,
    // an 800 window, and the question 700 down. Reachable is 100, so 600 short.
    const landing = land({ target: 700, base: 900, clientHeight: 800 })

    expect(landing.steps).toEqual([600, 600])
    expect(landing.scroll).toBe(700)
  })

  it("keeps asking for the same spacer once the DOM carries it", () => {
    // The regression that stopped the pin dead. This number is the whole spacer
    // the layout needs, not the part still missing — so it stays 600 rather than
    // falling to zero, and a readiness check written as "zero" waits forever.
    const first = pinStep({ target: 700, scrollHeight: 900, clientHeight: 800, tail: 0 })
    expect(first).toEqual({ tail: 600, scroll: null })

    const second = pinStep({ target: 700, scrollHeight: 1500, clientHeight: 800, tail: 600 })
    expect(second).toEqual({ tail: 600, scroll: 700 })
  })

  it("scrolls immediately when the transcript is already tall enough", () => {
    // A long conversation needs no spacer, and asking for a second step there
    // would be a frame of delay for nothing.
    const landing = land({ target: 700, base: 4000, clientHeight: 800 })

    expect(landing.steps).toEqual([0])
    expect(landing.scroll).toBe(700)
  })

  it("gives the spacer back as the answer grows into it", () => {
    // The pin holding still. The answer adds 200 at a time, so the spacer stops
    // needing 200 at a time — the transcript's total height, and with it the
    // question's position on screen, do not move at all.
    const held = (content: number, tail: number) =>
      pinStep({ target: 700, scrollHeight: content + tail, clientHeight: 800, tail }).tail

    expect(held(900, 600)).toBe(600)
    expect(held(1100, 600)).toBe(400)
    expect(held(1300, 400)).toBe(200)
    expect(held(1500, 200)).toBe(0)
  })

  it("asks for no spacer at all once the answer fills the screen", () => {
    // Past this point the pin has nothing left to hold and the view is free to
    // follow the bottom again.
    expect(pinStep({ target: 700, scrollHeight: 3000, clientHeight: 800, tail: 200 })).toEqual({
      tail: 0,
      scroll: null,
    })
  })

  it("never asks for a negative spacer", () => {
    expect(pinStep({ target: 0, scrollHeight: 5000, clientHeight: 800, tail: 0 })).toEqual({
      tail: 0,
      scroll: 0,
    })
  })

  it("rounds, because a fractional spacer is a fractional scroll that never settles", () => {
    const step = pinStep({ target: 700.4, scrollHeight: 900.2, clientHeight: 800, tail: 0 })
    expect(Number.isInteger(step.tail)).toBe(true)
    expect(step.tail).toBe(600)
  })
})

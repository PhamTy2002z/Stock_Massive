/**
 * How fast an answer appears, and where it is allowed to stop.
 *
 * The rate assertions are about the two ends of it: a one-line reply must not
 * crawl, and a page of prose must not take a minute. The boundary assertions are
 * the ones that keep the cascade from stuttering — a word put on screen in two
 * pieces is a word that fades in twice, and text with no word boundaries in it
 * must not stall the reveal completely.
 */

import { describe, expect, it } from "vitest"

import {
  REVEAL_DRAIN_MS,
  REVEAL_MAX_CPS,
  REVEAL_MIN_CPS,
  REVEAL_PARTIAL_MAX,
  advanceCursor,
  revealRate,
  revealedLength,
} from "./reveal"

describe("the rate", () => {
  it("clears whatever is waiting in about the drain time", () => {
    const backlog = 600
    const seconds = backlog / revealRate(backlog)

    expect(seconds * 1000).toBeCloseTo(REVEAL_DRAIN_MS, 0)
  })

  it("is bounded at both ends", () => {
    expect(revealRate(3)).toBe(REVEAL_MIN_CPS)
    expect(revealRate(100_000)).toBe(REVEAL_MAX_CPS)
  })

  it("is nothing at all when there is nothing waiting", () => {
    expect(revealRate(0)).toBe(0)
  })
})

describe("the cursor", () => {
  it("never runs past the text it is reading out", () => {
    expect(advanceCursor(0, 10, 10_000)).toBe(10)
  })

  it("keeps its fraction, because a frame is worth a few characters", () => {
    const after = advanceCursor(0, 4000, 16)
    expect(after).toBeGreaterThan(0)
    expect(Number.isInteger(after)).toBe(false)
  })
})

describe("where the reveal may stop", () => {
  it("holds a half-arrived word back until it is whole", () => {
    // "STB tăn|g nhẹ" — the cursor is inside a word, so the word waits.
    expect(revealedLength("STB tăng nhẹ", 7)).toBe(4)
  })

  it("shows a word as soon as the space after it exists", () => {
    expect(revealedLength("STB tăng nhẹ", 9)).toBe(9)
  })

  it("shows the last word of a finished answer, which has no space after it", () => {
    expect(revealedLength("STB tăng", 8)).toBe(8)
  })

  it("does not stall on text that has no word boundaries in it", () => {
    const url = "https://example.com/" + "a".repeat(200)
    const at = REVEAL_PARTIAL_MAX + 10

    expect(revealedLength(url + " sau", at)).toBe(at)
  })

  it("never goes backwards over a boundary it already passed", () => {
    expect(revealedLength("một hai ba", 0)).toBe(0)
    expect(revealedLength("", 5)).toBe(0)
  })
})

/**
 * A table is paced by the row, because it is the one construct whose layout is
 * measured from every cell it holds. A cell that grows re-measures the whole
 * grid, so a word at a time is a column shift per commit — and a header row on
 * its own is not a table at all, it is a line of pipe characters.
 */
describe("where the reveal may stop inside a table", () => {
  const TABLE = ["| Mã | ROE |", "| --- | ---: |", "| CTG | 70,0 |", "| MBB | 66,7 |"]
  const text = "Bảng:\n\n" + TABLE.join("\n") + "\n\nSau bảng."
  const at = (line: number) => text.indexOf(TABLE[line])

  it("holds the header row back until the row that makes it a table", () => {
    const inHeader = at(0) + "| Mã | ".length

    expect(revealedLength(text, inHeader)).toBe(at(0))
  })

  it("holds a half-arrived row back whole, not word by word", () => {
    const inRow = at(2) + "| CTG | ".length

    expect(revealedLength(text, inRow)).toBe(at(2))
  })

  it("shows a row as soon as the line that holds it is complete", () => {
    expect(revealedLength(text, at(3))).toBe(at(3))
  })

  it("paces the prose after a table by the word again", () => {
    const inWord = text.indexOf("bảng.") + 2

    expect(revealedLength(text, inWord)).toBe(text.indexOf("bảng."))
  })
})

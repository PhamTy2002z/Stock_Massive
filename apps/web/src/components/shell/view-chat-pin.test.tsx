// @vitest-environment jsdom
/**
 * Whether a new question actually gets moved to the top of the transcript.
 *
 * `pin-question.test.ts` proves the arithmetic. This proves the wiring, and the
 * wiring is what broke: the view rendered perfectly, the suite stayed green, and
 * the question sat at the bottom of the screen with the previous answer still
 * above it. Nothing in the component tree shows that — only the scroll position
 * does, which is why this file states geometry and asserts on a scroll.
 *
 * jsdom has no layout, so the four numbers a browser would supply are supplied
 * here: the window's height, the transcript's height, where the question sits,
 * and the spacer. They are installed on the prototype rather than on an element,
 * because the element that matters is the one React mounts *next* — a stub
 * attached to the question already on screen would miss the one being asked.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, render } from "@testing-library/react"

const desk = {
  threadId: "thread-1" as string | null,
  entries: [] as unknown[],
  canCancel: false,
  isCancelling: false,
  isSubmitting: false,
  refusal: null as string | null,
  flagFailedFor: null as number | null,
  submit: vi.fn(),
  cancel: vi.fn(),
  retry: vi.fn(),
  resend: vi.fn(),
  flag: vi.fn(),
  unflag: vi.fn(),
  dismissRefusal: vi.fn(),
  openThread: vi.fn(),
  newThread: vi.fn(),
  openAnalysis: vi.fn(),
}

vi.mock("./desk-state", () => ({
  useDesk: () => desk,
  DeskProvider: ({ children }: { children: React.ReactNode }) => children,
}))

import { ChatView } from "./view-chat"
import { ShellProvider } from "./shell-state"

/** The breathing room the view leaves above a pinned question. */
const ANCHOR_PAD_PX = 14

/** The stated geometry: an 800px window onto 1000px of transcript. */
const WINDOW_HEIGHT = 800
const CONTENT_HEIGHT = 1000
/**
 * Where the newest question sits, measured from the top of the *window*.
 *
 * Opening a conversation lands at its end, so by the time a follow-up is asked
 * the transcript is scrolled to the bottom — `CONTENT_HEIGHT` here. A rect is
 * relative to the window, so the question's offset into the transcript is the
 * two added together, and that is what the pin scrolls to.
 */
const QUESTION_TOP = 900
const QUESTION_OFFSET = CONTENT_HEIGHT + QUESTION_TOP
const PIN_TARGET = QUESTION_OFFSET - ANCHOR_PAD_PX
/** The room the pin has to make: everything the transcript cannot reach. */
const EXPECTED_TAIL = PIN_TARGET - (CONTENT_HEIGHT - WINDOW_HEIGHT)

const answer = {
  text: "Phiên 21/08/2026, STB tăng nhẹ 0,27%.",
  toolCalls: [],
  thoughts: [],
  followUps: [],
  elapsedMs: 0,
  completed: true,
}

const answered = [
  { kind: "user", key: "u1", text: "Về mã STB thì sao?", pending: false },
  { kind: "assistant", key: "a1", view: answer, messageId: 1, flaggedReason: null },
]

const followUp = {
  kind: "user",
  key: "u2",
  text: "Thời điểm nào biến động nhiều nhất?",
  pending: true,
}

/** Every scroll the view asked for, in order. */
let scrolls: number[] = []
const realScrollTo = HTMLElement.prototype.scrollTo
const realRect = Element.prototype.getBoundingClientRect

function isTranscript(element: Element): boolean {
  return element.classList.contains("overflow-y-auto")
}

/** The spacer the view rendered, read off the DOM rather than tracked here. */
function tailHeight(): number {
  const spacer = document.querySelector<HTMLElement>(".overflow-y-auto > div:last-child")
  return spacer ? Number.parseFloat(spacer.style.height || "0") : 0
}

beforeEach(() => {
  scrolls = []
  desk.entries = []
  desk.threadId = "thread-1"

  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get(this: HTMLElement) {
      return isTranscript(this) ? WINDOW_HEIGHT : 0
    },
  })
  // The spacer lives inside the transcript, so its height counts here — that
  // growth is exactly what the second step of a landing waits for.
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    get(this: HTMLElement) {
      return isTranscript(this) ? CONTENT_HEIGHT + tailHeight() : 0
    },
  })
  Element.prototype.getBoundingClientRect = function (this: Element) {
    const top = isTranscript(this) ? 0 : this.className.includes("items-end") ? QUESTION_TOP : 0
    return { top, bottom: top, left: 0, right: 0, width: 0, height: 0, x: 0, y: top, toJSON: () => ({}) } as DOMRect
  }
  HTMLElement.prototype.scrollTo = function (this: HTMLElement, options?: unknown) {
    if (options && typeof options === "object" && "top" in options) {
      scrolls.push(Number((options as ScrollToOptions).top))
    }
  } as HTMLElement["scrollTo"]
})

afterEach(() => {
  cleanup()
  HTMLElement.prototype.scrollTo = realScrollTo
  Element.prototype.getBoundingClientRect = realRect
  // @ts-expect-error restoring jsdom's own zero-height getters
  delete HTMLElement.prototype.clientHeight
  // @ts-expect-error as above
  delete HTMLElement.prototype.scrollHeight
})

function shell() {
  return (
    <ShellProvider>
      <ChatView />
    </ShellProvider>
  )
}

describe("asking a follow-up", () => {
  it("scrolls the new question to the top, past the answer already on screen", () => {
    desk.entries = [...answered]
    const view = render(shell())

    // Nothing has been asked yet, so nothing has been pinned.
    expect(scrolls).toEqual([])

    desk.entries = [...answered, followUp]
    act(() => view.rerender(shell()))

    // The transcript can only scroll 200 on its own, so the pin had to make
    // room before it could move — and it moved.
    expect(scrolls.at(-1)).toBe(PIN_TARGET)
    // Exactly the room needed, once. Asking on a commit that does not carry the
    // spacer yet asks for it twice over, which is a scrollbar that lurches.
    expect(tailHeight()).toBe(EXPECTED_TAIL)
  })

  it("does not re-pin when the pending question is replaced by the committed one", () => {
    desk.entries = [...answered]
    const view = render(shell())

    desk.entries = [...answered, followUp]
    act(() => view.rerender(shell()))
    const afterAsking = scrolls.length

    // Two keys, one question. Re-anchoring on the swap would jump the page a
    // second time for nothing.
    desk.entries = [...answered, { ...followUp, key: "m2", pending: false }]
    act(() => view.rerender(shell()))

    expect(scrolls.length).toBe(afterAsking)
  })

  it("holds the transcript still while the answer streams in", () => {
    desk.entries = [...answered]
    const view = render(shell())

    desk.entries = [...answered, followUp]
    act(() => view.rerender(shell()))
    const landed = scrolls.length

    // The answer arriving under a pinned question: the spacer gives back what
    // the answer took, so the total height — and with it the question's place on
    // screen — does not change, and nothing scrolls again.
    desk.entries = [
      ...answered,
      followUp,
      {
        kind: "draft",
        key: "d1",
        text: "Phiên 21/08…",
        working: false,
        toolCalls: [],
        thoughts: [],
        elapsedMs: 0,
        phase: "running",
        terminalReason: null,
      },
    ]
    act(() => view.rerender(shell()))

    expect(tailHeight()).toBe(EXPECTED_TAIL)
    expect(scrolls.length).toBe(landed)
  })
})

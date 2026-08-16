/**
 * The replay contract, as the browser has to honour it.
 *
 * ADR-0013 states it in three sentences — a snapshot replaces, a duplicate is
 * ignored, a gap forces a fresh snapshot — and every one of them is a rule
 * about a sequence of events rather than about React, which is why the reducer
 * is pure and why this file needs no DOM.
 */

import { describe, expect, it } from "vitest"

import {
  IDLE,
  isActive,
  isSettled,
  liveTurnReducer,
  resendPlan,
  type LiveTurn,
  type LiveTurnAction,
} from "./live-turn"
import type { ContentBlock, TurnEvent, TurnEventType } from "./types"

const TURN = "11111111-2222-3333-4444-555555555555"
const THREAD = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

function block(text: string): ContentBlock {
  return { kind: "prose", text, symbol: null, trading_day: null, citations: [] }
}

function event(
  seq: number,
  type: TurnEventType,
  data: Record<string, unknown> = {},
): LiveTurnAction {
  return {
    type: "event",
    event: { version: 1, seq, type, turn_id: TURN, data } as TurnEvent,
  }
}

function snapshot(
  through: number,
  overrides: Partial<{
    status: string
    terminal_reason: string | null
    activity: string | null
    blocks: ContentBlock[]
    widgets: unknown[]
    message_id: number | null
  }> = {},
): LiveTurnAction {
  return event(through, "turn.snapshot", {
    through_seq: through,
    status: "running",
    terminal_reason: null,
    activity: null,
    blocks: [],
    widgets: [],
    message_id: null,
    ...overrides,
  })
}

function run(...actions: LiveTurnAction[]): LiveTurn {
  return actions.reduce(liveTurnReducer, IDLE)
}

const started: LiveTurnAction = { type: "start", turnId: TURN, threadId: THREAD }

describe("starting a Turn", () => {
  it("begins from nothing, so the previous answer is not shown twice", () => {
    // The finished Turn is already a canonical message in the transcript.
    const carried = run(started, snapshot(0), event(1, "content.block", { block: block("cũ") }))

    const fresh = liveTurnReducer(carried, {
      type: "start",
      turnId: "another",
      threadId: THREAD,
    })

    expect(fresh.blocks).toEqual([])
    expect(fresh.seq).toBe(0)
    expect(fresh.phase).toBe("starting")
    expect(fresh.turnId).toBe("another")
  })
})

describe("a snapshot", () => {
  it("replaces the projection instead of merging into it", () => {
    // Merging would duplicate every block on every reconnect.
    const state = run(
      started,
      snapshot(0),
      event(1, "content.block", { block: block("một") }),
      snapshot(2, { blocks: [block("một"), block("hai")] }),
    )

    expect(state.blocks.map((entry) => entry.text)).toEqual(["một", "hai"])
    expect(state.seq).toBe(2)
  })

  it("carries the sequence forward so the stream resumes past it", () => {
    const state = run(started, snapshot(7, { blocks: [block("đã có")] }))

    const next = liveTurnReducer(state, event(8, "content.block", { block: block("mới") }))

    expect(next.blocks.map((entry) => entry.text)).toEqual(["đã có", "mới"])
    expect(next.seq).toBe(8)
  })

  it("settles a Turn that was already terminal when the reader arrived", () => {
    // A fast Turn must not look like a dead one.
    const state = run(
      started,
      snapshot(3, { status: "complete", blocks: [block("xong")] }),
    )

    expect(state.phase).toBe("completed")
    expect(isSettled(state)).toBe(true)
    expect(state.blocks).toHaveLength(1)
  })

  it("reads an incomplete Turn with content as a partial answer, not a failure", () => {
    const partial = run(
      started,
      snapshot(3, {
        status: "incomplete",
        terminal_reason: "turn_deadline",
        blocks: [block("một phần"), block("thứ hai")],
      }),
    )
    const empty = run(
      started,
      snapshot(1, { status: "incomplete", terminal_reason: "turn_failed" }),
    )

    // The UI never replaces useful content with a full-screen error, so the
    // two have to be different states rather than one status with a caveat.
    expect(partial.phase).toBe("incomplete")
    expect(partial.terminalReason).toBe("turn_deadline")
    expect(empty.phase).toBe("failed")
  })

  it("does not take a pressed stop button back", () => {
    // The snapshot honestly says `running`, and the user honestly pressed stop.
    const state = run(started, snapshot(0), { type: "cancelling" }, snapshot(1))

    expect(state.phase).toBe("cancelling")
  })
})

describe("which block just arrived", () => {
  it("names the one a content event delivered, so only that one is revealed", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "content.block", { block: block("một") }),
      event(2, "content.block", { block: block("hai") }),
    )

    expect(state.appendedIndex).toBe(1)
  })

  it("names none after a snapshot, however many blocks it restated", () => {
    // A reconnect and a reopened Thread render everything present at once. A
    // renderer comparing block counts between frames cannot tell a snapshot of
    // one block from an event delivering one, so the reducer says which it was.
    const state = run(started, snapshot(4, { blocks: [block("một")] }))

    expect(state.blocks).toHaveLength(1)
    expect(state.appendedIndex).toBeNull()
  })

  it("names none after an activity, so a block on screen does not re-arrive", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "content.block", { block: block("một") }),
      event(2, "turn.activity", { phase: "analyzing" }),
    )

    expect(state.appendedIndex).toBeNull()
  })
})

describe("a terminal snapshot", () => {
  it("names the message that replaces the draft, as the terminal event does", () => {
    // A reader arriving *after* the Turn ended gets a snapshot rather than a
    // terminal event. Without the id it would hold a draft it could never hand
    // over, and the answer would render twice — once without its Risk Notice.
    const state = run(
      started,
      snapshot(3, { status: "complete", blocks: [block("xong")], message_id: 42 }),
    )

    expect(state.phase).toBe("completed")
    expect(state.messageId).toBe(42)
  })

  it("leaves a message id the stream already gave alone", () => {
    const settled = run(
      started,
      snapshot(0),
      event(1, "turn.completed", { terminal_reason: null, message_id: 7 }),
    )

    expect(liveTurnReducer(settled, snapshot(1, { status: "complete" })).messageId).toBe(7)
  })
})

describe("a duplicate", () => {
  it("is ignored rather than applied a second time", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "content.block", { block: block("một") }),
      event(1, "content.block", { block: block("một") }),
    )

    expect(state.blocks).toHaveLength(1)
    expect(state.seq).toBe(1)
  })

  it("is ignored when a reconnect redelivers everything below the snapshot", () => {
    const state = run(
      started,
      snapshot(4, { blocks: [block("một"), block("hai")] }),
      event(3, "content.block", { block: block("hai") }),
      event(4, "turn.activity", { phase: "analyzing" }),
    )

    expect(state.blocks).toHaveLength(2)
    expect(state.activity).toBeNull()
  })
})

describe("a gap", () => {
  it("is not patched over — it asks for a fresh snapshot", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "content.block", { block: block("một") }),
      event(3, "content.block", { block: block("ba") }),
    )

    // The missing event cannot be reconstructed from what is here, so nothing
    // pretends it can be.
    expect(state.needsResync).toBe(true)
    expect(state.blocks.map((entry) => entry.text)).toEqual(["một"])
    expect(state.seq).toBe(1)
  })

  it("is cleared only by the snapshot that answers it", () => {
    const gapped = run(
      started,
      snapshot(0),
      event(2, "content.block", { block: block("hai") }),
    )

    const resynced = liveTurnReducer(
      liveTurnReducer(gapped, { type: "resynced" }),
      snapshot(2, { blocks: [block("một"), block("hai")] }),
    )

    expect(resynced.needsResync).toBe(false)
    expect(resynced.blocks).toHaveLength(2)
    expect(resynced.seq).toBe(2)
  })

  it("treats an unparseable frame the same way, because it is the same thing", () => {
    const state = run(started, snapshot(0), { type: "gap" })

    expect(state.needsResync).toBe(true)
  })
})

describe("the four terminal meanings", () => {
  const cases: Array<[TurnEventType, LiveTurn["phase"]]> = [
    ["turn.completed", "completed"],
    ["turn.incomplete", "incomplete"],
    ["turn.failed", "failed"],
    ["turn.cancelled", "cancelled"],
  ]

  it.each(cases)("%s settles as %s", (type, phase) => {
    const state = run(
      started,
      snapshot(0),
      event(1, type, { status: "x", terminal_reason: "why", message_id: 42 }),
    )

    expect(state.phase).toBe(phase)
    expect(state.terminalReason).toBe("why")
    // The message the client refetches the Thread for.
    expect(state.messageId).toBe(42)
    expect(isActive(state)).toBe(false)
  })

  it("keeps every block a cancelled Turn had already delivered", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "content.block", { block: block("giữ lại") }),
      { type: "cancelling" },
      event(2, "turn.cancelled", { terminal_reason: "cancelled_by_user" }),
    )

    expect(state.phase).toBe("cancelled")
    expect(state.blocks.map((entry) => entry.text)).toEqual(["giữ lại"])
  })
})

describe("settling from the Turn row", () => {
  it("applies whatever the sequence says, because the stream stopped speaking", () => {
    // The row is authoritative precisely when the stream is not, so holding
    // this to a rule about stream ordering would leave the UI spinning.
    const state = run(
      started,
      snapshot(9, { blocks: [block("một phần")] }),
      {
        type: "settled",
        status: "incomplete",
        terminalReason: "interrupted_restart",
        messageId: 7,
      },
    )

    expect(state.phase).toBe("incomplete")
    expect(state.terminalReason).toBe("interrupted_restart")
    expect(state.blocks).toHaveLength(1)
  })

  it("cannot overwrite a terminal state the stream already delivered", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "turn.completed", { terminal_reason: null, message_id: 3 }),
      { type: "settled", status: "incomplete", terminalReason: "late", messageId: 9 },
    )

    expect(state.phase).toBe("completed")
    expect(state.messageId).toBe(3)
  })
})

describe("the activity line", () => {
  it("shows a phase while tools run and clears when a block lands", () => {
    const working = run(started, snapshot(0), event(1, "turn.activity", { phase: "searching" }))
    const answered = liveTurnReducer(
      working,
      event(2, "content.block", { block: block("kết quả") }),
    )

    expect(working.activity).toBe("searching")
    expect(answered.activity).toBeNull()
  })

  it("keeps a finished phase as a step, in the order it finished", () => {
    // The transport publishes where the Turn *is*; the trail of where it has
    // been is assembled here, because nothing else sees every transition.
    const state = run(
      started,
      snapshot(0),
      event(1, "turn.activity", { phase: "searching" }),
      event(2, "turn.activity", { phase: "reading_data" }),
      event(3, "turn.activity", { phase: "analyzing" }),
    )

    expect(state.steps).toEqual(["searching", "reading_data"])
    expect(state.activity).toBe("analyzing")
  })

  it("closes the running phase into the trail when a block lands", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "turn.activity", { phase: "reading_data" }),
      event(2, "content.block", { block: block("kết quả") }),
    )

    expect(state.steps).toEqual(["reading_data"])
    expect(state.activity).toBeNull()
  })

  it("collapses a phase re-announced back to back into one step", () => {
    // Two reads in a row are one step called *reading data*, not two.
    const state = run(
      started,
      snapshot(0),
      event(1, "turn.activity", { phase: "reading_data" }),
      event(2, "turn.activity", { phase: "reading_data" }),
      event(3, "turn.activity", { phase: "analyzing" }),
    )

    expect(state.steps).toEqual(["reading_data"])
  })

  it("keeps the trail after the Turn ends, including one that ended early", () => {
    // On a Turn that stopped early the trail is most of what the reader has to
    // go on, so it outlives the running state.
    const state = run(
      started,
      snapshot(0),
      event(1, "turn.activity", { phase: "searching" }),
      event(2, "turn.incomplete", { terminal_reason: "turn_deadline" }),
    )

    expect(state.steps).toEqual(["searching"])
    expect(state.activity).toBeNull()
  })

  it("starts a new Turn with an empty trail", () => {
    const state = run(
      started,
      snapshot(0),
      event(1, "turn.activity", { phase: "searching" }),
      { type: "start", turnId: "another", threadId: THREAD },
    )

    expect(state.steps).toEqual([])
  })
})

describe("an event from another Turn", () => {
  it("is dropped, so a retry's stream cannot write into the new one", () => {
    const state = run(started, snapshot(0))

    const stray = liveTurnReducer(state, {
      type: "event",
      event: {
        version: 1,
        seq: 1,
        type: "content.block",
        turn_id: "a-different-turn",
        data: { block: block("của Turn khác") },
      },
    })

    expect(stray.blocks).toEqual([])
  })
})

describe("when the stream may be opened", () => {
  /**
   * The Turn has to exist before anything subscribes to it.
   *
   * `EventSource` does not reconnect after a non-200 response — the spec calls
   * that failing the connection — so a subscribe that raced the create and got
   * a 404 leaves the surface watching a stream that will never speak. Found by
   * the end-to-end acceptance (#92), where it happens on every send: the id is
   * generated locally and the create is a network round trip behind it.
   */
  it("is not open on an id the backend has not admitted yet", () => {
    const state = run(started)

    expect(state.turnId).toBe(TURN)
    expect(state.subscribable).toBe(false)
  })

  it("is open once the create came back", () => {
    const state = run(started, { type: "admitted" })

    expect(state.subscribable).toBe(true)
  })

  it("is open immediately when reattaching to a Turn that already exists", () => {
    // A reload does not create anything: the Turn is on the backend already,
    // and waiting for an admission that will never come would strand the tab.
    const state = run({
      type: "start",
      turnId: TURN,
      threadId: THREAD,
      subscribable: true,
    })

    expect(state.subscribable).toBe(true)
  })

  it("closes again when the next Turn starts", () => {
    const state = run(started, { type: "admitted" }, {
      type: "start",
      turnId: "another",
      threadId: THREAD,
    })

    expect(state.subscribable).toBe(false)
  })
})

describe("asking a question in the transcript again", () => {
  const settled = (phase: LiveTurn["phase"]): LiveTurn => ({ ...IDLE, phase })

  it("retries the last question when its Turn ended badly", () => {
    // Hung, failed or cancelled: a second attempt, linked to the first by
    // `retry_of_turn_id`.
    expect(resendPlan(settled("failed"), true)).toBe("retry")
    expect(resendPlan(settled("incomplete"), true)).toBe("retry")
    expect(resendPlan(settled("cancelled"), true)).toBe("retry")
  })

  it("asks it fresh when the last Turn answered", () => {
    // Not a retry: claiming a second attempt at a Turn that already answered
    // would make the lifecycle say something false.
    expect(resendPlan(settled("completed"), true)).toBe("submit")
  })

  it("asks any earlier question fresh, whatever the last Turn did", () => {
    expect(resendPlan(settled("failed"), false)).toBe("submit")
  })

  it("sends nothing at all while a Turn is in flight", () => {
    // The composer offers Stop rather than Send for exactly this stretch.
    expect(resendPlan(settled("starting"), true)).toBe("nothing")
    expect(resendPlan(settled("running"), false)).toBe("nothing")
  })
})

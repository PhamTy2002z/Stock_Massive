/**
 * The replay contract, as a sequence of events rather than as a rendered tree.
 *
 * Every assertion here is about what a reader ends up holding after a stream
 * misbehaves: a delta redelivered, a delta missed, a reconnect restating an
 * answer that is already on screen. The reducer is pure precisely so those
 * three can be stated without a browser.
 */

import { describe, expect, it } from "vitest"

import {
  IDLE,
  isActive,
  isSettled,
  liveTurnReducer,
  resendPlan,
  type LiveTurn,
} from "./live-turn"
import { TURN_EVENT_VERSION, type TurnEvent, type TurnEventType } from "./types"

const TURN = "turn-1"
const THREAD = "thread-1"

function event(
  type: TurnEventType,
  seq: number,
  data: Record<string, unknown> = {},
  turnId: string = TURN,
): TurnEvent {
  return { version: TURN_EVENT_VERSION, seq, type, turn_id: turnId, data }
}

function started(): LiveTurn {
  return liveTurnReducer(IDLE, { type: "start", turnId: TURN, threadId: THREAD })
}

function apply(state: LiveTurn, ...events: TurnEvent[]): LiveTurn {
  return events.reduce((next, one) => liveTurnReducer(next, { type: "event", event: one }), state)
}

function delta(seq: number, text: string): TurnEvent {
  return event("content.delta", seq, { text })
}

describe("admission", () => {
  it("does not let a subscriber open a stream until the create came back", () => {
    const state = started()
    expect(state.phase).toBe("starting")
    expect(state.subscribable).toBe(false)
    expect(liveTurnReducer(state, { type: "admitted" }).subscribable).toBe(true)
  })

  it("opens the stream at once when reattaching, because that Turn already exists", () => {
    const state = liveTurnReducer(IDLE, {
      type: "start",
      turnId: TURN,
      threadId: THREAD,
      subscribable: true,
    })
    expect(state.subscribable).toBe(true)
  })

  it("starts a new Turn from nothing, so the previous answer is not shown twice", () => {
    const finished = apply(started(), delta(1, "câu trả lời cũ"), event("turn.completed", 2))
    const next = liveTurnReducer(finished, {
      type: "start",
      turnId: "turn-2",
      threadId: THREAD,
    })
    expect(next.text).toBe("")
    expect(next.seq).toBe(0)
    expect(next.phase).toBe("starting")
  })
})

describe("content deltas", () => {
  it("joins them into one string, in the order they arrived", () => {
    const state = apply(started(), delta(1, "Xin "), delta(2, "chào "), delta(3, "bạn"))
    expect(state.text).toBe("Xin chào bạn")
    expect(state.seq).toBe(3)
  })

  it("advances the sequence on a delta carrying nothing, and adds nothing", () => {
    const state = apply(started(), delta(1, "một"), delta(2, ""))
    expect(state.text).toBe("một")
    expect(state.seq).toBe(2)
  })

  it("ignores a redelivered delta rather than printing it twice", () => {
    const state = apply(started(), delta(1, "một"), delta(2, " hai"), delta(2, " hai"))
    expect(state.text).toBe("một hai")
    expect(state.seq).toBe(2)
  })

  it("asks for a resync on a gap instead of stitching the hole shut", () => {
    const state = apply(started(), delta(1, "một"), delta(3, " ba"))
    expect(state.needsResync).toBe(true)
    // The missing sentence is not reconstructable, so nothing was applied.
    expect(state.text).toBe("một")
    expect(state.seq).toBe(1)
  })

  it("ignores an event belonging to a Turn it is not showing", () => {
    const state = apply(started(), delta(1, "một"), event("content.delta", 2, { text: " hai" }, "turn-9"))
    expect(state.text).toBe("một")
    expect(state.seq).toBe(1)
  })
})

describe("tool calls", () => {
  it("updates a call in place when its outcome arrives", () => {
    const state = apply(
      started(),
      event("tool.call", 1, { id: "a", name: "web_search", status: "running", summary: "Đang tìm" }),
      event("tool.call", 2, { id: "a", name: "web_search", status: "ok", summary: "Đã tìm" }),
    )
    expect(state.toolCalls).toEqual([
      {
        id: "a",
        name: "web_search",
        status: "ok",
        summary: "Đã tìm",
        round: 0,
        error: null,
        result_count: 0,
        results: [],
        kind: "external",
      },
    ])
  })

  it("carries the reason a call failed, and drops a blank one", () => {
    // The reason is what lets the surface tell a ceiling of ours apart from a
    // tool that broke. A payload with no reason is not an error about nothing:
    // it is a call whose status is all there is to say.
    const state = apply(
      started(),
      event("tool.call", 1, {
        id: "a",
        name: "web_search",
        status: "error",
        summary: "Tìm trên web: x",
        error: "external_budget_exhausted",
      }),
      event("tool.call", 2, {
        id: "b",
        name: "fetch_url",
        status: "error",
        summary: "Đọc trang: y",
        error: "",
      }),
    )

    expect(state.toolCalls.map((call) => call.error)).toEqual([
      "external_budget_exhausted",
      null,
    ])
  })

  it("keeps several calls in the order they first appeared", () => {
    const state = apply(
      started(),
      event("tool.call", 1, { id: "a", name: "web_search", status: "running", summary: "một" }),
      event("tool.call", 2, { id: "b", name: "fetch_url", status: "running", summary: "hai" }),
      event("tool.call", 3, { id: "a", name: "web_search", status: "ok", summary: "một" }),
    )
    expect(state.toolCalls.map((call) => call.id)).toEqual(["a", "b"])
    expect(state.toolCalls.map((call) => call.status)).toEqual(["ok", "running"])
  })

  it("reads a call with no id as no call, because nothing could ever update it", () => {
    const state = apply(started(), event("tool.call", 1, { name: "web_search", status: "ok" }))
    expect(state.toolCalls).toEqual([])
    expect(state.seq).toBe(1)
  })

  it("falls back to the tool's name when no summary was sent, and to running on an unknown status", () => {
    const state = apply(started(), event("tool.call", 1, { id: "a", name: "recall_facts" }))
    expect(state.toolCalls).toEqual([
      {
        id: "a",
        name: "recall_facts",
        status: "running",
        summary: "recall_facts",
        round: 0,
        error: null,
        result_count: 0,
        results: [],
        // A payload with no kind reads as outside content, which is the safe
        // direction and the one the backend's own default leans.
        kind: "external",
      },
    ])
  })

  it("carries the sources a call turned up, and the count the backend reported", () => {
    const state = apply(
      started(),
      event("tool.call", 1, {
        id: "a",
        name: "web_search",
        status: "ok",
        summary: "Tìm trên web: AI",
        round: 2,
        result_count: 15,
        results: [
          {
            title: "Technology + AI",
            url: "https://theguardian.com/x",
            source: "theguardian.com",
            snippet: "Skip to main content",
          },
        ],
      }),
    )
    const [call] = state.toolCalls
    expect(call.round).toBe(2)
    // The backend caps what it sends, so a count larger than the list is the
    // truth about the search rather than a bug in the list.
    expect(call.result_count).toBe(15)
    expect(call.results).toHaveLength(1)
    expect(call.results[0].source).toBe("theguardian.com")
  })

  it("keeps a call written down before its effect ran as the pending it is", () => {
    // `pending` and `running` are both calls that have not come back, and the
    // surface draws them alike — but only one of them says the intent was
    // checkpointed before anything ran, so the status is kept as it arrived.
    const state = apply(
      started(),
      event("tool.call", 1, {
        id: "a",
        name: "remember_fact",
        status: "pending",
        summary: "Ghi lại: STB",
      }),
      event("tool.call", 2, {
        id: "a",
        name: "remember_fact",
        status: "ok",
        summary: "Ghi lại: STB",
      }),
    )
    expect(state.toolCalls.map((call) => call.status)).toEqual(["ok"])
  })

  it("keeps a refused call as denied, with the code that says why", () => {
    // Not folded into `error`: a permission rule that closed the route is the
    // one failure pressing again cannot fix.
    const state = apply(
      started(),
      event("tool.call", 1, {
        id: "a",
        name: "web_search",
        status: "denied",
        summary: "Tìm trên web: x",
        error: "permission_denied",
      }),
    )
    expect(state.toolCalls[0].status).toBe("denied")
    expect(state.toolCalls[0].error).toBe("permission_denied")
  })

  it("drops a result that is neither titled nor linked, rather than drawing a blank row", () => {
    const state = apply(
      started(),
      event("tool.call", 1, {
        id: "a",
        name: "web_search",
        status: "ok",
        results: [{ snippet: "orphan" }, { title: "kept", url: "https://x.test" }],
      }),
    )
    expect(state.toolCalls[0].results.map((result) => result.title)).toEqual(["kept"])
  })
})

describe("a desk view", () => {
  const SIGNAL_DESK = {
    artifactId: "artifact-1",
    studyName: "intraday_liquidity_profile",
    studyDisplayName: "Thanh khoản trong phiên",
    title: "Thanh khoản trong phiên — STB",
    blockCount: 4,
    round: 0,
    symbol: "STB",
    asOf: "2026-08-28T09:00:00+07:00",
  }

  it("is remembered by the id the panel will fetch it with", () => {
    const state = apply(started(), event("signal_desk.ready", 1, SIGNAL_DESK))

    expect(state.deskViews).toEqual([SIGNAL_DESK])
    expect(state.seq).toBe(1)
  })

  it("is replaced rather than duplicated when it is announced twice", () => {
    // One Study run has one id, so a second announcement is a republish. The
    // sequence still advances: both events happened.
    const state = apply(
      started(),
      event("signal_desk.ready", 1, SIGNAL_DESK),
      event("signal_desk.ready", 2, { ...SIGNAL_DESK, title: "Đã đổi tên" }),
    )

    expect(state.deskViews).toHaveLength(1)
    expect(state.deskViews[0].title).toBe("Đã đổi tên")
    expect(state.seq).toBe(2)
  })

  it("is dropped when it names no artifact, because a card with no id opens nothing", () => {
    const state = apply(started(), event("signal_desk.ready", 1, { title: "Không có id" }))

    expect(state.deskViews).toEqual([])
    expect(state.seq).toBe(1)
  })

  it("survives a reconnect, because a snapshot restates it", () => {
    const state = apply(
      started(),
      event("signal_desk.ready", 1, SIGNAL_DESK),
      event("turn.snapshot", 0, {
        through_seq: 5,
        status: "running",
        terminal_reason: null,
        text: "Thanh khoản STB",
        tool_calls: [],
        signal_desks: [SIGNAL_DESK],
        message_id: null,
      }),
    )

    expect(state.deskViews).toEqual([SIGNAL_DESK])
  })

  it("is gone from a snapshot that names none, because a snapshot replaces", () => {
    const state = apply(
      started(),
      event("signal_desk.ready", 1, SIGNAL_DESK),
      event("turn.snapshot", 0, {
        through_seq: 5,
        status: "running",
        terminal_reason: null,
        text: "",
        tool_calls: [],
        message_id: null,
      }),
    )

    expect(state.deskViews).toEqual([])
  })
})

describe("narration", () => {
  const thought = (seq: number, text: string, round = 0) =>
    event("content.delta", seq, { text, kind: "thought", round })

  it("keeps a thought out of the answer", () => {
    const state = apply(started(), thought(1, "Đang tra tin"), delta(2, "Xong."))
    expect(state.text).toBe("Xong.")
    expect(state.thoughts).toEqual([{ round: 0, text: "Đang tra tin" }])
  })

  it("joins two deltas of one round into the one sentence they are", () => {
    const state = apply(started(), thought(1, "Đang tra "), thought(2, "tin hôm nay"))
    expect(state.thoughts).toEqual([{ round: 0, text: "Đang tra tin hôm nay" }])
  })

  it("keeps each round's narration on its own line", () => {
    const state = apply(started(), thought(1, "một", 0), thought(2, "hai", 1))
    expect(state.thoughts).toEqual([
      { round: 0, text: "một" },
      { round: 1, text: "hai" },
    ])
  })

  it("treats a delta with no kind as the answer, because that is where it shows", () => {
    const state = apply(started(), event("content.delta", 1, { text: "Xong." }))
    expect(state.text).toBe("Xong.")
    expect(state.thoughts).toEqual([])
  })
})

describe("the progress trail", () => {
  const part = (seq: number, overrides: Record<string, unknown> = {}) =>
    event("part.progress", seq, {
      seq,
      kind: "tool_round",
      round: seq - 1,
      payload: { calls: 1, external_used: seq },
      at: "2026-09-01T09:00:00+00:00",
      ...overrides,
    })

  it("keeps every part in the order the loop emitted them", () => {
    const state = apply(
      started(),
      part(1, { kind: "lane_selected", round: 0, payload: { lane: "light" } }),
      part(2, { kind: "model_attempt", payload: { status: "running" } }),
      part(3),
    )
    expect(state.progress.map((entry) => entry.kind)).toEqual([
      "lane_selected",
      "model_attempt",
      "tool_round",
    ])
    expect(state.progress.map((entry) => entry.seq)).toEqual([1, 2, 3])
  })

  it("orders the trail by the parts' own count rather than by arrival", () => {
    // The two counts are different things: the publisher's sequence advances on
    // every delta, and a reader reading the trail wants the parts' own order.
    const state = apply(started(), part(1, { seq: 9 }), part(2, { seq: 4 }))
    expect(state.progress.map((entry) => entry.seq)).toEqual([4, 9])
  })

  it("carries the payload as it arrived, without inventing a shape for it", () => {
    const state = apply(
      started(),
      part(1, { kind: "recovery", payload: { action: "compress", attempt: 1, bound: 2 } }),
    )
    expect(state.progress[0].payload).toEqual({ action: "compress", attempt: 1, bound: 2 })
    expect(state.progress[0].at).toBe("2026-09-01T09:00:00+00:00")
  })

  it("draws no row for a kind nobody designed one for", () => {
    const state = apply(started(), part(1, { kind: "vibes" }))
    expect(state.progress).toEqual([])
    // The event still counted: the trail lost a row, not the sequence.
    expect(state.seq).toBe(1)
  })

  it("tolerates a part carrying a key this build has never heard of", () => {
    const state = apply(started(), part(1, { lane_hint: "deep" }))
    expect(state.progress).toHaveLength(1)
    expect(state.progress[0]).not.toHaveProperty("lane_hint")
  })
})

describe("the question a Turn ends by asking", () => {
  const card = (overrides: Record<string, unknown> = {}) => ({
    question_id: "q-1",
    prompt: "Bạn đang quyết định gì?",
    options: [
      { id: "hold", label: "Giữ", detail: null },
      { id: "add", label: "Mua thêm", detail: "Trong 3 tháng" },
    ],
    multi_select: false,
    skip_label: "Bỏ qua",
    state: "pending",
    selected_option_ids: null,
    ...overrides,
  })

  it("holds the card so a reader watching live can answer it", () => {
    const state = apply(started(), event("part.question", 1, card()))
    expect(state.question?.question_id).toBe("q-1")
    expect(state.question?.state).toBe("pending")
    expect(state.question?.options.map((option) => option.label)).toEqual([
      "Giữ",
      "Mua thêm",
    ])
    // Nothing is chosen at the moment of asking, and null says so where an empty
    // list would read as a skip.
    expect(state.question?.selected_option_ids).toBeNull()
  })

  it("refuses a card with nothing answerable on it", () => {
    // A card is a dead end unless there are at least two ways out of it, which
    // is the same rule the backend applies when it builds one.
    const state = apply(
      started(),
      event("part.question", 1, card({ options: [{ id: "hold", label: "Giữ" }] })),
    )
    expect(state.question).toBeNull()
    expect(state.seq).toBe(1)
  })

  it("keeps the card across a reconnect, because a snapshot from a draft has none", () => {
    // A snapshot rebuilt out of a checkpoint always says null: the outcome
    // changes after the Turn ended, so it is read from the transcript rather
    // than from a draft. Clearing on that would take the card off screen from
    // the one reader who was looking at it.
    const asked = apply(started(), event("part.question", 1, card()))
    const state = apply(
      asked,
      event("turn.snapshot", 0, {
        through_seq: 1,
        status: "complete",
        terminal_reason: null,
        text: "Cần biết thêm một điều.",
        tool_calls: [],
        progress: [],
        question: null,
        message_id: 11,
      }),
    )
    expect(state.question?.question_id).toBe("q-1")
  })
})

describe("a snapshot", () => {
  const snapshot = (data: Record<string, unknown>) => event("turn.snapshot", 0, data)

  it("restates the narration and the clock a reconnecting tab missed", () => {
    const state = apply(
      started(),
      snapshot({
        through_seq: 6,
        status: "running",
        terminal_reason: null,
        text: "Đang trả lời",
        thoughts: [
          { round: 0, text: "Đang tra tin" },
          { round: 1, text: "Đang tổng hợp" },
        ],
        tool_calls: [],
        message_id: null,
        elapsed_ms: 8200,
      }),
    )
    expect(state.thoughts).toHaveLength(2)
    // The Turn's clock, not this tab's: a reader who joined late is told how
    // long the work took, not how long they have been watching it.
    expect(state.elapsedMs).toBe(8200)
  })

  it("replaces the answer rather than merging into it", () => {
    const state = apply(
      started(),
      delta(1, "một"),
      snapshot({
        through_seq: 4,
        status: "running",
        terminal_reason: null,
        text: "một hai ba",
        tool_calls: [{ id: "a", name: "web_search", status: "ok", summary: "Đã tìm" }],
        message_id: null,
      }),
    )
    expect(state.text).toBe("một hai ba")
    expect(state.seq).toBe(4)
    expect(state.toolCalls).toHaveLength(1)
    expect(state.needsResync).toBe(false)
  })

  it("replaces the progress trail wholesale rather than appending to it", () => {
    const trail = [
      {
        seq: 1,
        kind: "lane_selected",
        round: 0,
        payload: { lane: "light", reason: "default" },
        at: "2026-09-01T09:00:00+00:00",
      },
      {
        seq: 2,
        kind: "tool_round",
        round: 0,
        payload: { calls: 2, external_used: 2 },
        at: "2026-09-01T09:00:03+00:00",
      },
    ]
    const state = apply(
      started(),
      event("part.progress", 1, trail[0]),
      snapshot({
        through_seq: 4,
        status: "running",
        terminal_reason: null,
        text: "một",
        tool_calls: [],
        progress: trail,
        message_id: null,
      }),
    )
    // Two rows and not three: the snapshot restates the trail that was
    // published, so merging would show every step twice per reconnect.
    expect(state.progress.map((part) => part.seq)).toEqual([1, 2])
  })

  it("hands a reader who joined after the question the card they missed", () => {
    const state = apply(
      started(),
      snapshot({
        through_seq: 5,
        status: "complete",
        terminal_reason: null,
        text: "Cần biết thêm một điều.",
        tool_calls: [],
        progress: [],
        question: {
          question_id: "q-1",
          prompt: "Bạn đang quyết định gì?",
          options: [
            { id: "hold", label: "Giữ" },
            { id: "add", label: "Mua thêm" },
          ],
          multi_select: false,
          skip_label: "Bỏ qua",
          state: "pending",
          selected_option_ids: null,
        },
        message_id: 9,
      }),
    )
    expect(state.question?.prompt).toBe("Bạn đang quyết định gì?")
    expect(state.phase).toBe("completed")
  })

  it("is applied whatever its seq says, because it restates rather than replays", () => {
    const state = apply(
      started(),
      delta(1, "một"),
      delta(2, " hai"),
      snapshot({
        through_seq: 2,
        status: "running",
        terminal_reason: null,
        text: "một hai",
        tool_calls: [],
        message_id: null,
      }),
    )
    expect(state.text).toBe("một hai")
    expect(state.phase).toBe("running")
  })

  it("names the message that replaces the draft when it arrives after the Turn ended", () => {
    const state = apply(
      started(),
      snapshot({
        through_seq: 7,
        status: "complete",
        terminal_reason: null,
        text: "xong",
        tool_calls: [],
        message_id: 42,
      }),
    )
    expect(state.phase).toBe("completed")
    expect(state.messageId).toBe(42)
    expect(isSettled(state)).toBe(true)
  })

  it("reads an incomplete Turn that said nothing as the failure it is", () => {
    const state = apply(
      started(),
      snapshot({
        through_seq: 1,
        status: "incomplete",
        terminal_reason: "turn_deadline",
        text: "",
        tool_calls: [],
        message_id: null,
      }),
    )
    expect(state.phase).toBe("failed")
    expect(state.terminalReason).toBe("turn_deadline")
  })

  it("keeps a Turn the user stopped reading as cancelling until it actually ends", () => {
    const cancelling = liveTurnReducer(started(), { type: "cancelling" })
    const state = apply(
      cancelling,
      snapshot({
        through_seq: 2,
        status: "running",
        terminal_reason: null,
        text: "một",
        tool_calls: [],
        message_id: null,
      }),
    )
    expect(state.phase).toBe("cancelling")
  })
})

describe("the four endings", () => {
  it.each([
    ["turn.completed", "completed"],
    ["turn.incomplete", "incomplete"],
    ["turn.failed", "failed"],
    ["turn.cancelled", "cancelled"],
  ] as const)("%s settles the Turn as %s", (type, phase) => {
    const state = apply(started(), delta(1, "một"), event(type, 2, { message_id: 7 }))
    expect(state.phase).toBe(phase)
    expect(state.messageId).toBe(7)
    expect(isSettled(state)).toBe(true)
    // Whatever the ending, what the reader was shown stays on screen.
    expect(state.text).toBe("một")
  })

  it("carries the stable reason so the surface can say it in a sentence", () => {
    const state = apply(started(), event("turn.incomplete", 1, { terminal_reason: "turn_deadline" }))
    expect(state.terminalReason).toBe("turn_deadline")
  })
})

describe("settling from the Turn row", () => {
  it("applies without regard to the stream's sequence, because the stream stopped speaking", () => {
    const state = liveTurnReducer(apply(started(), delta(1, "một")), {
      type: "settled",
      status: "incomplete",
      terminalReason: "shutdown",
      messageId: null,
    })
    expect(state.phase).toBe("incomplete")
    expect(state.terminalReason).toBe("shutdown")
  })

  it("reads an incomplete Turn with nothing to keep as failed", () => {
    const state = liveTurnReducer(started(), {
      type: "settled",
      status: "incomplete",
      terminalReason: "turn_failed",
      messageId: null,
    })
    expect(state.phase).toBe("failed")
  })

  it("does not overwrite an ending the stream already delivered", () => {
    const completed = apply(started(), event("turn.completed", 1, { message_id: 5 }))
    const state = liveTurnReducer(completed, {
      type: "settled",
      status: "cancelled",
      terminalReason: "cancelled_by_user",
      messageId: null,
    })
    expect(state).toBe(completed)
  })
})

describe("cancelling, resync and reset", () => {
  it("shows the stop immediately and keeps every word already received", () => {
    const state = liveTurnReducer(apply(started(), delta(1, "một")), { type: "cancelling" })
    expect(state.phase).toBe("cancelling")
    expect(state.text).toBe("một")
    expect(isActive(state)).toBe(false)
  })

  it("ignores a stop pressed on a Turn that already ended", () => {
    const completed = apply(started(), event("turn.completed", 1))
    expect(liveTurnReducer(completed, { type: "cancelling" })).toBe(completed)
  })

  it("clears the resync flag once, so the stream is reopened once", () => {
    const gapped = liveTurnReducer(started(), { type: "gap" })
    const cleared = liveTurnReducer(gapped, { type: "resynced" })
    expect(cleared.needsResync).toBe(false)
    expect(liveTurnReducer(cleared, { type: "resynced" })).toBe(cleared)
  })

  it("treats an unparseable frame as the missed event it is indistinguishable from", () => {
    expect(liveTurnReducer(started(), { type: "gap" }).needsResync).toBe(true)
    // Nothing to resync when there is no Turn on screen.
    expect(liveTurnReducer(IDLE, { type: "gap" })).toBe(IDLE)
  })

  it("resets to idle", () => {
    expect(liveTurnReducer(apply(started(), delta(1, "một")), { type: "reset" })).toEqual(IDLE)
  })
})

describe("what asking again means", () => {
  it("sends nothing while a Turn is in flight", () => {
    expect(resendPlan(started(), true)).toBe("nothing")
  })

  it("links a second attempt at the last question, and only after a bad ending", () => {
    const failed = apply(started(), event("turn.failed", 1))
    expect(resendPlan(failed, true)).toBe("retry")
    expect(resendPlan(failed, false)).toBe("submit")
  })

  it("treats repeating an answered question as a new question", () => {
    const completed = apply(started(), delta(1, "một"), event("turn.completed", 2))
    expect(resendPlan(completed, true)).toBe("submit")
  })
})

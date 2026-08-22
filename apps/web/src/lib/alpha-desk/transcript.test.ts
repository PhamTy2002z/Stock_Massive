/**
 * Where the draft ends and history begins.
 *
 * The transcript is the one place the two halves of the client meet, and every
 * claim here is one a reasonable implementation gets wrong by merging them: the
 * draft shown next to its own canonical message, the pending question left on
 * screen after the real one committed, a Turn that failed with nothing
 * disappearing along with its retry.
 */

import { describe, expect, it } from "vitest"

import { IDLE, type LiveTurn } from "./live-turn"
import { buildTranscript, type TranscriptInput } from "./transcript"
import type { FlagReason, ThreadMessage, ToolCall } from "./types"

const THREAD = "11111111-1111-4111-8111-111111111111"
const TURN = "22222222-2222-4222-8222-222222222222"

function call(id: string, status: ToolCall["status"] = "ok"): ToolCall {
  return { id, name: "web_search", status, summary: "Đã tìm trên web" }
}

function userMessage(id: number, text: string): ThreadMessage {
  return {
    id,
    seq: id,
    role: "user",
    content: { text },
    created_at: "2026-08-22T09:00:00Z",
    flagged_reason: null,
    flagged_at: null,
  }
}

function assistantMessage(
  id: number,
  text: string,
  flag: FlagReason | null = null,
): ThreadMessage {
  return {
    id,
    seq: id,
    role: "assistant",
    content: { text, tool_calls: [] },
    created_at: "2026-08-22T09:00:05Z",
    flagged_reason: flag,
    flagged_at: flag === null ? null : "2026-08-22T10:00:00Z",
  }
}

/** A stored answer with whatever the JSONB column happened to hold. */
function withContent(extra: Record<string, unknown>): ThreadMessage {
  const message = assistantMessage(1, "đáp")
  return { ...message, content: { ...message.content, ...extra } }
}

function live(overrides: Partial<LiveTurn> = {}): LiveTurn {
  return { ...IDLE, turnId: TURN, threadId: THREAD, phase: "running", ...overrides }
}

function transcript(overrides: Partial<TranscriptInput> = {}) {
  return buildTranscript({
    threadId: THREAD,
    messages: [],
    live: IDLE,
    pendingUserText: null,
    ...overrides,
  })
}

describe("the canonical Thread", () => {
  it("renders messages in sequence order, not in arrival order", () => {
    const entries = transcript({
      messages: [assistantMessage(2, "đáp"), userMessage(1, "hỏi")],
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "assistant"])
  })

  it("skips a summary, which is context rather than conversation", () => {
    const summary: ThreadMessage = {
      id: 3,
      seq: 3,
      role: "summary",
      content: { text: "earlier Turns, compacted" },
      created_at: "2026-08-22T09:00:00Z",
      flagged_reason: null,
      flagged_at: null,
    }

    expect(transcript({ messages: [summary] })).toHaveLength(0)
  })

  it("carries the answer's whole text, which is what the message stores", () => {
    const [entry] = transcript({ messages: [assistantMessage(1, "một đoạn văn xuôi")] })

    expect(entry.kind === "assistant" && entry.view.text).toBe("một đoạn văn xuôi")
  })

  it("carries a flag already on the message, so a reopened Thread shows it", () => {
    // Otherwise the action looks unpressed after a reload and the reader presses
    // it a second time — which the backend would take as a correction.
    const [entry] = transcript({ messages: [assistantMessage(1, "đáp", "wrong_figure")] })

    expect(entry.kind === "assistant" && entry.flaggedReason).toBe("wrong_figure")
  })

  it("reports an unflagged message as null rather than as undefined", () => {
    const [entry] = transcript({ messages: [assistantMessage(1, "đáp")] })

    expect(entry.kind === "assistant" && entry.flaggedReason).toBeNull()
  })
})

describe("the tool calls a stored answer carries", () => {
  it("reads them through, keeping the order the message stored", () => {
    const [entry] = transcript({
      messages: [withContent({ tool_calls: [call("a"), call("b", "error")] })],
    })

    expect(entry.kind === "assistant" && entry.view.toolCalls.map((one) => one.id)).toEqual([
      "a",
      "b",
    ])
    expect(entry.kind === "assistant" && entry.view.toolCalls[1].status).toBe("error")
  })

  it("reads a message that used no tool as carrying none", () => {
    const [entry] = transcript({ messages: [assistantMessage(1, "đáp")] })

    expect(entry.kind === "assistant" && entry.view.toolCalls).toEqual([])
  })

  it("reads a key that is not a list as carrying none rather than as one item", () => {
    // The column is JSONB and this projection is the boundary: an object here
    // would otherwise reach the renderer as something to iterate.
    const [entry] = transcript({ messages: [withContent({ tool_calls: { id: "a" } })] })

    expect(entry.kind === "assistant" && entry.view.toolCalls).toEqual([])
  })

  it("drops a row it cannot draw instead of rendering a blank line", () => {
    const [entry] = transcript({
      messages: [withContent({ tool_calls: [{ id: "a" }, "rác", null, call("b")] })],
    })

    expect(entry.kind === "assistant" && entry.view.toolCalls.map((one) => one.id)).toEqual([
      "b",
    ])
  })

  it("labels a call that stored no summary with the tool's own name", () => {
    const [entry] = transcript({
      messages: [withContent({ tool_calls: [{ id: "a", name: "recall_facts" }] })],
    })

    expect(entry.kind === "assistant" && entry.view.toolCalls[0].summary).toBe("recall_facts")
  })
})

describe("whether a stored answer is whole", () => {
  it("reads as complete when the message says nothing about it", () => {
    const [entry] = transcript({ messages: [assistantMessage(1, "đáp")] })

    expect(entry.kind === "assistant" && entry.view.completed).toBe(true)
  })

  it("reads as a fragment when the message says the Turn stopped early", () => {
    const [entry] = transcript({ messages: [withContent({ status: "incomplete" })] })

    expect(entry.kind === "assistant" && entry.view.completed).toBe(false)
  })
})

describe("the draft", () => {
  it("shows while the Turn runs", () => {
    const entries = transcript({ live: live({ text: "phần đầu" }) })

    expect(entries.at(-1)?.kind).toBe("draft")
  })

  it("carries the text and the calls the reducer holds", () => {
    const entries = transcript({ live: live({ text: "phần đầu", toolCalls: [call("a", "running")] }) })
    const draft = entries.at(-1)

    expect(draft?.kind === "draft" && draft.text).toBe("phần đầu")
    expect(draft?.kind === "draft" && draft.toolCalls[0].status).toBe("running")
  })

  it("belongs to one Thread and does not follow the user to another", () => {
    // Switching Threads must not leave the previous answer streaming under the
    // new one's transcript.
    const entries = transcript({
      threadId: "33333333-3333-4333-8333-333333333333",
      live: live({ text: "phần đầu" }),
    })

    expect(entries).toHaveLength(0)
  })

  it("is replaced by the canonical message rather than shown beside it", () => {
    const entries = transcript({
      messages: [userMessage(1, "hỏi"), assistantMessage(2, "đáp")],
      live: live({ phase: "completed", messageId: 2, text: "đáp" }),
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "assistant"])
  })

  it("stands until that message actually arrives, so the answer never blinks out", () => {
    // The terminal event names a message id before the Thread refetch lands.
    // Dropping the draft on the id alone would empty the screen in between.
    const entries = transcript({
      messages: [userMessage(1, "hỏi")],
      live: live({ phase: "completed", messageId: 2, text: "đáp" }),
    })

    expect(entries.at(-1)?.kind).toBe("draft")
  })

  it("stays after a Turn that produced nothing, because the status is owed", () => {
    const entries = transcript({
      messages: [userMessage(1, "hỏi")],
      live: live({ phase: "failed", terminalReason: "turn_failed" }),
    })

    const draft = entries.at(-1)
    expect(draft?.kind).toBe("draft")
    expect(draft?.kind === "draft" && draft.terminalReason).toBe("turn_failed")
  })

  it("is absent before anything has been sent", () => {
    expect(transcript({ live: IDLE })).toHaveLength(0)
  })
})

describe("the question the user just asked", () => {
  it("appears immediately, before the create has committed it", () => {
    const entries = transcript({ pendingUserText: "FPT thế nào?" })

    expect(entries).toEqual([
      { kind: "user", key: "pending-user", text: "FPT thế nào?", pending: true },
    ])
  })

  it("is dropped once the committed copy is the newest message", () => {
    const entries = transcript({
      messages: [userMessage(1, "FPT thế nào?")],
      pendingUserText: "FPT thế nào?",
    })

    expect(entries).toHaveLength(1)
    expect(entries[0].kind === "user" && entries[0].pending).toBe(false)
  })

  it("still shows when the same question is asked twice in a row", () => {
    // The committed copy of the *first* one is no longer the newest message
    // once its answer landed, so the second must not be swallowed by it.
    const entries = transcript({
      messages: [userMessage(1, "FPT thế nào?"), assistantMessage(2, "đáp")],
      pendingUserText: "FPT thế nào?",
    })

    expect(entries.at(-1)).toMatchObject({ kind: "user", pending: true })
  })
})

describe("an Analysis opened into the transcript", () => {
  it("sits where it was opened rather than at the end", () => {
    const entries = transcript({
      messages: [userMessage(1, "FPT thế nào?"), assistantMessage(2, "đáp")],
      openedAnalyses: [{ symbol: "FPT", tradingDay: "2026-08-12", afterSeq: 1 }],
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "analysis", "assistant"])
  })

  it("appears on its own in a Thread that has no messages yet", () => {
    const entries = transcript({
      openedAnalyses: [{ symbol: "HPG", tradingDay: "2026-08-12", afterSeq: 0 }],
    })

    expect(entries).toEqual([
      {
        kind: "analysis",
        key: "analysis-HPG-2026-08-12",
        symbol: "HPG",
        tradingDay: "2026-08-12",
      },
    ])
  })

  it("keeps the order they were opened in when two share an anchor", () => {
    const entries = transcript({
      messages: [userMessage(1, "hai mã")],
      openedAnalyses: [
        { symbol: "FPT", tradingDay: "2026-08-12", afterSeq: 1 },
        { symbol: "HPG", tradingDay: "2026-08-12", afterSeq: 1 },
      ],
    })

    expect(
      entries.filter((entry) => entry.kind === "analysis").map((entry) => entry.key),
    ).toEqual(["analysis-FPT-2026-08-12", "analysis-HPG-2026-08-12"])
  })

  it("stays above a draft that is still streaming", () => {
    const entries = transcript({
      messages: [userMessage(1, "FPT thế nào?")],
      live: live({ text: "một câu" }),
      openedAnalyses: [{ symbol: "FPT", tradingDay: "2026-08-12", afterSeq: 1 }],
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "analysis", "draft"])
  })
})

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
import { buildTranscript, questionBefore, type TranscriptInput } from "./transcript"
import type { FlagReason, ThreadMessage, ToolCall } from "./types"

const THREAD = "11111111-1111-4111-8111-111111111111"
const TURN = "22222222-2222-4222-8222-222222222222"

function call(id: string, status: ToolCall["status"] = "ok"): ToolCall {
  return {
    id,
    name: "web_search",
    status,
    summary: "Đã tìm trên web",
    round: 0,
    error: null,
    result_count: 0,
    results: [],
  }
}

function userMessage(
  id: number,
  text: string,
  content: Record<string, unknown> = {},
): ThreadMessage {
  return {
    id,
    seq: id,
    role: "user",
    content: { text, ...content } as ThreadMessage["content"],
    created_at: "2026-08-22T09:00:00Z",
    flagged_reason: null,
    flagged_at: null,
    helpful_at: null,
  }
}

function assistantMessage(
  id: number,
  text: string,
  flag: FlagReason | null = null,
  helpfulAt: string | null = null,
): ThreadMessage {
  return {
    id,
    seq: id,
    role: "assistant",
    content: { text, tool_calls: [] },
    created_at: "2026-08-22T09:00:05Z",
    flagged_reason: flag,
    flagged_at: flag === null ? null : "2026-08-22T10:00:00Z",
    helpful_at: helpfulAt,
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
      helpful_at: null,
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

  it("carries the positive mark as a boolean, not as the stamp behind it", () => {
    // Nothing on this surface renders *when* the reader approved, only that
    // they did — so the entry says that and nothing more.
    const [marked] = transcript({
      messages: [assistantMessage(1, "đáp", null, "2026-08-22T10:00:00Z")],
    })
    const [unmarked] = transcript({ messages: [assistantMessage(2, "đáp")] })

    expect(marked.kind === "assistant" && marked.helpful).toBe(true)
    expect(unmarked.kind === "assistant" && unmarked.helpful).toBe(false)
  })

  it("keeps the two verdicts independent, because the store does", () => {
    const [entry] = transcript({
      messages: [assistantMessage(1, "đáp", "wrong_figure", "2026-08-22T10:00:00Z")],
    })

    // An answer that was useful and got one figure wrong is both, and the
    // transcript is not the place that decides one of them away.
    expect(entry.kind === "assistant" && entry.flaggedReason).toBe("wrong_figure")
    expect(entry.kind === "assistant" && entry.helpful).toBe(true)
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

describe("the question a stored answer ended by asking", () => {
  const card = (extra: Record<string, unknown> = {}) => ({
    question_id: "q-1",
    prompt: "Bạn đang quyết định gì?",
    options: [
      { id: "hold", label: "Giữ" },
      { id: "add", label: "Mua thêm" },
    ],
    multi_select: false,
    skip_label: "Bỏ qua",
    ...extra,
  })

  it("reads the card with the outcome the backend merged into it", () => {
    // The message is immutable and the outcome is not, so the transcript is
    // where the two are put back together — and this is where the client reads
    // the result of that.
    const [entry] = transcript({
      messages: [
        withContent({
          question: card({ state: "answered", selected_option_ids: ["add"] }),
        }),
      ],
    })

    expect(entry.kind === "assistant" && entry.view.question?.state).toBe("answered")
    expect(entry.kind === "assistant" && entry.view.question?.selected_option_ids).toEqual([
      "add",
    ])
  })

  it("reads a card whose row is gone as superseded, not as one to answer again", () => {
    // The backend leaves the content alone when the row behind a question has
    // vanished. Drawing that as pending would invite an answer nothing can
    // record.
    const [entry] = transcript({ messages: [withContent({ question: card() })] })

    expect(entry.kind === "assistant" && entry.view.question?.state).toBe("superseded")
  })

  it("reads an answer that asked nothing as carrying no card", () => {
    const [entry] = transcript({ messages: [assistantMessage(1, "đáp")] })

    expect(entry.kind === "assistant" && entry.view.question).toBeNull()
  })

  it("carries the live card on the draft, so it is answerable before the refetch", () => {
    const [entry] = transcript({
      messages: [],
      live: live({
        question: {
          question_id: "q-1",
          prompt: "Bạn đang quyết định gì?",
          options: [
            { id: "hold", label: "Giữ", detail: null },
            { id: "add", label: "Mua thêm", detail: null },
          ],
          multi_select: false,
          skip_label: "Bỏ qua",
          state: "pending",
          selected_option_ids: null,
        },
      }),
    })

    expect(entry.kind === "draft" && entry.question?.state).toBe("pending")
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

  it("shows what the reveal says is on screen, not everything received", () => {
    const entries = transcript({
      live: live({ text: "cả câu trả lời" }),
      reveal: { text: "cả câu", working: false, handedOver: false },
    })
    const draft = entries.at(-1)

    expect(draft?.kind === "draft" && draft.text).toBe("cả câu")
  })

  it("keeps the screen while the answer is still arriving", () => {
    // The Turn is over and the message has landed, and the words are still
    // coming: handing over now would put every one still waiting on screen at
    // once, because the canonical message draws them with no cadence.
    const entries = transcript({
      messages: [userMessage(1, "hỏi"), assistantMessage(2, "đáp")],
      live: live({ phase: "completed", messageId: 2, text: "đáp" }),
      reveal: { text: "đ", working: false, handedOver: false },
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "draft"])
  })

  it("hands over the moment the reveal says the answer is on screen", () => {
    const entries = transcript({
      messages: [userMessage(1, "hỏi"), assistantMessage(2, "đáp")],
      live: live({ phase: "completed", messageId: 2, text: "đáp" }),
      reveal: { text: "đáp", working: false, handedOver: true },
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "assistant"])
  })

  it("holds nothing back in a Thread it does not belong to", () => {
    // The hold is about one draft finishing. Another Thread's answers are
    // history and are drawn whatever this draft is doing.
    const entries = transcript({
      threadId: "33333333-3333-4333-8333-333333333333",
      messages: [userMessage(1, "hỏi"), assistantMessage(2, "đáp")],
      live: live({ phase: "completed", messageId: 2, text: "đáp" }),
      reveal: { text: "đ", working: false, handedOver: false },
    })

    expect(entries.map((entry) => entry.kind)).toEqual(["user", "assistant"])
  })

  it("shows everything received when nothing is pacing it", () => {
    const entries = transcript({ live: live({ text: "phần đầu" }) })
    const draft = entries.at(-1)

    expect(draft?.kind === "draft" && draft.text).toBe("phần đầu")
    expect(draft?.kind === "draft" && draft.working).toBe(true)
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
      {
        kind: "user",
        key: "pending-user",
        text: "FPT thế nào?",
        pending: true,
        attachments: [],
      },
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

describe("a stored answer", () => {
  const stored = (content: Record<string, unknown>): ThreadMessage => ({
    id: 1,
    seq: 1,
    role: "assistant",
    content,
    created_at: "2026-08-22T09:00:00Z",
    flagged_reason: null,
    flagged_at: null,
    helpful_at: null,
  })

  it("shows the reply and keeps the narration out of it", () => {
    const [entry] = buildTranscript({
      threadId: THREAD,
      messages: [
        stored({
          text: "Đang tra tin\n\nĐây là câu trả lời.",
          answer: "Đây là câu trả lời.",
          thoughts: [{ round: 0, text: "Đang tra tin" }],
          elapsed_ms: 8000,
        }),
      ],
      live: IDLE,
      pendingUserText: null,
    })

    expect(entry.kind === "assistant" && entry.view.text).toBe("Đây là câu trả lời.")
    expect(entry.kind === "assistant" && entry.view.thoughts).toEqual([
      { round: 0, text: "Đang tra tin" },
    ])
    expect(entry.kind === "assistant" && entry.view.elapsedMs).toBe(8000)
  })

  it("reads a message written before the split as all reply", () => {
    // The load-bearing back-compatibility case: an older row has `text` and no
    // `answer`, and every word of it was the reply. Falling back to an empty
    // string here would blank out the transcript of every past conversation.
    const [entry] = buildTranscript({
      threadId: THREAD,
      messages: [stored({ text: "Câu trả lời cũ.", tool_calls: [] })],
      live: IDLE,
      pendingUserText: null,
    })

    expect(entry.kind === "assistant" && entry.view.text).toBe("Câu trả lời cũ.")
    expect(entry.kind === "assistant" && entry.view.thoughts).toEqual([])
    expect(entry.kind === "assistant" && entry.view.elapsedMs).toBe(0)
  })

})

describe("what a question's attachments look like on the record", () => {
  it("reads them off the stored message", () => {
    const entries = transcript({
      messages: [
        userMessage(1, "ảnh này là gì?", {
          attachments: [
            { id: "a-1", filename: "bang-gia.png", media_type: "image/png", byte_size: 2048 },
          ],
        }),
      ],
    })

    expect(entries[0]).toMatchObject({
      kind: "user",
      attachments: [{ id: "a-1", filename: "bang-gia.png", byte_size: 2048 }],
    })
  })

  it("gives an ordinary question an empty list rather than undefined", () => {
    // Every consumer maps over it — the bubble, the retry, the resend — and a
    // missing array would be three optional chains instead of one invariant.
    const entries = transcript({ messages: [userMessage(1, "VCB thế nào?")] })

    expect(entries[0]).toMatchObject({ kind: "user", attachments: [] })
  })

  it("drops a half-written entry rather than the whole conversation", () => {
    // Stored JSONB, so a value written by an older build or edited by hand
    // should cost one missing chip and nothing else.
    const entries = transcript({
      messages: [
        userMessage(1, "hỏi", {
          attachments: [{ filename: "khong-co-id.png" }, { id: "a-2" }, "rác"],
        }),
      ],
    })

    expect(entries[0]).toMatchObject({
      kind: "user",
      // Named by its id when the filename is unreadable: a chip with no label
      // is a chip that says nothing.
      attachments: [{ id: "a-2", filename: "a-2" }],
    })
  })

  it("shows the chips on a question the create has not committed yet", () => {
    const entries = transcript({
      pendingUserText: "đọc ảnh này",
      pendingAttachments: [
        { id: "a-9", filename: "moi.png", media_type: "image/png", byte_size: 12 },
      ],
    })

    expect(entries.at(-1)).toMatchObject({
      kind: "user",
      pending: true,
      attachments: [{ id: "a-9" }],
    })
  })
})


describe("asking a question again", () => {
  const asked = (text: string, ids: string[] = []) => ({
    kind: "user" as const,
    key: `k-${text}`,
    text,
    pending: false,
    attachments: ids.map((id) => ({
      id,
      filename: `${id}.png`,
      media_type: "image/png",
      byte_size: 1,
    })),
  })
  const answered = (key: string) => ({ kind: "assistant" as const, key }) as never

  it("hands back the words and the files together", () => {
    // Together, because apart is the failure: a retry that sends the words alone
    // gets a confident answer about a picture the model never saw, and a retry
    // is a new Turn so no idempotency conflict catches it.
    expect(questionBefore([asked("một", ["a-1", "a-2"])])).toEqual({
      text: "một",
      attachments: ["a-1", "a-2"],
    })
  })

  it("takes the last question when no entry is named", () => {
    expect(questionBefore([asked("cũ", ["a-1"]), asked("mới", ["a-2"])])).toEqual({
      text: "mới",
      attachments: ["a-2"],
    })
  })

  it("takes the question before a named entry, with that question's own files", () => {
    const entries = [asked("cũ", ["a-1"]), answered("m-1"), asked("mới", ["a-2"])]

    expect(questionBefore(entries, "m-1")).toEqual({
      text: "cũ",
      attachments: ["a-1"],
    })
  })

  it("is null when nothing has been asked", () => {
    expect(questionBefore([])).toBeNull()
    expect(questionBefore([answered("m-1")], "m-1")).toBeNull()
  })

  it("gives an empty list for a question that carried nothing", () => {
    expect(questionBefore([asked("trơn")])).toEqual({ text: "trơn", attachments: [] })
  })
})

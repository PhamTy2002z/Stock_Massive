/**
 * What the create call sends, and what a refusal comes back as.
 *
 * Two properties of ADR-0013 live in this one small module, and neither is
 * visible from a component test.
 *
 * **The browser owns the Turn id.** It is generated before the `POST` and sent
 * *in* it, which is what makes a retried admission safe on a flaky network: a
 * `POST` that timed out after the server committed can be re-issued with the
 * same id and resolves to the Turn that already exists. An id assigned by the
 * server and returned could not — the retry would have no id to reuse.
 *
 * **Admission is an HTTP outcome.** A `429` or a `503` is thrown here with its
 * stable reason attached, never awaited as an event on a stream that a refused
 * Turn never opens.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AlphaRefusalError } from "@/lib/alpha"

import {
  attachmentUrl,
  createTurn,
  newTurnId,
  turnStreamUrl,
  uploadAttachment,
} from "./api"

let fetchMock: ReturnType<typeof vi.fn>

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function sentBody(): Record<string, unknown> {
  return JSON.parse(fetchMock.mock.calls[0][1].body as string)
}

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("the Turn id", () => {
  it("is carried in the create request rather than asked for", async () => {
    fetchMock.mockResolvedValue(json({ id: "t-1", created: true }))
    const turnId = newTurnId()

    await createTurn({ threadId: "thread-1", turnId, text: "VCB thế nào?" })

    expect(sentBody().turn_id).toBe(turnId)
    expect(fetchMock.mock.calls[0][0]).toBe("/api/alpha-desk/threads/thread-1/turns")
  })

  it("resubmits as the same key, so the same admission is one Turn", async () => {
    // The whole point of a client-chosen id: this is what a browser does after
    // a `POST` whose answer never arrived.
    // A fresh Response per call: one body cannot be read twice, and the point
    // of the test is that the client genuinely makes the call again.
    fetchMock.mockImplementation(async () => json({ id: "t-1", created: false }))
    const turnId = newTurnId()
    const input = { threadId: "thread-1", turnId, text: "VCB thế nào?" }

    await createTurn(input)
    await createTurn(input)

    const keys = fetchMock.mock.calls.map(
      (call) => JSON.parse(call[1].body as string).turn_id,
    )
    expect(keys).toEqual([turnId, turnId])
  })

  it("carries the mode the reader switched to, so the desk is asked for", async () => {
    fetchMock.mockResolvedValue(json({ id: "t-1", created: true }))

    await createTurn({
      threadId: "thread-1",
      turnId: newTurnId(),
      text: "VCB thế nào?",
      signalDesk: true,
    })

    expect(sentBody().mode).toBe("signal_desk")
  })

  it("says chat rather than saying nothing, because the mode is part of the key", async () => {
    // Omitted, the server would default it — and two Turns asked in two
    // different modes under one id would resolve to each other. The value is
    // stated so the idempotency payload can tell them apart.
    fetchMock.mockResolvedValue(json({ id: "t-1", created: true }))

    await createTurn({ threadId: "thread-1", turnId: newTurnId(), text: "VCB?" })

    expect(sentBody().mode).toBe("chat")
  })

  it("sends no analysis lens, because nothing behind the request reads one", async () => {
    // `active_symbol` used to travel here and was dropped in silence by a schema
    // that never declared it. A key nobody reads is worse than no key: it reads
    // from the browser as a lens the backend honours.
    fetchMock.mockResolvedValue(json({ id: "t-1", created: true }))

    await createTurn({ threadId: "thread-1", turnId: newTurnId(), text: "VCB?" })

    expect(sentBody()).not.toHaveProperty("active_symbol")
  })

  it("is a fresh id each time it is asked for", () => {
    const ids = new Set(Array.from({ length: 50 }, newTurnId))
    expect(ids.size).toBe(50)
  })

  it("points the stream at the same-origin proxy, so cookies travel", () => {
    expect(turnStreamUrl("t-1")).toBe("/api/alpha-desk/turns/t-1/events")
  })
})

describe("an admission refusal", () => {
  it("throws the exhausted user allowance as a 429 with its stable reason", async () => {
    fetchMock.mockResolvedValue(
      json(
        { detail: { reason: "user_turn_starts_daily", message: "Đã hết lượt hôm nay." } },
        429,
      ),
    )

    const refusal = await createTurn({
      threadId: "thread-1",
      turnId: newTurnId(),
      text: "VCB?",
    }).catch((error: unknown) => error)

    expect(refusal).toBeInstanceOf(AlphaRefusalError)
    expect((refusal as AlphaRefusalError).status).toBe(429)
    expect((refusal as AlphaRefusalError).reason).toBe("user_turn_starts_daily")
    // The sentence is kept beside the code rather than folded into it: the code
    // is what the surface branches on, the sentence is what it shows.
    expect((refusal as AlphaRefusalError).message).toBe("Đã hết lượt hôm nay.")
  })

  it("throws an exhausted service budget as a 503 that names no user rule", async () => {
    fetchMock.mockResolvedValue(
      json(
        { detail: { reason: "system_active_turns", message: "Dịch vụ đang bận." } },
        503,
      ),
    )

    const refusal = (await createTurn({
      threadId: "thread-1",
      turnId: newTurnId(),
      text: "VCB?",
    }).catch((error: unknown) => error)) as AlphaRefusalError

    expect(refusal.status).toBe(503)
    expect(refusal.reason).toBe("system_active_turns")
  })

  it("reports an outage with a null reason, so nobody mistakes it for a rule", async () => {
    fetchMock.mockResolvedValue(new Response("<html>502</html>", { status: 502 }))

    const refusal = (await createTurn({
      threadId: "thread-1",
      turnId: newTurnId(),
      text: "VCB?",
    }).catch((error: unknown) => error)) as AlphaRefusalError

    expect(refusal.status).toBe(502)
    expect(refusal.reason).toBeNull()
  })
})


describe("what a question carries besides its words", () => {
  it("sends an empty list when nothing was attached", async () => {
    fetchMock.mockResolvedValue(json({ id: "turn-1" }))

    await createTurn({ threadId: "t1", turnId: "turn-1", text: "VCB thế nào?" })

    expect(sentBody().attachments).toEqual([])
  })

  it("sends the ids, in the order they were added", async () => {
    fetchMock.mockResolvedValue(json({ id: "turn-1" }))

    await createTurn({
      threadId: "t1",
      turnId: "turn-1",
      text: "đọc hai ảnh này",
      attachments: ["a-1", "a-2"],
    })

    expect(sentBody().attachments).toEqual(["a-1", "a-2"])
  })
})

describe("putting one file up", () => {
  it("sends multipart and sets no Content-Type of its own", async () => {
    // The browser computes the multipart boundary from the body at send time.
    // Anything set here would either lose the boundary or shadow it.
    fetchMock.mockResolvedValue(
      json({ id: "a-1", filename: "a.png", media_type: "image/png", byte_size: 3 }),
    )

    const stored = await uploadAttachment(new File(["abc"], "a.png", { type: "image/png" }))

    const [, init] = fetchMock.mock.calls[0]
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined()
    expect(stored.id).toBe("a-1")
  })

  it("throws the refusal with its reason, so the chip can say which one", async () => {
    fetchMock.mockResolvedValue(
      json({ detail: { reason: "file_too_large", message: "quá lớn" } }, 413),
    )

    await expect(
      uploadAttachment(new File(["abc"], "a.png", { type: "image/png" })),
    ).rejects.toMatchObject({ reason: "file_too_large" })
  })
})

describe("where an attachment's bytes are read from", () => {
  it("is the proxy path, escaped", () => {
    expect(attachmentUrl("a b")).toBe("/api/alpha-desk/attachments/a%20b")
  })
})

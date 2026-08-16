import { expect, test } from "@playwright/test"

import {
  API_ORIGIN,
  ask,
  churn,
  finish,
  liveTurnId,
  newEmail,
  purge,
  resetTurn,
  say,
  signUp,
} from "./desk"

/**
 * The four properties streaming is accepted against (#92, ADR-0013).
 *
 * Through the real path: a real browser drives a real Next production build,
 * which proxies a real FastAPI. Every assertion below is about bytes arriving
 * over that path at a particular *time*, which is the one thing unit tests on
 * either side of a proxy cannot say anything about.
 *
 * Any future CDN or reverse proxy passes this same file. Running it is
 * documented in `docs/streaming-topology.md`.
 */

let email = ""

test.beforeEach(async ({ page, request }) => {
  email = newEmail()
  await resetTurn(request)
  await signUp(page, email)
  await page.goto("/alpha-desk")
  await expect(page.getByLabel("Ask Alpha Desk")).toBeVisible()
})

test.afterEach(async ({ request }) => {
  // Whatever the test did, the Turn must not be left holding a slot.
  await finish(request).catch(() => {})
  await purge(request, email)
})

test("the first block and a heartbeat arrive before the Turn completes", async ({
  page,
  request,
}) => {
  await ask(page, request, "VCB thế nào?")
  await say(request, "khối đầu tiên")

  // Arrived, and the Turn is still running: a transport that buffered would
  // show nothing here until `finish` had been called.
  await expect(page.getByText("khối đầu tiên")).toBeVisible()
  const before = await (await request.get(`${API_ORIGIN}/e2e/turn`)).json()
  expect(before.released).toBe(false)

  // The heartbeat is an SSE comment, so `EventSource` discards it by design and
  // the DOM can never show one. Read as raw bytes through the same proxy — a
  // quiet path that is not beating is indistinguishable from a hung one, which
  // is the whole reason the beat exists.
  const turnId = await liveTurnId(page)
  const observed = await page.evaluate(async (id) => {
    const response = await fetch(`/api/alpha-desk/turns/${id}/events`, {
      headers: { accept: "text/event-stream" },
    })
    const headers = {
      contentType: response.headers.get("content-type"),
      cacheControl: response.headers.get("cache-control"),
      contentLength: response.headers.get("content-length"),
    }
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    const deadline = Date.now() + 40_000
    let heartbeat = false
    while (Date.now() < deadline) {
      const { value, done } = await reader.read()
      if (done) break
      if (decoder.decode(value).includes(": heartbeat")) {
        heartbeat = true
        break
      }
    }
    await reader.cancel()
    return { ...headers, heartbeat }
  }, turnId)

  expect(observed.contentType).toContain("text/event-stream")
  expect(observed.cacheControl).toContain("no-transform")
  // A stream has no length to declare, and a synthesized one makes every hop
  // wait for exactly that many bytes.
  expect(observed.contentLength).toBeNull()
  expect(observed.heartbeat).toBe(true)

  const during = await (await request.get(`${API_ORIGIN}/e2e/turn`)).json()
  expect(during.released).toBe(false)
})

test("a mid-Turn reconnect resumes from an ordered snapshot, with no duplicate and no gap", async ({
  page,
  request,
}) => {
  await ask(page, request, "VCB thế nào?")
  await say(request, "khối một")
  await say(request, "khối hai")
  await expect(page.getByText("khối hai")).toBeVisible()

  // A reload ends this subscriber and nothing else: the Turn belongs to the
  // backend, and reattaching is what the desk remembered how to do.
  await page.reload()
  await expect(page.getByText("khối một")).toBeVisible()
  await expect(page.getByText("khối hai")).toBeVisible()

  // The same transcript, not a longer one.
  await expect(page.getByText("khối một")).toHaveCount(1)
  await expect(page.getByText("khối hai")).toHaveCount(1)

  // Order survives the reconnect, because a snapshot carries the blocks in
  // sequence rather than replaying them as they happen to be redelivered.
  const order = await page.evaluate(() => document.body.innerText)
  expect(order.indexOf("khối một")).toBeLessThan(order.indexOf("khối hai"))

  // And the third block, published after the reattach, lands on the reattached
  // subscriber rather than on the connection the reload closed.
  await say(request, "khối ba")
  await expect(page.getByText("khối ba")).toBeVisible()
})

test("a subscriber that stops reading is dropped, and the Turn finishes anyway", async ({
  page,
  request,
}) => {
  await ask(page, request, "VCB thế nào?")
  await say(request, "khối đầu tiên")
  await expect(page.getByText("khối đầu tiên")).toBeVisible()

  const turnId = await liveTurnId(page)

  // A second subscriber that opens the stream and never reads it. Its bounded
  // queue is what stops it from applying backpressure to the loop.
  await page.evaluate(async (id) => {
    const response = await fetch(`/api/alpha-desk/turns/${id}/events`, {
      headers: { accept: "text/event-stream" },
    })
    // Held, deliberately unread.
    ;(window as unknown as { __slow: ReadableStreamDefaultReader<Uint8Array> }).__slow =
      response.body!.getReader()
  }, turnId)

  await churn(request, 6_000)

  const startedAt = Date.now()
  await finish(request)

  // The Turn reached its terminal state and the canonical message replaced the
  // draft, while a subscriber sat there not reading a byte.
  await expect(page.getByRole("note", { name: "Risk notice" })).toBeVisible({
    timeout: 20_000,
  })
  expect(Date.now() - startedAt).toBeLessThan(20_000)

  // The unread subscriber's stream ended without ever delivering the terminal
  // event: it was dropped rather than waited for.
  const tail = await page.evaluate(async () => {
    const reader = (
      window as unknown as { __slow: ReadableStreamDefaultReader<Uint8Array> }
    ).__slow
    const decoder = new TextDecoder()
    let text = ""
    const deadline = Date.now() + 20_000
    while (Date.now() < deadline) {
      const { value, done } = await reader.read()
      if (done) break
      text += decoder.decode(value, { stream: true })
    }
    return { closed: Date.now() < deadline, sawTerminal: text.includes("turn.completed") }
  })

  expect(tail.closed).toBe(true)
  expect(tail.sawTerminal).toBe(false)
})

test("the terminal event refetches the Thread and replaces the draft", async ({
  page,
  request,
}) => {
  await ask(page, request, "VCB thế nào?")
  await say(request, "khối đầu tiên")
  await expect(page.getByText("khối đầu tiên")).toBeVisible()

  // The draft carries no Risk Notice; only the canonical message does, because
  // the backend attaches it in the terminal transaction.
  await expect(page.getByRole("note", { name: "Risk notice" })).toHaveCount(0)

  await finish(request)

  await expect(page.getByRole("note", { name: "Risk notice" })).toBeVisible({
    timeout: 20_000,
  })
  // Replaced, not appended to: one copy of the block, not two.
  await expect(page.getByText("khối đầu tiên")).toHaveCount(1)
  await expect(page.getByLabel("Assistant message")).toHaveCount(1)
})

import { expect, test } from "@playwright/test"

import {
  ANSWER_LABEL,
  API_ORIGIN,
  CANONICAL_MARK,
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
 * The four properties streaming is accepted against.
 *
 * Through the real path: a real browser drives a real Next production build,
 * which proxies a real FastAPI. Every assertion below is about bytes arriving
 * over that path at a particular *time*, which is the one thing unit tests on
 * either side of a proxy cannot say anything about.
 *
 * A `content.delta` is appended to the answer rather than added as a row, so
 * these read the answer for what it contains and count occurrences by hand: two
 * deltas are one paragraph, and `getByText` matches whole elements.
 *
 * Any future CDN or reverse proxy passes this same file. Running it is
 * documented in `docs/streaming-topology.md`.
 */

let email = ""

/** How many times a fragment appears in the answer on screen. */
function occurrences(text: string, fragment: string): number {
  return text.split(fragment).length - 1
}

test.beforeEach(async ({ page, request }) => {
  email = newEmail()
  await resetTurn(request)
  await signUp(page, email)
  await page.goto("/")
  await expect(page.getByLabel("Hỏi VisgniteAI")).toBeVisible()
})

test.afterEach(async ({ request }) => {
  // Whatever the test did, the Turn must not be left holding a slot.
  await finish(request).catch(() => {})
  await purge(request, email)
})

test("the first delta and a heartbeat arrive before the Turn completes", async ({
  page,
  request,
}) => {
  await ask(page, request, "VCB thế nào?")
  await say(request, "đoạn đầu tiên ")

  // Arrived, and the Turn is still running: a transport that buffered would
  // show nothing here until `finish` had been called.
  await expect(page.getByLabel(ANSWER_LABEL)).toContainText("đoạn đầu tiên")
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

test("streamed tables and code blocks stay stable and fit the transcript", async ({
  page,
  request,
}) => {
  const answer = page.getByLabel(ANSWER_LABEL)

  await ask(page, request, "Các vùng giá của STB?")
  await say(request, "| Vùng giá | Vai trò |\n| --- | --- |\n| 76.000–76.600 | Kháng cự gần |")

  const header = answer.getByRole("columnheader", { name: "Vùng giá" })
  await expect(header).toBeVisible()
  await header.evaluate((cell) => {
    ;(window as typeof window & { __streamedTableCell?: Element }).__streamedTableCell = cell
  })

  await say(request, "\n\nCách đọc cho tháng tới:")
  await expect(answer).toContainText("Cách đọc cho tháng tới:")

  expect(
    await header.evaluate((cell) =>
      (window as typeof window & { __streamedTableCell?: Element }).__streamedTableCell?.isSameNode(
        cell,
      ),
    ),
  ).toBe(true)

  const tableStyle = await header.evaluate((cell) => {
    const style = getComputedStyle(cell)
    return {
      borderBottomWidth: style.borderBottomWidth,
      borderLeftWidth: style.borderLeftWidth,
      borderRightWidth: style.borderRightWidth,
    }
  })
  expect(tableStyle.borderBottomWidth).not.toBe("0px")
  expect(tableStyle.borderLeftWidth).toBe("0px")
  expect(tableStyle.borderRightWidth).toBe("0px")
  await expect(answer.getByRole("button", { name: "Sao chép bảng" })).toBeVisible()

  await say(request, "\n\n```text\nFinancial Data\n  ↓\nAI Intent\n```")
  const codeBlock = answer.getByLabel("Khối mã", { exact: true })
  await expect(codeBlock).toBeVisible()
  await expect(codeBlock).toContainText("Financial Data")
  const codeStyle = await codeBlock.evaluate((pre) => {
    const surface = getComputedStyle(pre.parentElement!)
    return { backgroundColor: surface.backgroundColor, borderRadius: surface.borderRadius }
  })
  expect(codeStyle.backgroundColor).not.toBe("rgba(0, 0, 0, 0)")
  expect(codeStyle.borderRadius).not.toBe("0px")
  await expect(answer.getByRole("button", { name: "Sao chép khối mã" })).toBeVisible()
  await page.setViewportSize({ width: 375, height: 812 })
  await expect(header).toBeVisible()
  await expect(codeBlock).toBeVisible()
  expect(
    await answer.getByRole("region", { name: "Bảng trong câu trả lời" }).evaluate(
      (region) => region.scrollWidth > region.clientWidth,
    ),
  ).toBe(true)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    ),
  ).toBe(true)
})

test("a mid-Turn reconnect resumes from an ordered snapshot, with no duplicate and no gap", async ({
  page,
  request,
}) => {
  const answer = page.getByLabel(ANSWER_LABEL)

  await ask(page, request, "VCB thế nào?")
  await say(request, "đoạn một ")
  await say(request, "đoạn hai ")
  await expect(answer).toContainText("đoạn hai")

  // A reload ends this subscriber and nothing else: the Turn belongs to the
  // backend, and reattaching is what the desk remembered how to do.
  await page.reload()
  await expect(answer).toContainText("đoạn một")
  await expect(answer).toContainText("đoạn hai")

  // The same answer, not a longer one: a snapshot restates the whole text, so
  // merging it into what was on screen would print every delta twice.
  const restated = await answer.innerText()
  expect(occurrences(restated, "đoạn một")).toBe(1)
  expect(occurrences(restated, "đoạn hai")).toBe(1)
  // Order survives the reconnect, because the snapshot carries the text as one
  // string rather than replaying the deltas as they happen to be redelivered.
  expect(restated.indexOf("đoạn một")).toBeLessThan(restated.indexOf("đoạn hai"))

  // And the third delta, published after the reattach, lands on the reattached
  // subscriber rather than on the connection the reload closed.
  await say(request, "đoạn ba ")
  await expect(answer).toContainText("đoạn ba")
})

test("a subscriber that stops reading is dropped, and the Turn finishes anyway", async ({
  page,
  request,
}) => {
  await ask(page, request, "VCB thế nào?")
  await say(request, "đoạn đầu tiên ")
  await expect(page.getByLabel(ANSWER_LABEL)).toContainText("đoạn đầu tiên")

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
  await expect(page.getByRole(CANONICAL_MARK.role, { name: CANONICAL_MARK.name })).toBeVisible({
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
  const answer = page.getByLabel(ANSWER_LABEL)

  await ask(page, request, "VCB thế nào?")
  await say(request, "đoạn đầu tiên ")
  await expect(answer).toContainText("đoạn đầu tiên")

  // The draft carries no flag control; only the persisted message does, because
  // a flag names a message id and the draft has none yet.
  await expect(page.getByRole(CANONICAL_MARK.role, { name: CANONICAL_MARK.name })).toHaveCount(0)

  await finish(request)

  await expect(page.getByRole(CANONICAL_MARK.role, { name: CANONICAL_MARK.name })).toBeVisible({
    timeout: 20_000,
  })
  // Replaced, not appended to: one answer on screen, carrying one copy of the
  // text the stream delivered.
  await expect(answer).toHaveCount(1)
  expect(occurrences(await answer.innerText(), "đoạn đầu tiên")).toBe(1)
})

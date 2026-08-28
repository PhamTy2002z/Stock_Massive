import { expect, test } from "@playwright/test"

import {
  ask,
  draw,
  finish,
  liveThreadId,
  liveTurnId,
  newEmail,
  purge,
  resetTurn,
  say,
  signUp,
} from "./desk"

/**
 * The desk view, through the same three hops the answer travels.
 *
 * What only this path can prove: the announcement arrives on the live stream
 * *while the Turn is still running*, the panel opens on it without the reader
 * asking, and the id it carried fetches the row through the real ownership
 * join in the real proxy. Unit tests cover each of those against a mock; none
 * of them can say the event and the fetch agree about which artifact.
 *
 * The stored answer's card is the other half: a reader coming back to the
 * conversation tomorrow has to be able to open the same picture, and that goes
 * through the transcript rather than through the stream.
 */

let email = ""

test.beforeEach(async ({ page, request }) => {
  email = newEmail()
  await resetTurn(request)
  await signUp(page, email)
  await page.goto("/")
  await expect(page.getByLabel("Hỏi VisgniteAI")).toBeVisible()
})

test.afterEach(async ({ request }) => {
  await finish(request)
  await purge(request, email)
})

test("a desk view announced mid-answer opens the panel and draws the stored numbers", async ({
  page,
  request,
}) => {
  await ask(page, request, "Thanh khoản STB tập trung vào khung giờ nào?")
  const threadId = await liveThreadId(page)
  const turnId = await liveTurnId(page)

  await draw(request, threadId, turnId)

  // Opened by the event, not by the reader: the panel is the answer's own
  // second surface, and a picture nobody is shown may as well not exist.
  const panel = page.getByRole("complementary", { name: "Chat inspector" })
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("tab", { name: "Phân tích" })).toHaveAttribute(
    "aria-selected",
    "true",
  )

  // The row itself, fetched by the id the event carried and proxied through
  // Next: the title and the provenance are the server's, not the client's.
  await expect(panel.getByText("Thanh khoản trong phiên — STB")).toBeVisible()
  await expect(panel.getByText(/vnstock/)).toBeVisible()
  await expect(panel.getByText(/30 phiên/)).toBeVisible()
})

test("the finished answer keeps a card that opens the same picture again", async ({
  page,
  request,
}) => {
  await ask(page, request, "Thanh khoản STB tập trung vào khung giờ nào?")
  const threadId = await liveThreadId(page)
  const turnId = await liveTurnId(page)
  await draw(request, threadId, turnId)
  await say(request, "Thanh khoản STB dồn về phiên đóng cửa.")
  await finish(request)

  const panel = page.getByRole("complementary", { name: "Chat inspector" })
  await expect(panel.getByText("Thanh khoản trong phiên — STB")).toBeVisible()
  await panel.getByRole("button", { name: "Close inspector" }).click()
  await expect(panel).toBeHidden()

  // The canonical message carries the announcement, so the picture is still
  // reachable after the draft it was announced on has been replaced.
  await page.getByRole("button", { name: /Thanh khoản trong phiên/ }).click()

  await expect(panel).toBeVisible()
  await expect(panel.getByText(/vnstock/)).toBeVisible()
})

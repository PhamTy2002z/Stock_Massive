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
  // The desk is the trigger: a board announced while the mode is off leaves a
  // card in the transcript and changes nothing else, so the reader turns the
  // mode on before asking, as they would.
  await page.getByRole("radio", { name: "Signal Desk" }).click()
  await ask(page, request, "Thanh khoản STB tập trung vào khung giờ nào?")
  const threadId = await liveThreadId(page)
  const turnId = await liveTurnId(page)

  await draw(request, threadId, turnId)

  // Opened by the event, not by the reader: the panel is the answer's own
  // second surface, and a picture nobody is shown may as well not exist.
  const panel = page.getByRole("complementary", { name: "Signal Desk" })
  await expect(panel).toBeVisible()
  // The header names the board on screen on its one control; the other boards
  // of the conversation sit in the dropdown under it, not in a strip of tabs.
  await expect(panel.getByRole("button", { name: "Tất cả bảng" })).toContainText(
    "Thanh khoản trong phiên — STB",
  )

  // The row itself, fetched by the id the event carried and proxied through
  // Next: the title and the provenance are the server's, not the client's.
  await expect(panel.getByText("Thanh khoản trong phiên — STB")).toBeVisible()
  // The caption names the freeze and the window, and not the provider it read:
  // a reader asked about a company, so the strip talks about the data.
  await expect(panel.getByText(/dữ liệu \d{2}\/\d{2}\/\d{4}/)).toBeVisible()
  await expect(panel.getByText(/30 phiên/)).toBeVisible()
  await expect(panel.getByText(/vnstock/)).toBeHidden()
})

test("the finished answer keeps a card that opens the same picture again", async ({
  page,
  request,
}) => {
  await page.getByRole("radio", { name: "Signal Desk" }).click()
  await ask(page, request, "Thanh khoản STB tập trung vào khung giờ nào?")
  const threadId = await liveThreadId(page)
  const turnId = await liveTurnId(page)
  await draw(request, threadId, turnId)
  await say(request, "Thanh khoản STB dồn về phiên đóng cửa.")
  await finish(request)

  const panel = page.getByRole("complementary", { name: "Signal Desk" })
  await expect(panel.getByText("Thanh khoản trong phiên — STB")).toBeVisible()
  await panel.getByRole("button", { name: "Close Signal Desk" }).click()
  await expect(panel).toBeHidden()

  // The canonical message carries the announcement, so the picture is still
  // reachable after the draft it was announced on has been replaced.
  await page.getByRole("button", { name: /Thanh khoản trong phiên/ }).click()

  await expect(panel).toBeVisible()
  await expect(panel.getByText(/30 phiên/)).toBeVisible()
})

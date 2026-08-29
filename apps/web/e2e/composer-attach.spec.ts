import { expect, test } from "@playwright/test"

import { newEmail, purge, signUp } from "./desk"

/**
 * The attach menu's rows are reachable by a press.
 *
 * This exists because they were not, and because **no unit test could have
 * said so**. Every test of this menu renders `Composer` on its own, where the
 * shell's scrim does not exist; in the running app the scrim is a sibling of
 * `main` carrying `z-[25]`, `main` is positioned with `z-index: auto`, and a
 * positioned ancestor without a z-index of its own still paints as one unit —
 * so the menu drawn inside the composer painted *under* the scrim however high
 * its own z-index went. The rows rendered, read as enabled, had their handlers
 * bound, and every press landed on the scrim.
 *
 * jsdom cannot catch that: it has no layout, so it has no hit testing. Only a
 * real browser can say whether the pixel a reader aims at belongs to the
 * control they are aiming at.
 *
 * `click({ trial: true })` is the assertion: it runs Playwright's actionability
 * checks — visible, stable, **receives events**, enabled — and stops before
 * pressing anything. That matters here, because both rows open something the
 * operating system owns (a file dialog, a screen picker) and a test that opened
 * one would hang waiting for a human.
 */

let email = ""

test.beforeEach(async ({ page }) => {
  email = newEmail()
  await signUp(page, email)
  await page.goto("/")
  await expect(page.getByLabel("Hỏi VisgniteAI")).toBeVisible()
})

test.afterEach(async ({ request }) => {
  await purge(request, email)
})

test("both live rows of the attach menu can actually be pressed", async ({ page }) => {
  await page.getByRole("button", { name: "Đính kèm" }).click()

  const addFile = page.getByRole("menuitem", { name: /Thêm tệp hoặc ảnh/ })
  const capture = page.getByRole("menuitem", { name: /Chụp màn hình/ })

  await expect(addFile).toBeVisible()
  await expect(capture).toBeVisible()

  // Nothing may sit between the reader and either row.
  await addFile.click({ trial: true })
  await capture.click({ trial: true })
})

test("a press outside still closes the menu, and the trigger still toggles it", async ({
  page,
}) => {
  // The scrim used to do this. Losing dismissal would be a fair price to
  // notice, so it is asserted rather than assumed.
  const trigger = page.getByRole("button", { name: "Đính kèm" })
  const addFile = page.getByRole("menuitem", { name: /Thêm tệp hoặc ảnh/ })

  await trigger.click()
  await expect(addFile).toBeVisible()

  await page.getByLabel("Hỏi VisgniteAI").click()
  await expect(addFile).not.toBeVisible()

  // And the trigger closes what it opened rather than reopening it: the press
  // that dismisses and the press that toggles are the same press.
  await trigger.click()
  await expect(addFile).toBeVisible()
  await trigger.click()
  await expect(addFile).not.toBeVisible()
})

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

test("an attachment survives the Next proxy byte for byte, both ways", async ({ page }) => {
  /**
   * The proxy is the third hop, and it is where bytes go wrong quietly.
   *
   * Before this path was opened it had four faults, and the worst had no status
   * code and no log: the response helper called `await response.text()`, which
   * decodes as UTF-8 and replaces every byte the decoder cannot represent. An
   * image came back the right length-ish, the right content type, and corrupt.
   * Nothing short of comparing the bytes says so — which is why this compares
   * the bytes, in both directions, through the real production build.
   */
  const result = await page.evaluate(async () => {
    // A real PNG, built in the page so the sent bytes are known exactly.
    const width = 200
    const height = 150
    const scan: number[] = []
    for (let y = 0; y < height; y++) {
      scan.push(0)
      for (let x = 0; x < width * 3; x++) scan.push((x * 7 + y * 13) & 255)
    }
    const deflated = new Uint8Array(
      await new Response(
        new Blob([new Uint8Array(scan)]).stream().pipeThrough(new CompressionStream("deflate")),
      ).arrayBuffer(),
    )
    const table = [...Array(256).keys()].map((n) => {
      let c = n
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
      return c >>> 0
    })
    const crc = (b: Uint8Array) => {
      let c = 0xffffffff
      for (const x of b) c = table[(c ^ x) & 255] ^ (c >>> 8)
      return (c ^ 0xffffffff) >>> 0
    }
    const u32 = (n: number) => [n >>> 24 & 255, n >>> 16 & 255, n >>> 8 & 255, n & 255]
    const chunk = (type: string, data: number[]) => {
      const body = [...new TextEncoder().encode(type), ...data]
      return [...u32(data.length), ...body, ...u32(crc(new Uint8Array(body)))]
    }
    const bytes = new Uint8Array([
      137, 80, 78, 71, 13, 10, 26, 10,
      ...chunk("IHDR", [...u32(width), ...u32(height), 8, 2, 0, 0, 0]),
      ...chunk("IDAT", [...deflated]),
      ...chunk("IEND", []),
    ])
    const digest = async (b: Uint8Array) =>
      [...new Uint8Array(await crypto.subtle.digest("SHA-256", b as BufferSource))]
        .map((x) => x.toString(16).padStart(2, "0"))
        .join("")

    const form = new FormData()
    form.append("file", new File([bytes as BufferSource], "round-trip.png", { type: "image/png" }))
    const up = await fetch("/api/alpha-desk/attachments", { method: "POST", body: form })
    const meta = await up.json()
    const down = await fetch(`/api/alpha-desk/attachments/${meta.id}`)
    const got = new Uint8Array(await down.arrayBuffer())

    return {
      upStatus: up.status,
      downStatus: down.status,
      mediaType: meta.media_type,
      sentLength: bytes.length,
      gotLength: got.length,
      sentHash: await digest(bytes),
      gotHash: await digest(got),
      contentType: down.headers.get("content-type"),
      noSniff: down.headers.get("x-content-type-options"),
      disposition: down.headers.get("content-disposition"),
    }
  })

  expect(result.upStatus).toBe(201)
  expect(result.downStatus).toBe(200)
  expect(result.mediaType).toBe("image/png")
  // The bytes, not their length and not their type: a UTF-8 round trip changes
  // the content while leaving both of those looking right.
  expect(result.gotLength).toBe(result.sentLength)
  expect(result.gotHash).toBe(result.sentHash)
  // Phase 05 sets these and phase 02 has to let them through the proxy.
  expect(result.contentType).toContain("image/png")
  expect(result.noSniff).toBe("nosniff")
  expect(result.disposition).toContain("round-trip.png")
})

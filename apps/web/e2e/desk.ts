import { expect, type APIRequestContext, type Page } from "@playwright/test"

/**
 * Driving the desk from outside it: an account, a Turn, and the control surface.
 *
 * Everything here goes through something a user or an operator could do — the
 * registration form, the composer, the `/e2e` control endpoints the harness
 * mounts on the FastAPI process. Nothing reaches into React state, and nothing
 * stubs a network call: a test that mocked the transport would be testing the
 * mock, which is exactly the gap this acceptance exists to close.
 */

export const API_ORIGIN = `http://127.0.0.1:${process.env.E2E_API_PORT ?? 8010}`

/**
 * The one control only a *canonical* assistant message carries.
 *
 * A flag names a message id, and the draft above it does not have one yet, so
 * the flag control is mounted on the persisted message and nowhere else. Seeing
 * it is how the test knows the draft was replaced rather than added to.
 *
 * It replaced the Risk Notice in this role when the notice was taken off the
 * surface: the notice is still attached in the terminal transaction, it is just
 * no longer something on screen to assert against.
 */
export const CANONICAL_MARK = { role: "button" as const, name: "Báo lỗi câu trả lời" }

export function newEmail(): string {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`
}

/** Register through the real form, which is what puts the session cookies on. */
export async function signUp(page: Page, email: string): Promise<void> {
  await page.goto("/register")
  await page.fill("#email", email)
  await page.fill("#password", "sup3r-secret-pw")
  await page.click('button[type="submit"]')
  await page.waitForURL((url) => !url.pathname.startsWith("/register"), {
    timeout: 30_000,
  })
}

export async function purge(request: APIRequestContext, email: string): Promise<void> {
  await request.post(`${API_ORIGIN}/e2e/purge`, { data: { email } })
}

/** Forget the previous Turn before steering the next one. */
export async function resetTurn(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/e2e/reset`)
  expect(response.ok()).toBeTruthy()
}

/**
 * Ask the question, and wait until the Turn is actually executing.
 *
 * The retry is not flake-hiding. The composer is a server-rendered form that
 * only becomes interactive when React hydrates, and a value typed into it
 * before then is a value the component never learns about — the field would
 * read as filled while `Send` stayed disabled. Retrying until the control is
 * enabled is how a test waits for hydration without asserting on it.
 */
export async function ask(
  page: Page,
  request: APIRequestContext,
  text: string,
): Promise<void> {
  const field = page.getByLabel("Ask Alpha Desk")
  const send = page.getByRole("button", { name: "Send" })

  await expect(async () => {
    await field.fill(text)
    await expect(send).toBeEnabled({ timeout: 1_000 })
  }).toPass({ timeout: 30_000 })

  await send.click()
  const started = await request.post(`${API_ORIGIN}/e2e/turn/wait`)
  expect(started.ok(), "the Turn should have started executing").toBeTruthy()
}

export async function say(request: APIRequestContext, text: string): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/e2e/turn/say`, { data: { text } })
  expect(response.ok()).toBeTruthy()
}

/** Publish activity events and nothing else, to fill a subscriber's queue. */
export async function churn(
  request: APIRequestContext,
  count: number,
): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/e2e/turn/churn`, {
    data: { count },
  })
  expect(response.ok()).toBeTruthy()
}

export async function finish(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/e2e/turn/finish`)
  expect(response.ok()).toBeTruthy()
}

/** The Turn this tab is watching, read from where the desk remembers it. */
export async function liveTurnId(page: Page): Promise<string> {
  const turnId = await page.evaluate(() => {
    const raw = window.sessionStorage.getItem("alpha-desk.session")
    return raw ? (JSON.parse(raw).turnId as string | null) : null
  })
  expect(turnId, "the desk should have remembered its live Turn").toBeTruthy()
  return turnId as string
}

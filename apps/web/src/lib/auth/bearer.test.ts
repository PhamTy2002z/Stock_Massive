/**
 * One refresh, however many callers meet the same expired token.
 *
 * `single-flight.test.ts` proves the primitive. This proves the wiring, which
 * is the part that can silently come undone: `rotateAccessToken` is the export
 * every route handler calls, and rebuilding it as a plain `async function` that
 * awaits the cookie first would read as a harmless tidy-up and reopen the race.
 *
 * The race matters here because the refresh token **rotates** — exchanging it
 * invalidates it. Two Alpha Desk tabs subscribing to the same Turn meet one
 * expired access token in the same instant; a second exchange would be handed a
 * token the API has already retired, and its `401` signs the user out
 * mid-conversation.
 */

import { beforeEach, describe, expect, it, vi } from "vitest"

const refresh = vi.fn()
const getRefreshToken = vi.fn<() => Promise<string | undefined>>()
const setSessionCookies = vi.fn<(tokens: unknown) => Promise<void>>()
const clearSessionCookies = vi.fn<() => Promise<void>>()

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api")
  return { ...actual, refresh: (token: string) => refresh(token) }
})

vi.mock("./session", () => ({
  getRefreshToken: () => getRefreshToken(),
  setSessionCookies: (tokens: unknown) => setSessionCookies(tokens),
  clearSessionCookies: () => clearSessionCookies(),
  getAccessToken: async () => undefined,
}))

const { rotateAccessToken } = await import("./bearer")

/** A gate the test opens by hand, so "concurrent" is not a matter of timing. */
function gate() {
  let open!: () => void
  const opened = new Promise<void>((resolve) => {
    open = resolve
  })
  return { open, opened }
}

beforeEach(() => {
  vi.clearAllMocks()
  getRefreshToken.mockResolvedValue("refresh-1")
  setSessionCookies.mockResolvedValue(undefined)
})

describe("two subscribes racing an expired token", () => {
  it("perform one refresh between them, and share its answer", async () => {
    const exchange = gate()
    refresh.mockImplementation(async () => {
      await exchange.opened
      return { access_token: "access-2", refresh_token: "refresh-2", expires_in: 900 }
    })

    // Both start before either can finish, which is the whole of the scenario.
    const first = rotateAccessToken()
    const second = rotateAccessToken()
    exchange.open()

    expect(await first).toBe("access-2")
    expect(await second).toBe("access-2")
    expect(refresh).toHaveBeenCalledTimes(1)
    // And the rotated pair is written once, not twice with the same values.
    expect(setSessionCookies).toHaveBeenCalledTimes(1)
  })

  it("exchanges again for a caller that arrives after the first settled", async () => {
    refresh.mockResolvedValue({
      access_token: "access-2",
      refresh_token: "refresh-2",
      expires_in: 900,
    })

    await rotateAccessToken()
    await rotateAccessToken()

    // The single flight is a window, not a cache: a later 401 is a new question
    // about a cookie that has since changed.
    expect(refresh).toHaveBeenCalledTimes(2)
  })
})

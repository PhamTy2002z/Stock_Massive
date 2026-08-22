/**
 * One refresh, however many callers meet the same expired token.
 *
 * `single-flight.test.ts` proves the primitive. This proves the wiring, which
 * is the part that can silently come undone: `rotateAccessToken` is the export
 * every route handler calls, and rebuilding it as a plain `async function` that
 * exchanges whatever the cookie says would read as a harmless tidy-up and
 * reopen the race.
 *
 * The race matters here because the refresh token **rotates**, and because the
 * upstream treats a second presentation of a spent token as a replayed
 * credential and revokes every session the user has. Cookies are per-request,
 * so every request already in the air when the access token expired carries the
 * same refresh token — the callers that must not exchange twice are not
 * hypothetical tabs, they are the sidebar and the rail and the transcript of one
 * page load.
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

const PAIR = { access_token: "access-2", refresh_token: "refresh-2", expires_in: 900 }

/**
 * A token nobody has spent yet.
 *
 * The memo inside `bearer` is module state with a one-minute window, which is
 * the behaviour under test — so each test brings its own token rather than
 * reaching in to clear it. One literal shared across tests would have them
 * answer each other out of the memo.
 */
let spent = 0
const freshToken = () => `refresh-${(spent += 1)}`

beforeEach(() => {
  vi.clearAllMocks()
  getRefreshToken.mockResolvedValue(freshToken())
  setSessionCookies.mockResolvedValue(undefined)
})

describe("two subscribes racing an expired token", () => {
  it("perform one refresh between them, and share its answer", async () => {
    const exchange = gate()
    refresh.mockImplementation(async () => {
      await exchange.opened
      return PAIR
    })

    // Both start before either can finish, which is the whole of the scenario.
    const first = rotateAccessToken()
    const second = rotateAccessToken()
    exchange.open()

    expect(await first).toBe("access-2")
    expect(await second).toBe("access-2")
    expect(refresh).toHaveBeenCalledTimes(1)
    // Both responses carry the pair. A caller that skipped the write would
    // answer its own request and leave the browser holding the spent token.
    expect(setSessionCookies).toHaveBeenCalledTimes(2)
  })

  it("does not exchange again for a caller holding the token already spent", async () => {
    refresh.mockResolvedValue(PAIR)

    await rotateAccessToken()
    // Its cookie jar was fixed when the browser sent it, so it still names the
    // same token — presenting that again is the replay the upstream punishes by
    // revoking every session this user has.
    await rotateAccessToken()

    expect(refresh).toHaveBeenCalledTimes(1)
    expect(clearSessionCookies).not.toHaveBeenCalled()
  })

  it("exchanges again once the browser has actually moved on", async () => {
    refresh.mockResolvedValue(PAIR)
    await rotateAccessToken()

    // A request sent after the rotated pair reached the browser carries the new
    // token, and that is a genuinely new question.
    getRefreshToken.mockResolvedValue(freshToken())
    await rotateAccessToken()

    expect(refresh).toHaveBeenCalledTimes(2)
  })
})

describe("a session that is genuinely over", () => {
  it("clears the cookies and reports no token", async () => {
    const { AuthApiError } = await import("./api")
    refresh.mockRejectedValue(new AuthApiError(401, "Invalid refresh token"))

    expect(await rotateAccessToken()).toBeNull()
    expect(clearSessionCookies).toHaveBeenCalledTimes(1)
    expect(setSessionCookies).not.toHaveBeenCalled()
  })

  it("keeps the session when the API is merely unreachable", async () => {
    // A 500 or a dead socket is not an answer about the user's session, and
    // signing them out over one would lose a conversation to a blip.
    refresh.mockRejectedValue(new Error("ECONNREFUSED"))

    await expect(rotateAccessToken()).rejects.toThrow("ECONNREFUSED")
    expect(clearSessionCookies).not.toHaveBeenCalled()
  })

  it("reports no token without touching the API when there is no cookie", async () => {
    getRefreshToken.mockResolvedValue(undefined)

    expect(await rotateAccessToken()).toBeNull()
    expect(refresh).not.toHaveBeenCalled()
    expect(clearSessionCookies).not.toHaveBeenCalled()
  })
})

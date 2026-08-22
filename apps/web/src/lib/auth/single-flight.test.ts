/**
 * One exchange per token, which is a stronger promise than one at a time.
 *
 * The upstream revokes every session a user has when a spent refresh token is
 * presented again, so "one concurrent exchange" is not enough: cookies are
 * per-request, so a straggler from the same burst arrives holding the same
 * already-spent token. Tested here rather than through the proxy, because
 * through the proxy the refresh itself would have to be mocked — and a test
 * that mocks the thing it is asserting about proves nothing.
 */

import { describe, expect, it, vi } from "vitest"

import { keyedSingleFlight } from "./single-flight"

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe("keyedSingleFlight", () => {
  it("runs the work once for callers that arrive together", async () => {
    const gate = deferred<string>()
    const work = vi.fn(() => gate.promise)
    const share = keyedSingleFlight(work, { ttlMs: 60_000 })

    const first = share("refresh-1")
    const second = share("refresh-1")
    gate.resolve("token-2")

    expect(await first).toBe("token-2")
    expect(await second).toBe("token-2")
    expect(work).toHaveBeenCalledTimes(1)
  })

  it("answers a caller that arrives after the work settled from the memo", async () => {
    // The case that signed users out: the second caller is not asking a new
    // question, it is holding the same spent token and would replay it.
    const work = vi.fn(async () => "token-2")
    const share = keyedSingleFlight(work, { ttlMs: 60_000 })

    expect(await share("refresh-1")).toBe("token-2")
    expect(await share("refresh-1")).toBe("token-2")

    expect(work).toHaveBeenCalledTimes(1)
  })

  it("runs again for a different key, because that is a different token", async () => {
    const work = vi.fn(async (key: string) => `for-${key}`)
    const share = keyedSingleFlight(work, { ttlMs: 60_000 })

    expect(await share("refresh-1")).toBe("for-refresh-1")
    expect(await share("refresh-2")).toBe("for-refresh-2")

    expect(work).toHaveBeenCalledTimes(2)
  })

  it("forgets an answer once its window has passed", async () => {
    const work = vi.fn(async () => "token")
    const share = keyedSingleFlight(work, { ttlMs: 5 })

    await share("refresh-1")
    await new Promise((resolve) => setTimeout(resolve, 20))
    await share("refresh-1")

    // Not a cache of credentials for the life of the process: the memo covers
    // one burst and then lets go.
    expect(work).toHaveBeenCalledTimes(2)
  })

  it("releases the slot when the work fails, and every caller sees the failure", async () => {
    // A rejected exchange spends nothing, so remembering it would make one bad
    // moment on the network outlive itself.
    const gate = deferred<string>()
    const work = vi.fn(() => gate.promise)
    const share = keyedSingleFlight(work, { ttlMs: 60_000 })

    const first = share("refresh-1")
    const second = share("refresh-1")
    gate.reject(new Error("refresh rejected"))

    await expect(first).rejects.toThrow("refresh rejected")
    await expect(second).rejects.toThrow("refresh rejected")

    const after = vi.fn(async () => "fresh")
    expect(await keyedSingleFlight(after, { ttlMs: 60_000 })("refresh-1")).toBe("fresh")
    expect(work).toHaveBeenCalledTimes(1)
  })
})

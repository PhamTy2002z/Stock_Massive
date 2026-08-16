/**
 * The one exchange several tabs share.
 *
 * ADR-0013 requires exactly one refresh between simultaneous subscribes, and
 * this is where that is true. Tested here rather than through the proxy,
 * because through the proxy the refresh itself would have to be mocked — and a
 * test that mocks the thing it is asserting about proves nothing.
 */

import { describe, expect, it, vi } from "vitest"

import { singleFlight } from "./single-flight"

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe("singleFlight", () => {
  it("runs the work once for callers that arrive together", async () => {
    const gate = deferred<string>()
    const work = vi.fn(() => gate.promise)
    const share = singleFlight(work)

    const first = share()
    const second = share()
    gate.resolve("token-2")

    expect(await first).toBe("token-2")
    expect(await second).toBe("token-2")
    expect(work).toHaveBeenCalledTimes(1)
  })

  it("runs again once the previous call has settled", async () => {
    // Not a lock: the point is one *concurrent* exchange, not one ever. A
    // later 401 is a genuinely new question about a genuinely new token.
    const work = vi.fn(async () => "token")
    const share = singleFlight(work)

    await share()
    await share()

    expect(work).toHaveBeenCalledTimes(2)
  })

  it("releases the slot when the work fails, and every caller sees the failure", async () => {
    // A rejected exchange that left the promise cached would make one dead
    // refresh token poison every later request for the life of the process.
    const gate = deferred<string>()
    const work = vi.fn(() => gate.promise)
    const share = singleFlight(work)

    const first = share()
    const second = share()
    gate.reject(new Error("refresh rejected"))

    await expect(first).rejects.toThrow("refresh rejected")
    await expect(second).rejects.toThrow("refresh rejected")

    const after = vi.fn(async () => "fresh")
    expect(await singleFlight(after)()).toBe("fresh")
    expect(work).toHaveBeenCalledTimes(1)
  })
})

/**
 * The classifier, against the four error classes that actually reach it.
 *
 * Written against the real constructors rather than against shaped literals:
 * the whole value of this module is that it reads what the network layer
 * genuinely throws, and a test using its own stand-ins would keep passing after
 * that layer changed shape.
 */

import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api"
import { AlphaRefusalError } from "@/lib/alpha"
import { AuthApiError } from "@/lib/auth/api"
import { ApiUnavailableError } from "@/lib/connection-status"
import { describeFailure, isTransient } from "@/lib/failure"

describe("describeFailure", () => {
  it("reads the status the same way whichever class carried it", () => {
    // Four layers, four error types, one meaning. This is the property the
    // module exists for: before it, each surface branched on whichever class
    // its own fetch happened to throw.
    const kinds = [
      new ApiError(403, "forbidden"),
      new AuthApiError(403, "forbidden"),
      new AlphaRefusalError(403, null, "forbidden"),
    ].map((error) => describeFailure(error).kind)

    expect(kinds).toEqual(["forbidden", "forbidden", "forbidden"])
  })

  it("separates an expired session from a refused one", () => {
    // The distinction the product got wrong for the longest: both are "you
    // cannot have this", but only one of them is fixed by signing in, and
    // offering that button for a 403 sends the reader round a loop.
    const expired = describeFailure(new ApiError(401, "unauthorized"))
    expect(expired.kind).toBe("session_expired")
    expect(expired.recovery).toBe("signin")

    const refused = describeFailure(new ApiError(403, "forbidden"))
    expect(refused.kind).toBe("forbidden")
    expect(refused.recovery).toBe("none")
    expect(refused.action).toBeNull()
  })

  it("offers no retry for anything that will answer the same way again", () => {
    for (const status of [403, 404]) {
      expect(isTransient(describeFailure(new ApiError(status, "no")))).toBe(false)
    }
    for (const status of [429, 500, 503]) {
      expect(isTransient(describeFailure(new ApiError(status, "later")))).toBe(true)
    }
  })

  it("treats a fetch that never connected as offline, not as a server fault", () => {
    // `ApiUnavailableError` carries no status when the request never left the
    // browser, and blaming the server for the reader's own dropped wifi is
    // both wrong and unactionable.
    const offline = describeFailure(new ApiUnavailableError(undefined, undefined))
    expect(offline.kind).toBe("offline")
    expect(offline.status).toBeNull()

    expect(describeFailure(new TypeError("Failed to fetch")).kind).toBe("offline")
  })

  it("reads the server's fault out of a retryable wrapper", () => {
    // A 503 arrives wrapped in the same class as an offline failure. The status
    // is what separates them, and losing it would tell a reader their network
    // is down when the API is the thing that fell over.
    const server = describeFailure(new ApiUnavailableError("down", 503))
    expect(server.kind).toBe("server")
    expect(server.status).toBe(503)
  })

  it("keeps the server's own sentence when it wrote one worth reading", () => {
    // A 422 carries a specific reason and no category could improve on it.
    const failure = describeFailure(
      new AlphaRefusalError(422, "budget_exhausted", "Ngân sách lượt đã hết."),
    )
    expect(failure.detail).toBe("Ngân sách lượt đã hết.")
    expect(failure.kind).toBe("request_failed")
  })

  it("reads a status off a layer it has never heard of", () => {
    // The structural contract, and the reason this module imports almost
    // nothing: naming each error class coupled the classifier to a module
    // behind `server-only` and broke the client build. A fifth transport can
    // arrive without editing `failure.ts`.
    class SomeFutureTransportError extends Error {
      constructor(readonly status: number) {
        super("from a layer that does not exist yet")
      }
    }

    expect(describeFailure(new SomeFutureTransportError(404)).kind).toBe("not_found")
  })

  it("ignores a status on something that is not an error at all", () => {
    // A `Response` has `.status` too. Only thrown errors are classified.
    const failure = describeFailure({ status: 404 })
    expect(failure.kind).toBe("request_failed")
    expect(failure.detail).toBe("")
  })

  it("never throws, whatever it is handed", () => {
    // It runs inside error boundaries. A classifier that threw would replace
    // the screen the reader is already unhappy with by a worse one.
    for (const thrown of [undefined, null, "a string", 42, {}, new Error("plain")]) {
      expect(() => describeFailure(thrown)).not.toThrow()
      expect(describeFailure(thrown).title).not.toBe("")
    }
  })

  it("gives every kind exactly one way out, and names it", () => {
    // The invariant the UI leans on: a surface reads `action` straight onto a
    // control, so a kind with a recovery and no label would render a nameless
    // button.
    const samples = [401, 403, 404, 429, 500, 422].map(
      (status) => describeFailure(new ApiError(status, "x")),
    )
    for (const failure of samples) {
      if (failure.recovery === "none") expect(failure.action).toBeNull()
      else expect(failure.action).toBeTruthy()
      expect(failure.title).not.toBe("")
      // A missing resource is the one kind that says nothing past its title:
      // there is no recovery to explain, and guessing at the cause misleads.
      if (failure.kind === "not_found") expect(failure.detail).toBe("")
      else expect(failure.detail).not.toBe("")
    }
  })
})

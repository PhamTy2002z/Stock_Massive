// @vitest-environment jsdom
/**
 * What the capture does, and what it refuses to do without being looked at.
 *
 * jsdom has no `getDisplayMedia`, so the stream is a stub — which is exactly the
 * risk this file has to name rather than hide. What it can prove: that a
 * dismissed picker is not an error, that the track is stopped, that a frame is
 * scaled before it is uploaded, and that an unsupported browser is detected
 * rather than pressed. What it cannot prove is that a real capture looks right;
 * that is the manual step in `phase-09`, and no number of these tests replaces
 * it.
 */

import { afterEach, describe, expect, it, vi } from "vitest"

import {
  MAX_CAPTURE_EDGE_PX,
  canCapture,
  captureFilename,
  captureScreen,
  scaledSize,
} from "./screen-capture"

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubDisplayMedia(impl: () => Promise<MediaStream>) {
  vi.stubGlobal("navigator", {
    ...navigator,
    mediaDevices: { getDisplayMedia: impl },
  })
}

/** A stream whose tracks record being stopped. */
function fakeStream() {
  const stopped: string[] = []
  const track = { kind: "video", stop: () => void stopped.push("video") }
  return { stream: { getTracks: () => [track] } as unknown as MediaStream, stopped }
}

describe("whether this browser can capture at all", () => {
  it("says no when the API is absent", () => {
    // Absent over plain HTTP, because the API needs a secure context. A control
    // that pressed anyway would be a control that does nothing and says nothing.
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined })

    expect(canCapture()).toBe(false)
  })

  it("says yes when it is there", () => {
    stubDisplayMedia(async () => fakeStream().stream)

    expect(canCapture()).toBe(true)
  })
})

describe("scaling a frame before it is uploaded", () => {
  it("leaves a frame already small enough alone", () => {
    expect(scaledSize(1_280, 720)).toEqual({ width: 1_280, height: 720 })
  })

  it("brings the long edge down to the limit, keeping the shape", () => {
    // A 4K full-screen capture is the ordinary case on a large display, and it
    // is past the per-file ceiling before it is scaled.
    expect(scaledSize(3_840, 2_160)).toEqual({
      width: MAX_CAPTURE_EDGE_PX,
      height: 1_080,
    })
  })

  it("scales by the long edge even when that is the height", () => {
    expect(scaledSize(1_000, 4_000)).toEqual({ width: 480, height: MAX_CAPTURE_EDGE_PX })
  })

  it("does not divide by zero on an empty frame", () => {
    expect(scaledSize(0, 0)).toEqual({ width: 0, height: 0 })
  })
})

describe("what the file is called", () => {
  it("says when it was taken", () => {
    expect(captureFilename(new Date(2026, 7, 29, 1, 14))).toBe(
      "chup-man-hinh-2026-08-29-0114.png",
    )
  })
})

describe("dismissing the browser's own picker", () => {
  it("is a cancellation and not an error", async () => {
    // A reader who changed their mind must not be handed an error message.
    stubDisplayMedia(() => Promise.reject(new DOMException("no", "NotAllowedError")))

    await expect(captureScreen()).resolves.toBeNull()
  })

  it("returns null rather than throwing when the API is missing", async () => {
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined })

    await expect(captureScreen()).resolves.toBeNull()
  })
})

describe("the sharing indicator", () => {
  it("goes out even when the frame cannot be drawn", async () => {
    // The failure this covers: an indicator left lit tells the reader they are
    // still sharing their screen when they are not, which is the interface
    // lying about a privacy state.
    const { stream, stopped } = fakeStream()
    stubDisplayMedia(async () => stream)
    // jsdom gives a video element with no dimensions and a canvas with no 2d
    // context, so the draw fails — which is the path under test.
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined)

    await captureScreen()

    expect(stopped).toEqual(["video"])
  })
})

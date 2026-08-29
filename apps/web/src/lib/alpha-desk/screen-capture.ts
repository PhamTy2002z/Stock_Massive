/**
 * One frame of a window or a screen, as a file.
 *
 * No library. `getDisplayMedia` gives a stream, a `<video>` element gives it a
 * decoded frame, and a canvas turns that frame into a PNG — four browser APIs
 * that already ship, against a dependency that would have to be audited and
 * kept.
 *
 * **The track is stopped the moment the frame is drawn.** Leaving it open keeps
 * the browser's screen-sharing indicator lit after the work is done, which tells
 * the reader they are still sharing when they are not. That is not a tidiness
 * issue; it is the interface lying about a privacy state.
 */

/** The long edge a capture is scaled down to before it is uploaded. */
export const MAX_CAPTURE_EDGE_PX = 1_920

/** JPEG would be smaller; PNG keeps text in a price table legible. */
const CAPTURE_TYPE = "image/png"

/** Whether this browser, on this origin, can capture at all. */
export function canCapture(): boolean {
  // A secure context is required, so `mediaDevices` is simply absent over plain
  // HTTP. Checked rather than assumed: a dead control that swallows the press is
  // worse than one that says it cannot.
  return typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getDisplayMedia === "function"
}

/** A filename that says when the picture was taken. */
export function captureFilename(now: Date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0")
  const stamp = [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()) + pad(now.getMinutes()),
  ].join("-")
  return `chup-man-hinh-${stamp}.png`
}

/** How big the drawn frame should be, keeping the aspect ratio. */
export function scaledSize(
  width: number,
  height: number,
  limit: number = MAX_CAPTURE_EDGE_PX,
): { width: number; height: number } {
  const longest = Math.max(width, height)
  if (longest <= limit || longest === 0) return { width, height }
  const factor = limit / longest
  return { width: Math.round(width * factor), height: Math.round(height * factor) }
}

/**
 * Ask for a window or a screen, and return one frame of it.
 *
 * `null` means the reader dismissed the browser's own picker. That is a
 * cancellation and not a failure: it must not raise, and it must not put an
 * error in front of somebody who simply changed their mind.
 */
export async function captureScreen(): Promise<File | null> {
  if (!canCapture()) return null
  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
  } catch {
    // `NotAllowedError` is the dismissal, and every other reason a browser
    // refuses here is equally not something the reader can act on.
    return null
  }

  try {
    const frame = await drawFrame(stream)
    return frame
  } finally {
    // In `finally`, so a failure to decode still puts the indicator out.
    for (const track of stream.getTracks()) track.stop()
  }
}

async function drawFrame(stream: MediaStream): Promise<File | null> {
  const video = document.createElement("video")
  video.srcObject = stream
  video.muted = true
  await video.play().catch(() => undefined)
  // A stream's first frame is not ready the instant `play` resolves, and a
  // canvas drawn before it is a black rectangle.
  if (video.videoWidth === 0) await nextFrame(video)

  const size = scaledSize(video.videoWidth, video.videoHeight)
  const canvas = document.createElement("canvas")
  canvas.width = size.width
  canvas.height = size.height
  const context = canvas.getContext("2d")
  if (context === null || size.width === 0) return null
  context.drawImage(video, 0, 0, size.width, size.height)

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, CAPTURE_TYPE),
  )
  if (blob === null) return null
  return new File([blob], captureFilename(), { type: CAPTURE_TYPE })
}

/** Wait for the stream to have a frame worth drawing. */
function nextFrame(video: HTMLVideoElement): Promise<void> {
  return new Promise((resolve) => {
    const done = () => resolve()
    video.addEventListener("loadeddata", done, { once: true })
    // A stream that never produces a frame must not hang the press forever.
    window.setTimeout(done, 1_500)
  })
}

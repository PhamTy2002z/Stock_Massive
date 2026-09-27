/**
 * Telling a reader who looked away that their answer has arrived.
 *
 * Only while the tab is hidden: a reader watching the answer arrive needs no
 * second signal, and a tone over text they are reading is noise. Both channels
 * are wishes stored in `preferences` — the browser's notification permission
 * still decides whether the first one may speak at all.
 */

import { readPreferences } from "./preferences"

/** Whether this browser can raise a system notification at all. */
export function notificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window
}

type AudioContextClass = typeof AudioContext

function audioContextClass(): AudioContextClass | null {
  if (typeof window === "undefined") return null
  const legacy = (window as Window & { webkitAudioContext?: AudioContextClass }).webkitAudioContext
  return window.AudioContext ?? legacy ?? null
}

/** Whether this browser can synthesise the completion tone. */
export function toneSupported(): boolean {
  return audioContextClass() !== null
}

/**
 * A short, soft two-note chime, synthesised rather than shipped as a file.
 *
 * Quiet on purpose (peak gain 0.08) and under half a second: it announces, it
 * does not alarm. A context the browser refuses to start is not an error the
 * reader can act on, so it is dropped.
 */
export function playAnswerTone(): void {
  const Context = audioContextClass()
  if (Context === null) return
  try {
    const context = new Context()
    const start = context.currentTime
    const gain = context.createGain()
    gain.connect(context.destination)
    gain.gain.setValueAtTime(0.0001, start)
    gain.gain.exponentialRampToValueAtTime(0.08, start + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.42)

    for (const [frequency, offset] of [
      [660, 0],
      [880, 0.12],
    ] as const) {
      const tone = context.createOscillator()
      tone.type = "sine"
      tone.frequency.setValueAtTime(frequency, start + offset)
      tone.connect(gain)
      tone.start(start + offset)
      tone.stop(start + 0.44)
    }

    void context.resume().catch(() => undefined)
    setTimeout(() => void context.close().catch(() => undefined), 600)
  } catch {
    // Autoplay policy or no audio device: silence is the only fallback.
  }
}

/**
 * Announce one settled Turn, if the reader is away and asked to be told.
 *
 * `tag` is the Turn id, so the system replaces a notification for the same
 * Turn rather than stacking a second one beside it.
 */
export function announceSettledTurn({
  turnId,
  title,
  answered,
}: {
  turnId: string
  title: string | null
  /** False when the Turn failed and there is no answer to read. */
  answered: boolean
}): void {
  if (typeof document === "undefined" || !document.hidden) return
  const preferences = readPreferences()

  if (
    preferences.notifyOnAnswer &&
    notificationsSupported() &&
    Notification.permission === "granted"
  ) {
    try {
      const notification = new Notification(title?.trim() || "VisgniteAI", {
        body: answered ? "Your answer is ready." : "The question wasn't answered. Reopen to try again.",
        tag: turnId,
      })
      notification.onclick = () => {
        window.focus()
        notification.close()
      }
    } catch {
      // Some mobile browsers only allow notifications from a service worker and
      // throw from the constructor. The tone below can still speak.
    }
  }

  if (preferences.soundOnAnswer) playAnswerTone()
}

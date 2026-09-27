"use client"

import * as React from "react"

import {
  notificationsSupported,
  playAnswerTone,
  toneSupported,
} from "@/lib/alpha-desk/answer-alert"
import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

import { SettingsRow, SettingsSection, Toggle } from "./settings-primitives"

/**
 * When the product may speak up about an answer the reader is not watching.
 *
 * Both signals fire only when a Turn settles while this tab is hidden
 * (`answer-alert.ts`, called from the one place the client learns a Turn
 * settled). Both are remembered on this browser alone, because the permission
 * and the speakers they depend on are this browser's too.
 */

type Permission = NotificationPermission | "unsupported"

function readPermission(): Permission {
  return notificationsSupported() ? Notification.permission : "unsupported"
}

function NotifyRow() {
  // Both read after mount: neither `localStorage` nor `Notification` exists
  // during the server render.
  const [wanted, setWanted] = React.useState(false)
  const [permission, setPermission] = React.useState<Permission | null>(null)
  const [asking, setAsking] = React.useState(false)

  React.useEffect(() => {
    setWanted(readPreferences().notifyOnAnswer)
    setPermission(readPermission())
  }, [])

  // On only when the browser agrees: a stored wish the site may not act on is
  // not a notification the reader will get.
  const on = wanted && permission === "granted"

  const change = async (next: boolean) => {
    if (!next) {
      setWanted(false)
      writePreferences({ notifyOnAnswer: false })
      return
    }
    let answer = readPermission()
    if (answer === "default") {
      setAsking(true)
      try {
        answer = await Notification.requestPermission()
      } catch {
        answer = readPermission()
      } finally {
        setAsking(false)
      }
    }
    setPermission(answer)
    const granted = answer === "granted"
    setWanted(granted)
    writePreferences({ notifyOnAnswer: granted })
  }

  const description =
    permission === "unsupported"
      ? "This browser doesn't support notifications."
      : permission === "denied"
        ? "Your browser is blocking notifications for this site. Allow them in your browser settings, then turn this back on."
        : "Notify me when an answer finishes while I'm on another tab or window."

  return (
    <SettingsRow label="Notify when an answer is ready" description={asking ? "Waiting for the browser to allow this…" : description}>
      <Toggle
        label="Notify when an answer is ready"
        checked={on}
        disabled={permission === null || permission === "unsupported" || permission === "denied" || asking}
        onChange={(next) => void change(next)}
      />
    </SettingsRow>
  )
}

function SoundRow() {
  const [on, setOn] = React.useState(false)
  const [supported, setSupported] = React.useState(true)

  React.useEffect(() => {
    setOn(readPreferences().soundOnAnswer)
    setSupported(toneSupported())
  }, [])

  return (
    <SettingsRow
      label="Sound when finished"
      description={
        supported
          ? "Play a short, soft sound when an answer finishes while you're on another tab."
          : "This browser can't play sound alerts."
      }
    >
      <Toggle
        label="Sound when finished"
        checked={on && supported}
        disabled={!supported}
        onChange={(next) => {
          setOn(next)
          writePreferences({ soundOnAnswer: next })
          // Heard once on the way in, so the reader knows what they turned on.
          if (next) playAnswerTone()
        }}
      />
    </SettingsRow>
  )
}

export function NotificationsSection() {
  return (
    <SettingsSection title="Notifications">
      <NotifyRow />
      <SoundRow />
    </SettingsSection>
  )
}

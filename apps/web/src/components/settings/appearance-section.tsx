"use client"

import * as React from "react"
import { Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import {
  applyMotion,
  readPreferences,
  writePreferences,
  type MotionPreference,
} from "@/lib/alpha-desk/preferences"

import { Segmented, SettingsRow, SettingsSection } from "./settings-primitives"

const MODES = [
  { value: "system", label: "System", icon: <Monitor className="size-4" strokeWidth={1.7} /> },
  { value: "light", label: "Light", icon: <Sun className="size-4" strokeWidth={1.7} /> },
  { value: "dark", label: "Dark", icon: <Moon className="size-4" strokeWidth={1.7} /> },
]

const MOTIONS: { value: MotionPreference; label: string }[] = [
  { value: "system", label: "System" },
  { value: "reduced", label: "Reduced" },
]

/** Whether the component has mounted, so stored choices can be read. */
function useMounted(): boolean {
  const [mounted, setMounted] = React.useState(false)
  React.useEffect(() => setMounted(true), [])
  return mounted
}

function ThemePicker() {
  const { theme, setTheme } = useTheme()

  // theme is read from localStorage, which the server render cannot see. Until
  // mount, no segment claims to be selected — otherwise the first paint marks
  // the wrong one and corrects itself a frame later.
  const mounted = useMounted()

  return (
    <Segmented
      label="Color mode"
      options={MODES}
      iconOnly
      selected={mounted ? (theme ?? null) : null}
      onSelect={setTheme}
    />
  )
}

/**
 * Whether this browser stills motion even where the system does not ask.
 *
 * `System` leaves the decision to the operating system's reduced-motion
 * setting; `Reduced` stills everything here regardless, including the word-by-word
 * reveal of an answer. The stylesheet reads the attribute `applyMotion` sets.
 */
function MotionPicker() {
  const [motion, setMotion] = React.useState<MotionPreference | null>(null)
  React.useEffect(() => setMotion(readPreferences().motion), [])

  return (
    <Segmented
      label="Motion"
      options={MOTIONS}
      selected={motion}
      onSelect={(next) => {
        setMotion(next)
        writePreferences({ motion: next })
        applyMotion(next)
      }}
    />
  )
}

/**
 * How the product looks on this browser.
 *
 * There is no up/down colour convention row. The Signal Desk chart is drawn by
 * the pinned Flint package onto a canvas with colours of its own choosing, and
 * the host may not rewrite what it compiles — so a swap of the CSS tokens would
 * recolour the text and leave the chart the other way round.
 */
export function AppearanceSection() {
  return (
    <SettingsSection title="Appearance">
      <SettingsRow label="Color mode">
        <ThemePicker />
      </SettingsRow>
      <SettingsRow
        label="Motion"
        description="Reduce motion when answers appear and elsewhere in the interface."
      >
        <MotionPicker />
      </SettingsRow>
    </SettingsSection>
  )
}

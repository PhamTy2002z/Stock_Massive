"use client"

import * as React from "react"

import { SIGNAL_DESK_PAUSED } from "@/components/shell/shell-state"
import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

import { SettingsRow, SettingsSection, Toggle } from "./settings-primitives"

/**
 * How a *new* conversation opens.
 *
 * The mode itself stays a property of each conversation and stays on the
 * composer, where the reader is when they change their mind about one answer.
 * What was missing is the other question — the one a Thread with no history
 * cannot answer — and until now it was always answered "Chat", silently, on
 * every new Thread, in every new tab.
 *
 * A wish, not an entitlement. The composer holds the single edge an entitlement
 * check attaches to, so a reader whose plan does not carry the desk meets the
 * same answer here as they would there.
 */
function DefaultDeskToggle() {
  // Read after mount, like the theme picker: `localStorage` is invisible to the
  // server render, and a switch that claimed to be on during the first paint
  // would correct itself a frame later.
  const [on, setOn] = React.useState(false)
  React.useEffect(() => setOn(readPreferences().signalDeskByDefault), [])

  return (
    <Toggle
      label={`${SIGNAL_DESK_COPY.name} is the default mode`}
      checked={on}
      onChange={(next) => {
        setOn(next)
        writePreferences({ signalDeskByDefault: next })
      }}
    />
  )
}

/**
 * The section holds one row, and that row only means something while the desk
 * can be opened — so a paused desk takes the whole section with it rather than
 * leaving a heading over nothing.
 */
export function ConversationSection() {
  if (SIGNAL_DESK_PAUSED) return null

  return (
    <SettingsSection title="Conversation">
      <SettingsRow
        label={`${SIGNAL_DESK_COPY.name} is the default mode`}
        description="New conversations open with the analysis pane already showing. Remembered on this browser; each conversation can still switch it from the composer."
      >
        <DefaultDeskToggle />
      </SettingsRow>
    </SettingsSection>
  )
}

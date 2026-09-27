"use client"

import * as React from "react"

import { Avatar } from "@/components/shell/primitives"
import { useAuth, useUpdateProfile, type InvestingStyle } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"

import {
  FIELD,
  PillAction,
  SelectField,
  SettingsRow,
  SettingsSection,
  TextField,
} from "./settings-primitives"

/** The longest custom instruction the account will keep. */
export const INSTRUCTIONS_LIMIT = 1500

const STYLES: { value: InvestingStyle | ""; label: string }[] = [
  { value: "", label: "Choose" },
  { value: "long_term", label: "Long-term / value" },
  { value: "growth", label: "Growth" },
  { value: "dividend", label: "Dividend" },
  { value: "swing", label: "Short-term swing" },
  { value: "learning", label: "Learning to invest" },
]

/**
 * The reader's standing instruction, saved on an explicit press.
 *
 * Unlike the one-line fields this does not save on blur: a paragraph is
 * written over several visits to the field, and saving each half-sentence
 * would make the assistant read drafts. Cancel and Save appear only once the text
 * differs from what is saved. The parent keys this on the saved text, so a
 * save — this one or another tab's — starts the field over from it.
 */
function InstructionsField({ saved, disabled }: { saved: string; disabled: boolean }) {
  const [draft, setDraft] = React.useState(saved)
  const update = useUpdateProfile()
  const dirty = draft !== saved

  const save = () =>
    update.mutate({
      preferences: { custom_instructions: draft.trim() === "" ? null : draft.trim() },
    })

  return (
    <div className="w-full">
      <textarea
        aria-label="Custom instructions"
        aria-describedby="instructions-count"
        rows={4}
        maxLength={INSTRUCTIONS_LIMIT}
        value={draft}
        disabled={disabled || update.isPending}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="e.g. prefer concise analysis, focus on liquidity and cash flow"
        className={cn(FIELD, "block min-h-[96px] resize-y py-2.5 leading-[1.55]")}
      />
      <div className="mt-2 flex min-h-8 items-center gap-2">
        <span id="instructions-count" className="text-meta tabular-nums text-ink-6">
          {draft.length}/{INSTRUCTIONS_LIMIT}
        </span>
        {dirty ? (
          <div className="ml-auto flex gap-2">
            <PillAction disabled={update.isPending} onClick={() => setDraft(saved)}>
              Cancel
            </PillAction>
            <PillAction disabled={update.isPending} onClick={save}>
              {update.isPending ? "Saving…" : "Save"}
            </PillAction>
          </div>
        ) : null}
      </div>
    </div>
  )
}

/**
 * Who is signed in, and what the assistant should know about them.
 *
 * Every field writes `PATCH /auth/me` with only the key it owns, so two fields
 * saved in quick succession cannot overwrite each other with stale values.
 */
export function ProfileSection() {
  const { user, isPending } = useAuth()
  const update = useUpdateProfile()

  const email = user?.email ?? ""
  const displayName = user?.full_name?.trim() || (email ? email.split("@")[0] : "")
  const initial = (displayName || "?").charAt(0).toUpperCase()
  const preferences = user?.preferences
  const unavailable = isPending || user === null

  return (
    <SettingsSection title="Profile">
      <SettingsRow label="Avatar">
        <Avatar initial={initial} className="size-10 text-row" />
      </SettingsRow>

      <SettingsRow label="Full name">
        <TextField
          label="Full name"
          value={user?.full_name ?? ""}
          placeholder={isPending ? "Loading…" : displayName}
          required
          disabled={unavailable}
          onCommit={(next) => update.mutateAsync({ full_name: next })}
        />
      </SettingsRow>

      <SettingsRow label="What should the system call you?">
        <TextField
          label="Nickname"
          value={preferences?.nickname ?? ""}
          placeholder={displayName || "Nickname"}
          disabled={unavailable}
          onCommit={(next) =>
            update.mutateAsync({ preferences: { nickname: next === "" ? null : next } })
          }
        />
      </SettingsRow>

      <SettingsRow label="What's your investing style?">
        <SelectField
          label="Investing style"
          value={preferences?.investing_style ?? ""}
          options={STYLES}
          disabled={unavailable || update.isPending}
          onChange={(next) =>
            update.mutate({
              preferences: { investing_style: next === "" ? null : (next as InvestingStyle) },
            })
          }
        />
      </SettingsRow>

      <SettingsRow
        label="Custom instructions"
        description="The system remembers this in every conversation. It's a presentation preference; it doesn't change source-verification rules."
        className="md:flex-col md:items-stretch"
      >
        <InstructionsField
          key={preferences?.custom_instructions ?? ""}
          saved={preferences?.custom_instructions ?? ""}
          disabled={unavailable}
        />
      </SettingsRow>
    </SettingsSection>
  )
}

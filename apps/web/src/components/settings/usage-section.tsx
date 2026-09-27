"use client"

import { useQuery } from "@tanstack/react-query"

import { fetchUsage } from "@/lib/alpha-desk/api"
import type { Allowance } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

import {
  AllowanceMeter,
  PillAction,
  ReadOnlyField,
  SettingsRow,
  SettingsSection,
  type MeterTone,
} from "./settings-primitives"

/**
 * What this account has used, against what it is allowed.
 *
 * It exists because the refusals it explains are otherwise invisible until they
 * land. A Turn stopped by `user_turn_starts_daily` or `user_spend_daily` reads
 * as a fault in the product when the reader had no way of seeing it coming, and
 * the numbers behind both were already being measured — just never shown to the
 * person they were measured about.
 *
 * **Not a bill.** These are operating limits on generation, not an amount owed,
 * and nothing here is a price the reader pays. The copy says so once, plainly,
 * rather than leaving a currency figure to imply the opposite.
 *
 * Read-only by nature. There is no version of this pane where the reader edits
 * their own ceiling, so it offers no controls and does not pretend to.
 */
export function UsageSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: queryKeys.usage,
    queryFn: fetchUsage,
    // The daily half stops being true at Vietnamese midnight and every Turn
    // moves the rest, so this is not cached for the life of the tab.
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  })

  return (
    <SettingsSection
      title="Usage"
      description="Operating limits on generating answers, not an amount owed."
    >
      {isError ? (
        <SettingsRow
          label="Couldn't load usage"
          description="The figures live on the server; the next try may be able to read them."
        >
          <PillAction onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Retrying…" : "Retry"}
          </PillAction>
        </SettingsRow>
      ) : (
        <>
          <SettingsRow
            label="Questions today"
            description="Resets at midnight Vietnam time."
          >
            <AllowanceCell
              label="Questions today"
              allowance={data?.turns_today}
              pending={isPending}
              format={(value) => `${value}`}
            />
          </SettingsRow>
          <SettingsRow
            label="Processing cost today"
            description="Today's compute cost, in US dollars."
          >
            <AllowanceCell
              label="Processing cost today"
              allowance={data?.spend_today_micro_usd}
              pending={isPending}
              format={usd}
            />
          </SettingsRow>
          <SettingsRow
            label="Processing cost, 30 days"
            description="A rolling window, releasing older questions as it goes."
          >
            <AllowanceCell
              label="Processing cost, 30 days"
              allowance={data?.spend_rolling_30d_micro_usd}
              pending={isPending}
              format={usd}
            />
          </SettingsRow>
        </>
      )}
    </SettingsSection>
  )
}

/**
 * One allowance, in whichever of its four states it is actually in.
 *
 * Loading, unlimited, and metered are three different things and none of them
 * may be drawn as another. An unlimited ceiling in particular must not render
 * as a full meter: the API reports a ceiling the deployment switched off as
 * `null`, and a subscription route switches all of them off.
 */
function AllowanceCell({
  label,
  allowance,
  pending,
  format,
}: {
  /** The row's own label, repeated onto the meter so it carries its own name. */
  label: string
  allowance: Allowance | undefined
  pending: boolean
  format: (value: number) => string
}) {
  if (pending || allowance === undefined) {
    return <ReadOnlyField value="Loading…" />
  }

  if (allowance.limit === null) {
    return <ReadOnlyField value={`${format(allowance.used)} · unlimited`} />
  }

  return (
    <AllowanceMeter
      label={label}
      value={allowance.used}
      ceiling={allowance.limit}
      tone={toneOf(allowance)}
      figure={`${format(allowance.used)} / ${format(allowance.limit)}`}
      note={remaining(allowance, format)}
    />
  )
}

/**
 * Micro-USD as the reader's own figure.
 *
 * Two decimals, and never rounded to `$0.00` while something has actually been
 * spent: a figure that reads as nothing beside a meter that has moved is the
 * one presentation guaranteed to look broken. Below a cent it says so instead.
 */
function usd(microUsd: number): string {
  if (microUsd === 0) return "$0"
  const dollars = microUsd / 1_000_000
  if (dollars < 0.01) return "<$0.01"
  return `$${dollars.toFixed(2)}`
}

function toneOf(allowance: Allowance): MeterTone {
  const limit = allowance.limit ?? 0
  if (limit <= 0) return "normal"
  if (allowance.used >= limit) return "spent"
  return allowance.used / limit >= 0.8 ? "caution" : "normal"
}

/**
 * What is left, said as a quantity rather than as a percentage.
 *
 * A reader deciding whether to ask one more question needs the count, not a
 * ratio. Once the allowance is gone the note carries the recovery instead — the
 * one moment where when-it-frees matters more than how-much-is-left.
 */
function remaining(allowance: Allowance, format: (value: number) => string): string {
  const limit = allowance.limit ?? 0
  const left = limit - allowance.used

  if (left <= 0) {
    const at = resetLabel(allowance.resets_at)
    return at === null ? "Allowance used up" : `Used up · opens again ${at}`
  }
  return `${format(left)} left`
}

/**
 * A reset moment in Vietnam time, or null when there is nothing to say.
 *
 * The two halves are formatted separately and joined here rather than left to
 * one `Intl` call, so the clock and the day always come out in the dd/mm,
 * 24-hour order this product uses, regardless of what a single combined
 * formatter would choose.
 */
function resetLabel(isoMoment: string | null): string | null {
  if (isoMoment === null) return null
  const moment = new Date(isoMoment)
  if (Number.isNaN(moment.getTime())) return null

  const options = { timeZone: "Asia/Ho_Chi_Minh" } as const
  const clock = new Intl.DateTimeFormat("en-GB", {
    ...options,
    hour: "2-digit",
    minute: "2-digit",
  }).format(moment)
  const day = new Intl.DateTimeFormat("en-GB", {
    ...options,
    day: "2-digit",
    month: "2-digit",
  }).format(moment)

  return `${clock} on ${day}`
}

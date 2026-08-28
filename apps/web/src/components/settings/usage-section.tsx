"use client"

import { useQuery } from "@tanstack/react-query"

import { fetchUsage } from "@/lib/alpha-desk/api"
import type { Allowance } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

import {
  AllowanceMeter,
  ReadOnlyField,
  SettingsPanel,
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
      title="Hạn mức"
      description="Mức sử dụng của tài khoản này so với hạn mức đang áp dụng. Đây là giới hạn vận hành cho việc tạo câu trả lời, không phải khoản phải trả."
    >
      <SettingsPanel
        footer={
          <p className="text-micro text-ink-6">
            Hạn mức ngày đặt lại vào 0h giờ Việt Nam. Cửa sổ 30 ngày nhả dần
            theo từng câu hỏi cũ.
          </p>
        }
      >
        {isError ? (
          <SettingsRow
            label="Không đọc được hạn mức"
            description="Số liệu nằm ở máy chủ; lần thử tiếp theo có thể đọc được."
          >
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="rounded-lg border border-border px-3 py-2 text-meta transition-colors hover:bg-accent disabled:opacity-60"
            >
              {isFetching ? "Đang thử lại…" : "Thử lại"}
            </button>
          </SettingsRow>
        ) : (
          <>
            <SettingsRow
              label="Câu hỏi hôm nay"
              description="Số câu hỏi đã gửi tới trợ lý trong ngày giao dịch hiện tại."
            >
              <AllowanceCell
                label="Câu hỏi hôm nay"
                allowance={data?.turns_today}
                pending={isPending}
                format={(value) => `${value}`}
              />
            </SettingsRow>
            <SettingsRow
              label="Chi phí xử lý hôm nay"
              description="Chi phí tính toán đã dùng trong ngày, quy về đô-la Mỹ."
            >
              <AllowanceCell
                label="Chi phí xử lý hôm nay"
                allowance={data?.spend_today_micro_usd}
                pending={isPending}
                format={usd}
              />
            </SettingsRow>
            <SettingsRow
              label="Chi phí xử lý 30 ngày"
              description="Cửa sổ lăn 30 ngày, tính từ thời điểm hiện tại."
            >
              <AllowanceCell
                label="Chi phí xử lý 30 ngày"
                allowance={data?.spend_rolling_30d_micro_usd}
                pending={isPending}
                format={usd}
              />
            </SettingsRow>
          </>
        )}
      </SettingsPanel>
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
    return <ReadOnlyField value="Đang tải…" />
  }

  if (allowance.limit === null) {
    return <ReadOnlyField value={`${format(allowance.used)} · không giới hạn`} />
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
  if (dollars < 0.01) return "<$0,01"
  return `$${dollars.toFixed(2).replace(".", ",")}`
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
    return at === null ? "Đã dùng hết hạn mức" : `Đã dùng hết · mở lại ${at}`
  }
  return `Còn ${format(left)}`
}

/**
 * A reset moment in Vietnamese time, or null when there is nothing to say.
 *
 * The two halves are formatted separately and joined here rather than left to
 * one `Intl` call: asked for both, `vi-VN` returns the clock before the date
 * and separates the date with a dash — "11:00 12-09" — which is neither the
 * order nor the separator a Vietnamese reader expects for a moment.
 */
function resetLabel(isoMoment: string | null): string | null {
  if (isoMoment === null) return null
  const moment = new Date(isoMoment)
  if (Number.isNaN(moment.getTime())) return null

  const options = { timeZone: "Asia/Ho_Chi_Minh" } as const
  const clock = new Intl.DateTimeFormat("vi-VN", {
    ...options,
    hour: "2-digit",
    minute: "2-digit",
  }).format(moment)
  const day = new Intl.DateTimeFormat("vi-VN", {
    ...options,
    day: "2-digit",
    month: "2-digit",
  }).format(moment)

  return `${clock} ngày ${day}`
}

"use client"

import type { ChangeEvent } from "react"

import {
  MONITOR_EXCHANGES,
  MONITOR_HORIZONS,
  MONITOR_LENSES,
  type MarketMonitorUrlApi,
  type MonitorLens,
} from "@/lib/market-monitor/url-state"
import { cn } from "@/lib/utils"
import { CoverageLine } from "./monitor-primitives"
import { useMonitorStatus } from "./monitor-status"

const LABELS: Record<MonitorLens, string> = {
  overview: "Tổng quan",
  breadth: "Độ rộng",
  flow: "Dòng tiền",
  sectors: "Ngành",
  stocks: "Cổ phiếu",
}

interface MonitorNavigationProps {
  url: MarketMonitorUrlApi
}

export function MonitorNavigation({ url }: MonitorNavigationProps) {
  const { state } = url
  const status = useMonitorStatus()
  return (
    <div className="sticky top-0 z-20 border-b border-border bg-background px-3.5 pb-2.5 pt-1.5 sm:px-5">
      <div className="mx-auto max-w-[1560px]">
        <div className="hidden items-center gap-1 md:flex" role="tablist" aria-label="Góc nhìn thị trường">
          {MONITOR_LENSES.map((lens) => (
            <button
              key={lens}
              type="button"
              role="tab"
              id={`monitor-tab-${lens}`}
              aria-controls={`monitor-panel-${lens}`}
              aria-selected={state.lens === lens}
              tabIndex={state.lens === lens ? 0 : -1}
              onClick={() => url.setLens(lens)}
              onKeyDown={(event) => {
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
                event.preventDefault()
                const current = MONITOR_LENSES.indexOf(lens)
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? MONITOR_LENSES.length - 1
                      : (current + (event.key === "ArrowRight" ? 1 : -1) + MONITOR_LENSES.length) %
                        MONITOR_LENSES.length
                url.setLens(MONITOR_LENSES[next])
                requestAnimationFrame(() => {
                  document.querySelector<HTMLElement>(`[role="tab"][aria-selected="true"]`)?.focus()
                })
              }}
              className={cn(
                "rounded-control px-3 py-2 text-control text-ink-5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                state.lens === lens && "bg-foreground/[0.075] text-ink-1",
              )}
            >
              {LABELS[lens]}
            </button>
          ))}
        </div>

        <label className="grid gap-1 md:hidden">
          <span className="text-micro text-ink-5">Chế độ xem</span>
          <select
            aria-label="Góc nhìn thị trường"
            value={state.lens}
            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
              url.setLens(event.target.value as MonitorLens)
            }
            className="h-9 w-full rounded-control border border-border bg-surface-sunken px-3 text-control text-ink-1 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {MONITOR_LENSES.map((lens) => (
              <option key={lens} value={lens}>
                {LABELS[lens]}
              </option>
            ))}
          </select>
        </label>

        <div className="mt-2 flex items-center gap-2 overflow-x-auto pb-0.5" aria-label="Phạm vi thị trường">
          <SegmentedControl
            label="Sàn"
            values={MONITOR_EXCHANGES}
            value={state.exchange}
            render={(value) => (value === "ALL" ? "HOSE + HNX" : value)}
            onChange={(exchange) => url.replace({ exchange })}
          />
          <SegmentedControl
            label="Kỳ"
            values={MONITOR_HORIZONS}
            value={state.horizon}
            render={(value) => `${value}P`}
            onChange={(horizon) => url.replace({ horizon })}
          />
          <label className="ml-auto flex h-8 shrink-0 items-center gap-2 rounded-control border border-border bg-surface-sunken px-2.5 text-meta text-ink-5">
            <span>Tại ngày</span>
            <input
              type="date"
              aria-label="Ngày dữ liệu"
              value={state.asOf ?? ""}
              max={new Date(Date.now() + 7 * 60 * 60 * 1000).toISOString().slice(0, 10)}
              onChange={(event) => url.replace({ asOf: event.target.value || null })}
              className="bg-transparent font-mono text-meta text-ink-2 outline-none"
            />
          </label>
          {status.meta && <div className="hidden shrink-0 xl:block"><CoverageLine meta={status.meta} updating={status.updating} /></div>}
        </div>
        {status.meta && status.meta.state !== "complete" && <div className="mt-2 xl:hidden"><CoverageLine meta={status.meta} updating={status.updating} /></div>}
      </div>
    </div>
  )
}

interface SegmentedControlProps<T extends string | number> {
  label: string
  values: readonly T[]
  value: T
  render: (value: T) => string
  onChange: (value: T) => void
}

function SegmentedControl<T extends string | number>({
  label,
  values,
  value,
  render,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div className="flex h-8 items-center rounded-control border border-border bg-surface-sunken p-0.5" aria-label={label}>
      {values.map((item) => (
        <button
          key={item}
          type="button"
          aria-pressed={item === value}
          onClick={() => onChange(item)}
          className={cn(
            "h-7 rounded-[7px] px-2.5 text-meta text-ink-5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            item === value && "bg-foreground/[0.08] text-ink-1",
          )}
        >
          {render(item)}
        </button>
      ))}
    </div>
  )
}

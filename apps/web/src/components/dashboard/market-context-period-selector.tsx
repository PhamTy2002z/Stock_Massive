"use client"

import { Button } from "@/components/ui/button"
import type { MarketContextPeriod } from "@/lib/api"

interface PeriodSelectorProps {
  value: MarketContextPeriod
  onChange: (period: MarketContextPeriod) => void
}

const PERIODS: { value: MarketContextPeriod; label: string }[] = [
  { value: "1M", label: "1M" },
  { value: "3M", label: "3M" },
  { value: "6M", label: "6M" },
  { value: "1Y", label: "1Y" },
]

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <div className="flex gap-1" role="group" aria-label="Period selector">
      {PERIODS.map((period) => (
        <Button
          key={period.value}
          variant={value === period.value ? "default" : "outline"}
          size="sm"
          onClick={() => onChange(period.value)}
          className="min-w-[48px]"
          aria-pressed={value === period.value}
        >
          {period.label}
        </Button>
      ))}
    </div>
  )
}

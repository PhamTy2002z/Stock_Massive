"use client"

import * as React from "react"
import { Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { cn } from "@/lib/utils"
import { SettingsPanel, SettingsRow, SettingsSection } from "./settings-primitives"

const MODES = [
  { value: "light", label: "Sáng", icon: Sun },
  { value: "dark", label: "Tối", icon: Moon },
  { value: "system", label: "Hệ thống", icon: Monitor },
] as const

function ThemePicker() {
  const { theme, setTheme } = useTheme()

  // theme is read from localStorage, which the server render cannot see. Until
  // mount, no segment claims to be selected — otherwise the first paint marks
  // the wrong one and corrects itself a frame later.
  const [mounted, setMounted] = React.useState(false)
  React.useEffect(() => setMounted(true), [])

  return (
    <div
      role="radiogroup"
      aria-label="Chế độ màu"
      className="flex w-full gap-1 rounded-full border border-hairline bg-surface-sunken p-1 md:w-auto"
    >
      {MODES.map(({ value, label, icon: Icon }) => {
        const selected = mounted && theme === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => setTheme(value)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-full px-3.5 py-1.5 text-meta font-medium leading-[1.29] outline-none transition-[background-color,color,transform] duration-150 focus-visible:ring-2 focus-visible:ring-interactive-strong active:scale-95 md:flex-none",
              selected
                // Ink on emerald, never white — the filled control is a lit
                // surface with dark type, not a coloured chip.
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-[15px]" />
            {label}
          </button>
        )
      })}
    </div>
  )
}

/** A quote block in miniature — the fastest way to judge a theme is on the
 *  numbers, where up and down have to stay apart on both surfaces. */
function QuotePreview() {
  return (
    <div className="w-full rounded-card border border-hairline bg-background p-4 md:w-[320px]">
      <div className="flex items-baseline justify-between">
        <span className="text-[0.95rem] font-semibold">
          VNM
        </span>
        <span className="text-micro text-muted-foreground">
          HOSE
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-[21px] font-semibold leading-[1.19] tabular-nums">
          64.200
        </span>
        <span className="text-meta font-semibold leading-[1.29] tabular-nums text-positive">
          +1,42%
        </span>
      </div>
      <div className="mt-2 flex items-center gap-3 text-micro tabular-nums">
        <span className="text-ceiling">Trần 68.650</span>
        <span className="text-floor">Sàn 59.750</span>
      </div>
    </div>
  )
}

export function AppearanceSection() {
  return (
    <SettingsSection
      id="appearance"
      title="Giao diện"
      description="Chế độ màu áp dụng cho toàn bộ hệ thống và được nhớ trên trình duyệt này."
    >
      <SettingsPanel
        footer={
          <p className="text-micro text-muted-foreground">
            Lựa chọn được lưu ngay khi bấm — không có bước xác nhận.
          </p>
        }
      >
        <SettingsRow
          label="Chế độ màu"
          description="Hệ thống sẽ đi theo cài đặt của thiết bị."
        >
          <ThemePicker />
        </SettingsRow>
        <SettingsRow
          label="Xem trước"
          description="Một thẻ giá thu nhỏ, để kiểm tra sắc tăng giảm trên nền hiện tại."
        >
          <QuotePreview />
        </SettingsRow>
      </SettingsPanel>
    </SettingsSection>
  )
}

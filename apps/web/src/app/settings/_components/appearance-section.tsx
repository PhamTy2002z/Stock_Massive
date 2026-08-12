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

/** The ramp the two themes disagree about, shown so a change is visible here. */
const SWATCHES = [
  { token: "--background", label: "Nền trang", className: "bg-background" },
  { token: "--card", label: "Bề mặt", className: "bg-card" },
  { token: "--muted", label: "Nền phụ", className: "bg-muted" },
  { token: "--interactive", label: "Tương tác", className: "bg-interactive" },
  { token: "--positive", label: "Tăng", className: "bg-positive" },
  { token: "--negative", label: "Giảm", className: "bg-negative" },
]

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
      className="flex w-full gap-1 rounded-full border border-[hsl(var(--hairline))] bg-muted/60 p-1 md:w-auto"
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
              "flex flex-1 items-center justify-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px] font-medium leading-[1.29] tracking-[-0.208px] outline-none transition-[background-color,color,transform] duration-150 focus-visible:ring-2 focus-visible:ring-interactive-strong active:scale-95 md:flex-none",
              selected
                ? "bg-interactive text-white"
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

function PalettePreview() {
  return (
    <div className="flex flex-wrap gap-3">
      {SWATCHES.map(({ token, label, className }) => (
        <div key={token} className="flex items-center gap-2">
          <span
            aria-hidden
            className={cn(
              "size-6 rounded-lg border border-[hsl(var(--hairline))]",
              className
            )}
          />
          <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
            {label}
          </span>
        </div>
      ))}
    </div>
  )
}

/** A quote block in miniature — the fastest way to judge a theme is on the
 *  numbers, where up and down have to stay apart on both surfaces. */
function QuotePreview() {
  return (
    <div className="w-full rounded-[18px] border border-[hsl(var(--hairline))] bg-background p-4 md:w-[320px]">
      <div className="flex items-baseline justify-between">
        <span className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
          VNM
        </span>
        <span className="text-[11px] leading-[1.3] tracking-[-0.11px] text-muted-foreground">
          HOSE
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-[21px] font-semibold leading-[1.19] tracking-[-0.374px] tabular-nums">
          64.200
        </span>
        <span className="text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] tabular-nums text-positive">
          +1,42%
        </span>
      </div>
      <div className="mt-2 flex items-center gap-3 text-[11px] leading-[1.3] tracking-[-0.11px] tabular-nums">
        <span className="text-positive">Trần 68.650</span>
        <span className="text-negative">Sàn 59.750</span>
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
          <p className="text-[11px] leading-[1.3] tracking-[-0.11px] text-muted-foreground">
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
          label="Bảng màu"
          description="Các bề mặt và màu ngữ nghĩa của chế độ đang chọn."
        >
          <PalettePreview />
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

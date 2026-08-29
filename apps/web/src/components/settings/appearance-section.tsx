"use client"

import * as React from "react"
import { Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import {
  Segmented,
  SelectStub,
  SettingsRow,
  SettingsSection,
} from "./settings-primitives"

const MODES = [
  { value: "light", label: "Sáng", icon: <Sun className="size-[13px]" strokeWidth={1.7} /> },
  { value: "dark", label: "Tối", icon: <Moon className="size-[13px]" strokeWidth={1.7} /> },
  {
    value: "system",
    label: "Hệ thống",
    icon: <Monitor className="size-[13px]" strokeWidth={1.7} />,
  },
]

/** The two colour conventions a Vietnamese board is drawn in. */
const CONVENTIONS = [
  { value: "vn", label: "Xanh tăng", up: "bg-positive", down: "bg-negative" },
  { value: "intl", label: "Đỏ tăng", up: "bg-negative", down: "bg-positive" },
]

function ThemePicker() {
  const { theme, setTheme } = useTheme()

  // theme is read from localStorage, which the server render cannot see. Until
  // mount, no segment claims to be selected — otherwise the first paint marks
  // the wrong one and corrects itself a frame later.
  const [mounted, setMounted] = React.useState(false)
  React.useEffect(() => setMounted(true), [])

  return (
    <Segmented
      label="Chế độ màu"
      options={MODES}
      selected={mounted ? (theme ?? null) : null}
      onSelect={setTheme}
    />
  )
}

/**
 * Which way up is drawn.
 *
 * Vietnamese boards put green on a rising price and every surface in this
 * product follows them; the international convention is the reverse. The
 * segments are drawn because the reference asks for the choice, but the up and
 * down colours are read from tokens the whole app shares, so flipping them is a
 * palette change rather than a preference — hence inert until there is a token
 * swap behind it.
 */
function ConventionPicker() {
  return (
    <div
      role="radiogroup"
      aria-label="Sắc màu tăng giảm"
      aria-disabled="true"
      className="flex w-full gap-0.5 rounded-[11px] border border-hairline bg-surface-sunken p-[3px] md:w-auto"
    >
      {CONVENTIONS.map((convention, position) => (
        <span
          key={convention.value}
          role="radio"
          aria-checked={position === 0}
          aria-label={convention.label}
          className={
            position === 0
              ? "flex flex-1 cursor-not-allowed items-center justify-center gap-[0.45rem] rounded-[8px] bg-surface-menu px-3 py-1.5 text-control leading-[1.25] text-foreground shadow-sm md:flex-none"
              : "flex flex-1 cursor-not-allowed items-center justify-center gap-[0.45rem] rounded-[8px] px-3 py-1.5 text-control leading-[1.25] text-ink-6 md:flex-none"
          }
        >
          <span aria-hidden="true" className="flex gap-[2px]">
            <i className={`block size-2 rounded-[2px] ${convention.up}`} />
            <i className={`block size-2 rounded-[2px] ${convention.down}`} />
          </span>
          {convention.label}
        </span>
      ))}
    </div>
  )
}

/** A quote block in miniature — the fastest way to judge a theme is on the
 *  numbers, where up and down have to stay apart on both surfaces. */
function QuotePreview() {
  return (
    <div className="w-full rounded-card border border-hairline bg-surface-raised px-[15px] py-[13px] md:w-[230px]">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[0.95rem] font-medium">VNM</span>
        <span className="ml-auto text-eyebrow text-ink-6">HOSE</span>
      </div>
      <div className="mt-[0.45rem] flex items-baseline gap-2">
        <span className="font-mono text-[1.35rem] font-medium leading-[1.2] tracking-[-0.03em] tabular-nums">
          64.200
        </span>
        <span className="font-mono text-control tabular-nums text-positive">+1,42%</span>
      </div>
      <div className="mt-[0.45rem] flex gap-[0.9rem] font-mono text-micro tabular-nums">
        <span className="text-ceiling">Trần 68.650</span>
        <span className="text-floor">Sàn 59.750</span>
      </div>
    </div>
  )
}

export function AppearanceSection() {
  return (
    <SettingsSection
      title="Giao diện"
      description="Chế độ màu áp dụng cho toàn bộ hệ thống và được nhớ trên trình duyệt này."
      footer="Lựa chọn được lưu ngay khi bấm — không có bước xác nhận."
    >
      <SettingsRow
        label="Chế độ màu"
        description="Hệ thống sẽ đi theo cài đặt của thiết bị."
      >
        <ThemePicker />
      </SettingsRow>
      <SettingsRow
        label="Sắc màu tăng / giảm"
        description="Quy ước màu cho giá tăng và giảm trên bảng, biểu đồ."
        soon
      >
        <ConventionPicker />
      </SettingsRow>
      <SettingsRow
        label="Xem trước"
        description="Một thẻ giá thu nhỏ, để kiểm tra sắc tăng giảm trên nền hiện tại."
      >
        <QuotePreview />
      </SettingsRow>
      <SettingsRow
        label="Phông chữ số liệu"
        description="Áp dụng cho giá, khối lượng và bảng dữ liệu."
        soon
      >
        <SelectStub label="Phông chữ số liệu" value="JetBrains Mono" mono />
      </SettingsRow>
    </SettingsSection>
  )
}

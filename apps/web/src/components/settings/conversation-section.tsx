"use client"

import * as React from "react"
import { MessagesSquare, PanelRight } from "lucide-react"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"
import { cn } from "@/lib/utils"

import { SettingsPanel, SettingsRow, SettingsSection } from "./settings-primitives"

const MODES = [
  { value: false, label: SIGNAL_DESK_COPY.chatMode, icon: MessagesSquare },
  { value: true, label: SIGNAL_DESK_COPY.name, icon: PanelRight },
] as const

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
function DefaultModePicker() {
  // Read after mount, like the theme picker: `localStorage` is invisible to the
  // server render, and a segment that claimed to be selected during the first
  // paint would correct itself a frame later.
  const [selected, setSelected] = React.useState<boolean | null>(null)
  React.useEffect(() => setSelected(readPreferences().signalDeskByDefault), [])

  const choose = (value: boolean) => {
    setSelected(value)
    writePreferences({ signalDeskByDefault: value })
  }

  return (
    <div
      role="radiogroup"
      aria-label="Chế độ mở hội thoại mới"
      className="flex w-full gap-0.5 rounded-[11px] border border-hairline bg-background p-[3px] md:w-auto"
    >
      {MODES.map(({ value, label, icon: Icon }) => {
        const active = selected === value
        return (
          <button
            key={label}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => choose(value)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-[9px] px-3 py-1.5 text-meta leading-[1.29] outline-none transition-[background-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-ring md:flex-none",
              // The same raised neutral the theme picker uses. Two segmented
              // controls in one dialog that expressed selection differently
              // would read as two different kinds of control.
              active
                ? "bg-surface-menu text-foreground shadow-sm"
                : "text-ink-4 hover:text-foreground"
            )}
          >
            <Icon className="size-[15px]" strokeWidth={1.7} />
            {label}
          </button>
        )
      })}
    </div>
  )
}

export function ConversationSection() {
  return (
    <SettingsSection
      title="Hội thoại"
      description="Mặc định áp dụng cho hội thoại mới. Mỗi hội thoại vẫn đổi được chế độ ngay tại thanh nhập."
    >
      <SettingsPanel
        footer={
          <p className="text-micro text-ink-6">
            Mặc định được nhớ trên trình duyệt này — đăng nhập ở máy khác sẽ
            quay về Chat.
          </p>
        }
      >
        <SettingsRow
          label="Mở hội thoại mới ở"
          description="Signal Desk dựng bảng phân tích bên cạnh câu trả lời, khi câu hỏi cần tới số."
        >
          <DefaultModePicker />
        </SettingsRow>
      </SettingsPanel>
    </SettingsSection>
  )
}

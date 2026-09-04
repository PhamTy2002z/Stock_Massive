"use client"

import * as React from "react"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

import {
  SelectStub,
  SettingsRow,
  SettingsSection,
  Toggle,
} from "./settings-primitives"

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
      label={`${SIGNAL_DESK_COPY.name} là chế độ mặc định`}
      checked={on}
      onChange={(next) => {
        setOn(next)
        writePreferences({ signalDeskByDefault: next })
      }}
    />
  )
}

/**
 * The three rows the reference asks for that have nothing behind them.
 *
 * Follow-up suggestions, thread auto-naming and a completion sound are each a
 * turn-loop decision, not a browser one: none is read anywhere in the agent, so
 * a switch here would persist an opinion no code consults. They keep their
 * shape and say so.
 */
const UNBUILT = [
  {
    label: "Gợi ý sau mỗi câu trả lời",
    description: "Hiện 2–3 câu hỏi tiếp theo dưới mỗi câu trả lời.",
    checked: true,
  },
  {
    label: "Tự động đặt tên hội thoại",
    description: "Đặt tên ngắn gọn theo nội dung ngay sau câu hỏi đầu tiên.",
    checked: true,
  },
  {
    label: "Âm thanh khi phân tích xong",
    description: `Phát âm báo nhẹ khi ${SIGNAL_DESK_COPY.name} dựng xong.`,
    checked: false,
  },
]

export function ConversationSection() {
  return (
    <SettingsSection
      title="Hội thoại"
      description="Mặc định áp dụng cho hội thoại mới. Mỗi hội thoại vẫn đổi được chế độ ngay tại thanh nhập."
      footer="Mặc định được nhớ trên trình duyệt này — đăng nhập ở máy khác sẽ quay về Chat."
    >
      <SettingsRow
        label={`${SIGNAL_DESK_COPY.name} là chế độ mặc định`}
        description="Mỗi hội thoại mới mở sẵn bảng phân tích bên cạnh câu trả lời."
      >
        <DefaultDeskToggle />
      </SettingsRow>

      {UNBUILT.map((row) => (
        <SettingsRow key={row.label} label={row.label} description={row.description} soon>
          <Toggle label={row.label} checked={row.checked} disabled />
        </SettingsRow>
      ))}

      <SettingsRow
        label="Ngôn ngữ trả lời"
        description="Hệ thống sẽ ưu tiên trả lời bằng ngôn ngữ này."
        soon
      >
        <SelectStub label="Ngôn ngữ trả lời" value="Tiếng Việt" />
      </SettingsRow>
    </SettingsSection>
  )
}

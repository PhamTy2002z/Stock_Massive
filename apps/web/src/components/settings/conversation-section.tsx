"use client"

import {
  SelectStub,
  SettingsRow,
  SettingsSection,
  Toggle,
} from "./settings-primitives"

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
    label: "Âm thanh khi trả lời xong",
    description: "Phát âm báo nhẹ khi câu trả lời hoàn tất.",
    checked: false,
  },
]

export function ConversationSection() {
  return (
    <SettingsSection
      title="Hội thoại"
      description="Tuỳ chọn cho trải nghiệm hội thoại."
      footer="Tuỳ chọn được nhớ trên trình duyệt này."
    >
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

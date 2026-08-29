"use client"

import { SettingsRow, SettingsSection, Toggle } from "./settings-primitives"

/**
 * When the product is allowed to interrupt.
 *
 * Nothing here is wired. There is no notification transport in the product at
 * all — no push registration, no outbound mail on a Turn finishing, no schedule
 * that knows the trading session — so all three rows are drawn and marked. The
 * pane exists rather than being hidden because the choices are real product
 * commitments the reference makes, and a reader who goes looking for them
 * should find out that they are coming rather than that they are absent.
 */
const CHANNELS = [
  {
    label: "Thông báo trong ứng dụng",
    description: "Khi câu trả lời hoặc bảng phân tích dựng xong.",
    checked: true,
  },
  {
    label: "Email",
    description: "Thông báo quan trọng về tài khoản và bảo mật.",
    checked: false,
  },
  {
    label: "Im lặng ngoài phiên",
    description: "Không thông báo ngoài giờ giao dịch (9:00–15:00, T2–T6).",
    checked: true,
  },
]

export function NotificationsSection() {
  return (
    <SettingsSection
      title="Thông báo"
      description="Chọn kênh và thời điểm hệ thống được phép làm phiền bạn."
      footer="Chưa có kênh thông báo nào hoạt động — các lựa chọn dưới đây chỉ để xem trước."
    >
      {CHANNELS.map((channel) => (
        <SettingsRow
          key={channel.label}
          label={channel.label}
          description={channel.description}
          soon
        >
          <Toggle label={channel.label} checked={channel.checked} disabled />
        </SettingsRow>
      ))}
    </SettingsSection>
  )
}

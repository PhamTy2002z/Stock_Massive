"use client"

import { ReadOnlyField, SettingsPanel, SettingsRow, SettingsSection } from "./settings-primitives"

/**
 * Fixed facts about the platform rather than switches. They live here because
 * "why is this timestamp an hour off" is a settings question, even when the
 * answer is that the value is not configurable.
 */
export function SystemSection() {
  return (
    <SettingsSection
      title="Hệ thống"
      description="Các quy ước dữ liệu đang áp dụng cho mọi màn hình."
    >
      <SettingsPanel>
        <SettingsRow
          label="Múi giờ hiển thị"
          description="Mọi mốc thời gian và phiên giao dịch đều quy về giờ Việt Nam."
        >
          <ReadOnlyField value="Asia/Ho_Chi_Minh (UTC+7)" />
        </SettingsRow>
        <SettingsRow
          label="Sàn theo dõi"
          description="Phạm vi mã mà nền tảng thu thập và phục vụ."
        >
          <ReadOnlyField value="HOSE · HNX · UPCOM" />
        </SettingsRow>
      </SettingsPanel>
    </SettingsSection>
  )
}

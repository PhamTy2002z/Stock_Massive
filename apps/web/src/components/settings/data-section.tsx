"use client"

import {
  PillAction,
  SelectStub,
  SettingsRow,
  SettingsSection,
  Toggle,
} from "./settings-primitives"

/**
 * The conversation history, and what the reader may do with it.
 *
 * Every row is a write against `agent_thread` and its Turns, and none of the
 * four is built: there is no opt-out of persistence, no retention job, no
 * export pipeline, and no bulk delete. They are drawn because they are the
 * commitments the reference makes about the reader's own data, and a product
 * that stores conversations should say what it will let the reader do about
 * that even while the answer is "not yet".
 *
 * Deleting one conversation *is* built — it lives on each thread's own menu in
 * the sidebar, which is where a reader deleting one thing looks for it.
 */
export function DataSection() {
  return (
    <SettingsSection
      title="Dữ liệu"
      description="Lịch sử hội thoại và dữ liệu của bạn trên hệ thống."
      footer="Xóa một hội thoại đơn lẻ đã dùng được — mở menu của hội thoại đó ở thanh bên."
    >
      <SettingsRow
        label="Lưu lịch sử hội thoại"
        description="Tắt thì hội thoại mới không được lưu sau khi đóng."
        soon
      >
        <Toggle label="Lưu lịch sử hội thoại" checked disabled />
      </SettingsRow>

      <SettingsRow
        label="Tự động xóa hội thoại cũ"
        description="Xóa vĩnh viễn sau khoảng thời gian đã chọn."
        soon
      >
        <SelectStub label="Tự động xóa hội thoại cũ" value="Không tự xóa" />
      </SettingsRow>

      <SettingsRow
        label="Xuất dữ liệu"
        description="Nhận bản sao toàn bộ hội thoại và bảng phân tích qua email."
        soon
      >
        <PillAction disabled>Xuất</PillAction>
      </SettingsRow>

      <SettingsRow
        label="Xóa toàn bộ hội thoại"
        description="Không thể hoàn tác."
        soon
      >
        <PillAction tone="danger" disabled>
          Xóa tất cả
        </PillAction>
      </SettingsRow>
    </SettingsSection>
  )
}

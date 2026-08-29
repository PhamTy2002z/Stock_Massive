"use client"

import { useAuth } from "@/hooks/use-auth"
import { Avatar } from "@/components/shell/primitives"

import {
  ReadOnlyField,
  SelectStub,
  SettingsRow,
  SettingsSection,
  TextFieldStub,
} from "./settings-primitives"

/**
 * Who is signed in, and who the product will one day be told they are.
 *
 * Two different things sit in this pane and the difference is marked. The name
 * and the avatar are read from the session — real values, read-only, because
 * there is no profile write endpoint. The three rows below them are the
 * reference's own personalisation fields, and each would have to reach the turn
 * loop's prompt to mean anything; none does yet.
 */
export function ProfileSection() {
  const { user, isPending } = useAuth()

  const email = user?.email ?? ""
  const displayName = user?.full_name?.trim() || (email ? email.split("@")[0] : "")
  const initial = (displayName || "?").charAt(0).toUpperCase()

  return (
    <SettingsSection
      title="Hồ sơ"
      description="Thông tin giúp hệ thống hiểu bạn hơn trong mọi hội thoại."
      footer="Chỉnh sửa hồ sơ chưa được build — tên và ảnh đại diện lấy từ phiên đăng nhập."
    >
      <SettingsRow label="Ảnh đại diện" description="Sinh từ chữ đầu của tên hiển thị.">
        <Avatar initial={initial} className="size-[42px] text-[1rem]" />
      </SettingsRow>

      <SettingsRow label="Họ và tên" description="Tên dùng trong thanh tài khoản.">
        <ReadOnlyField value={isPending ? "Đang tải…" : displayName || "Chưa đăng nhập"} />
      </SettingsRow>

      <SettingsRow
        label="Hệ thống nên gọi bạn là gì?"
        description="Tên gọi dùng trong câu trả lời, khi khác với tên trên hồ sơ."
        soon
      >
        <TextFieldStub label="Tên gọi" placeholder={displayName || "Tên gọi"} />
      </SettingsRow>

      <SettingsRow
        label="Bạn đầu tư theo phong cách nào?"
        description="Dùng để chọn mức chi tiết và khung thời gian khi phân tích."
        soon
      >
        <SelectStub label="Phong cách đầu tư" value="Chọn" />
      </SettingsRow>

      <SettingsRow
        label="Hướng dẫn riêng"
        description="Hệ thống sẽ ghi nhớ trong mọi hội thoại và bảng phân tích."
        soon
        className="md:flex-col md:items-stretch"
      >
        <TextFieldStub
          label="Hướng dẫn riêng"
          rows={4}
          placeholder="vd. ưu tiên phân tích ngắn gọn, tập trung vào thanh khoản và dòng tiền"
        />
      </SettingsRow>
    </SettingsSection>
  )
}

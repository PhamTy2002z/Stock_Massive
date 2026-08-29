"use client"

import * as React from "react"
import { Check, Copy } from "lucide-react"
import { toast } from "sonner"

import { useAuth } from "@/hooks/use-auth"

import { PillAction, SettingsRow, SettingsSection, Toggle } from "./settings-primitives"

/**
 * Login, and the two things a reader can actually do about it.
 *
 * The email is the session's own, and copying it is the one action on this pane
 * that works — everything else needs an endpoint that does not exist. Changing
 * an email, rotating a password, enrolling a second factor and revoking other
 * sessions are four separate writes against `src/auth/*`, none of them built,
 * and each is marked rather than hidden: a reader who came here to check
 * whether two-factor is on deserves the answer "not yet", not an empty pane.
 *
 * Signing *this* session out is not offered here. It already lives one click
 * away in the account menu, and a second copy inside a settings dialog is a
 * second place to keep correct for no gain.
 */
function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = React.useState(false)

  // The timer is cleared on unmount so a copy immediately before closing the
  // dialog does not set state on a gone component.
  React.useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
    } catch {
      // Clipboard access is refused outside a secure context, and a button that
      // silently does nothing is worse than one that says so.
      toast.error("Trình duyệt không cho phép sao chép")
    }
  }

  return (
    <PillAction onClick={handleCopy}>
      <span className="flex items-center gap-1.5">
        {copied ? (
          <Check className="size-[14px] text-positive" strokeWidth={1.9} />
        ) : (
          <Copy className="size-[14px]" strokeWidth={1.7} />
        )}
        {copied ? "Đã chép" : `Chép ${label}`}
      </span>
    </PillAction>
  )
}

export function SecuritySection() {
  const { user, isPending } = useAuth()
  const email = user?.email ?? ""

  return (
    <SettingsSection
      title="Bảo mật"
      description="Đăng nhập, xác thực và các phiên đang hoạt động."
      footer="Đăng xuất phiên hiện tại nằm ở thanh tài khoản, góc dưới bên trái."
    >
      <SettingsRow
        label="Email đăng nhập"
        description={isPending ? "Đang tải…" : email || "Chưa đăng nhập"}
      >
        {email ? <CopyButton value={email} label="email" /> : null}
      </SettingsRow>

      <SettingsRow label="Đổi email" description="Cần xác nhận qua địa chỉ mới." soon>
        <PillAction disabled>Đổi</PillAction>
      </SettingsRow>

      <SettingsRow label="Mật khẩu" description="Đặt lại mật khẩu đăng nhập." soon>
        <PillAction disabled>Đổi mật khẩu</PillAction>
      </SettingsRow>

      <SettingsRow
        label="Xác thực hai bước"
        description="Yêu cầu thêm mã từ ứng dụng xác thực khi đăng nhập trên thiết bị mới."
        soon
      >
        <Toggle label="Xác thực hai bước" checked={false} disabled />
      </SettingsRow>

      <SettingsRow
        label="Phiên đang hoạt động"
        description="Xem và thu hồi các thiết bị đang đăng nhập vào tài khoản này."
        soon
      >
        <PillAction tone="danger" disabled>
          Đăng xuất tất cả
        </PillAction>
      </SettingsRow>
    </SettingsSection>
  )
}

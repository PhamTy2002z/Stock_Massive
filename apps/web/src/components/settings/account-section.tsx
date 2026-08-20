"use client"

import * as React from "react"
import { Check, Copy } from "lucide-react"
import { toast } from "sonner"

import { useAuth } from "@/hooks/use-auth"
import {
  ReadOnlyField,
  SettingsPanel,
  SettingsRow,
  SettingsSection,
} from "./settings-primitives"

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = React.useState(false)

  // The timer is cleared on unmount so a copy immediately before navigating
  // away does not set state on a gone component.
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
    <button
      type="button"
      onClick={handleCopy}
      aria-label={`Sao chép ${label}`}
      className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-meta transition-[background-color,transform] duration-150 hover:bg-accent active:scale-95"
    >
      {copied ? <Check className="size-[15px] text-positive" /> : <Copy className="size-[15px]" />}
      {copied ? "Đã chép" : "Chép"}
    </button>
  )
}

export function AccountSection() {
  const { user, isPending } = useAuth()

  const email = user?.email ?? ""
  const displayName = user?.full_name || (email ? email.split("@")[0] : "")

  return (
    <SettingsSection
      title="Tài khoản"
      description="Thông tin của phiên đăng nhập hiện tại."
    >
      <SettingsPanel
        footer={
          <p className="text-micro text-ink-6">
            Chỉnh sửa hồ sơ chưa được build — các giá trị dưới đây chỉ để xem.
          </p>
        }
      >
        <SettingsRow label="Tên hiển thị" description="Tên dùng trong thanh tài khoản.">
          <ReadOnlyField value={isPending ? "Đang tải…" : displayName || "Chưa đăng nhập"} />
        </SettingsRow>
        <SettingsRow label="Email" description="Định danh đăng nhập, không đổi được ở đây.">
          <div className="flex w-full items-center gap-2 md:w-auto">
            <ReadOnlyField value={isPending ? "Đang tải…" : email || "Chưa đăng nhập"} />
            {email ? <CopyButton value={email} label="email" /> : null}
          </div>
        </SettingsRow>
      </SettingsPanel>
    </SettingsSection>
  )
}

"use client"

import { AccountSection } from "./account-section"
import { AppearanceSection } from "./appearance-section"
import { SettingsNav, type SettingsNavGroup } from "./settings-nav"
import { SystemSection } from "./system-section"

const NAV_GROUPS: SettingsNavGroup[] = [
  { heading: "Cấu hình", items: [{ id: "appearance", label: "Giao diện" }] },
  {
    heading: "Tài khoản",
    items: [
      { id: "account", label: "Hồ sơ" },
      { id: "system", label: "Hệ thống" },
    ],
  },
]

/**
 * Two columns: a rail that stays put and a single stack of sections that
 * scrolls past it. The rail collapses above the content below md — a 224px
 * column and a readable content measure do not both fit on a phone.
 */
export function SettingsView() {
  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-8 md:flex-row md:gap-12">
      <SettingsNav groups={NAV_GROUPS} />
      <div className="min-w-0 flex-1 space-y-12 pb-16">
        <AppearanceSection />
        <AccountSection />
        <SystemSection />
      </div>
    </div>
  )
}

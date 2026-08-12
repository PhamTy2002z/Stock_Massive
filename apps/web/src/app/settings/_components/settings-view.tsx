"use client"

import * as React from "react"

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
 * Two columns filling the content box edge to edge: a rail flush against the
 * app sidebar, and a column that scrolls beside it with the content held to a
 * reading measure and centred in whatever width is left.
 *
 * The rail is deliberately not a card floating inside padding — it belongs to
 * the chrome, and the hairline between the two columns is the only thing
 * separating them.
 */
export function SettingsView() {
  const scrollRef = React.useRef<HTMLDivElement>(null)

  return (
    <div className="flex h-full min-h-0">
      <SettingsNav groups={NAV_GROUPS} scrollRef={scrollRef} />

      <div ref={scrollRef} className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[760px] px-6 py-10 md:px-10 md:py-14">
          <header className="mb-10">
            <h2 className="text-[28px] font-semibold leading-[1.14] tracking-[-0.5px]">
              Cài đặt hệ thống
            </h2>
            <p className="mt-2 text-[15px] leading-[1.47] tracking-[-0.24px] text-muted-foreground">
              Giao diện, tài khoản và các quy ước dữ liệu đang áp dụng.
            </p>
          </header>

          <div className="space-y-14 pb-16">
            <AppearanceSection />
            <AccountSection />
            <SystemSection />
          </div>
        </div>
      </div>
    </div>
  )
}

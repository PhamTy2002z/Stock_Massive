"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"

import { VisgniteWordmark } from "@/components/shared/visgnite-logo"

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
 * Settings, as its own surface rather than a page inside the app chrome.
 *
 * The shell is a single workspace with a conversation in it; hanging a settings
 * screen off its main column would mean a sidebar full of Threads beside a form
 * about time zones. So this replaces the shell for as long as it is open, and
 * the one way back is the link at the top left — which is why that link is the
 * first thing in the tab order.
 *
 * The page itself never scrolls: the rail and the content column each own their
 * overflow, the same way every region of the shell does.
 */
export function SettingsView() {
  const scrollRef = React.useRef<HTMLDivElement>(null)

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-hidden bg-background text-foreground">
      <header className="flex flex-none items-center gap-3 border-b border-border px-5 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="size-4" strokeWidth={1.7} />
          Quay lại
        </Link>
        <span className="ml-auto">
          <VisgniteWordmark />
        </span>
      </header>

      <div className="flex min-h-0 flex-1">
        <SettingsNav groups={NAV_GROUPS} scrollRef={scrollRef} />

        <div ref={scrollRef} className="scrollbar-thin min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[760px] px-6 py-10 md:px-10 md:py-14">
            <header className="mb-10">
              <h2 className="text-[28px] font-semibold leading-[1.14] tracking-[-0.5px]">
                Cài đặt hệ thống
              </h2>
              <p className="mt-2 text-[0.95rem] leading-[1.47] tracking-[-0.24px] text-ink-4">
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
    </div>
  )
}

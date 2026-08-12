"use client"

import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"

interface DashboardLayoutClientProps {
  children: React.ReactNode
  /** See DashboardLayout — hands the page an unpadded, non-scrolling content box. */
  bleed?: boolean
}

export function DashboardLayoutClient({ children, bleed }: DashboardLayoutClientProps) {
  const router = useRouter()

  const handleStockSelect = (symbol: string) => {
    router.push(`/analytics/deep-dive?symbol=${encodeURIComponent(symbol)}`)
  }

  return (
    <DashboardLayout onStockSelect={handleStockSelect} bleed={bleed}>
      {children}
    </DashboardLayout>
  )
}

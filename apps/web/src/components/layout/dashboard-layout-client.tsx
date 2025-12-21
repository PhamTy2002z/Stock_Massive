"use client"

import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"

interface DashboardLayoutClientProps {
  children: React.ReactNode
}

export function DashboardLayoutClient({ children }: DashboardLayoutClientProps) {
  const router = useRouter()

  const handleStockSelect = (symbol: string) => {
    router.push(`/analytics/deep-dive?symbol=${encodeURIComponent(symbol)}`)
  }

  return <DashboardLayout onStockSelect={handleStockSelect}>{children}</DashboardLayout>
}

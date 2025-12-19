"use client"

import { useSearchParams, useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"

interface DashboardLayoutClientProps {
  children: React.ReactNode
}

export function DashboardLayoutClient({ children }: DashboardLayoutClientProps) {
  const searchParams = useSearchParams()
  const router = useRouter()

  const handleStockSelect = (symbol: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("symbol", symbol)
    router.push(`/?${params.toString()}`, { scroll: false })
  }

  return <DashboardLayout onStockSelect={handleStockSelect}>{children}</DashboardLayout>
}

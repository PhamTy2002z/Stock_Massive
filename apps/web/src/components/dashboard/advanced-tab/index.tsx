"use client"

import { lazy, Suspense, useState } from "react"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, BarChart3, Building2 } from "lucide-react"

const OrderFlowSubtab = lazy(() => import("./order-flow-subtab"))
const TechnicalSubtab = lazy(() => import("./technical-subtab"))
const SectorSubtab = lazy(() => import("./sector-subtab"))

type AdvancedSubTabValue = "order-flow" | "technical" | "sector"

interface AdvancedTabProps {
  symbol: string
}

const subTabs = [
  {
    value: "order-flow" as const,
    label: "Order Flow",
    icon: TrendingUp,
    description: "Phân tích lệnh mua/bán",
  },
  {
    value: "technical" as const,
    label: "Technical",
    icon: BarChart3,
    description: "Chỉ số kỹ thuật",
  },
  {
    value: "sector" as const,
    label: "Sector",
    icon: Building2,
    description: "So sánh với công ty cùng ngành",
  },
]

function SubtabSkeleton() {
  return (
    <div className="space-y-6 py-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-8 w-24" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
      <Skeleton className="h-64" />
    </div>
  )
}

export function AdvancedTab({ symbol }: AdvancedTabProps) {
  const [activeSubTab, setActiveSubTab] = useState<AdvancedSubTabValue>("order-flow")

  return (
    <div className="space-y-4">
      {/* Sub-tab Navigation */}
      <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-sunken border border-border">
        {subTabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeSubTab === tab.value

          return (
            <button
              key={tab.value}
              onClick={() => setActiveSubTab(tab.value)}
              title={tab.description}
              className={cn(
                "relative flex items-center justify-center gap-2 px-4 py-2 rounded-md",
                "text-sm font-medium transition-all duration-200 ease-out",
                "flex-1 min-w-0",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isActive && [
                  "bg-background text-foreground",
                  "shadow-sm",
                  "border border-border",
                ],
                !isActive && [
                  "text-muted-foreground",
                  "hover:text-foreground hover:bg-background/50",
                  "active:scale-[0.98]",
                ]
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors duration-200",
                  isActive ? "text-primary" : "text-muted-foreground"
                )}
              />
              <span className="truncate hidden sm:inline">{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Sub-tab Content */}
      <div className="rounded-lg border border-border bg-card p-4">
        {activeSubTab === "order-flow" && (
          <Suspense fallback={<SubtabSkeleton />}>
            <OrderFlowSubtab symbol={symbol} />
          </Suspense>
        )}
        {activeSubTab === "technical" && (
          <Suspense fallback={<SubtabSkeleton />}>
            <TechnicalSubtab symbol={symbol} />
          </Suspense>
        )}
        {activeSubTab === "sector" && (
          <Suspense fallback={<SubtabSkeleton />}>
            <SectorSubtab symbol={symbol} />
          </Suspense>
        )}
      </div>
    </div>
  )
}

export function AdvancedTabSkeleton() {
  return (
    <div className="space-y-4">
      {/* Sub-tab Navigation Skeleton */}
      <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-sunken border border-border">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="flex-1 h-9 rounded-md" />
        ))}
      </div>
      {/* Content Skeleton */}
      <div className="rounded-lg border border-border bg-card p-4">
        <SubtabSkeleton />
      </div>
    </div>
  )
}

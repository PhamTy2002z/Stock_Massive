"use client"

import { lazy, Suspense, useState } from "react"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, BarChart3, Coins, Building2, ChevronRight, Sparkles } from "lucide-react"

const OrderFlowSubtab = lazy(() => import("./advanced-tab/order-flow-subtab"))
const TechnicalSubtab = lazy(() => import("./advanced-tab/technical-subtab"))
const MoneyFlowSubtab = lazy(() => import("./advanced-tab/money-flow-subtab"))
const SectorSubtab = lazy(() => import("./advanced-tab/sector-subtab"))

type AdvancedSubTabValue = "order-flow" | "technical" | "money-flow" | "sector"

interface AdvancedSectionProps {
  symbol: string
  className?: string
}

const subTabs = [
  {
    value: "order-flow" as const,
    label: "Order Flow",
    icon: TrendingUp,
    description: "Phân tích dòng lệnh mua/bán realtime",
    color: "text-emerald-500",
    bgColor: "bg-emerald-500/10",
  },
  {
    value: "technical" as const,
    label: "Technical",
    icon: BarChart3,
    description: "Chỉ số kỹ thuật & thống kê giao dịch",
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
  },
  {
    value: "money-flow" as const,
    label: "Money Flow",
    icon: Coins,
    description: "Dòng tiền NĐTNN & Tự doanh",
    color: "text-white",
    bgColor: "bg-white/10",
  },
  {
    value: "sector" as const,
    label: "Sector",
    icon: Building2,
    description: "So sánh với công ty cùng ngành",
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
  },
]

function SubtabSkeleton() {
  return (
    <div className="space-y-6 py-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-8 w-24" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-52 rounded-xl" />
        <Skeleton className="h-52 rounded-xl" />
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  )
}

export function AdvancedSection({ symbol, className }: AdvancedSectionProps) {
  const [activeSubTab, setActiveSubTab] = useState<AdvancedSubTabValue>("order-flow")

  return (
    <section className={cn("space-y-5", className)}>
      {/* Section Header */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/20">
          <Sparkles className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-foreground tracking-tight">
            Phân Tích Nâng Cao
          </h2>
          <p className="text-sm text-muted-foreground">
            Order flow, chỉ số kỹ thuật & dòng tiền
          </p>
        </div>
      </div>

      {/* Sub-tab Navigation - Card Style */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {subTabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeSubTab === tab.value

          return (
            <button
              key={tab.value}
              onClick={() => setActiveSubTab(tab.value)}
              className={cn(
                "group relative flex flex-col items-start gap-2 p-4 rounded-xl",
                "text-left transition-all duration-200 ease-out",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isActive && [
                  "bg-card border-2 border-primary/30",
                  "shadow-lg shadow-primary/5",
                ],
                !isActive && [
                  "bg-muted/30 border border-border/50",
                  "hover:bg-muted/50 hover:border-border",
                  "active:scale-[0.98]",
                ]
              )}
            >
              {/* Icon */}
              <div
                className={cn(
                  "flex items-center justify-center w-9 h-9 rounded-lg transition-colors",
                  isActive ? tab.bgColor : "bg-muted",
                )}
              >
                <Icon
                  className={cn(
                    "h-4.5 w-4.5 transition-colors",
                    isActive ? tab.color : "text-muted-foreground"
                  )}
                />
              </div>

              {/* Label */}
              <div className="space-y-0.5">
                <span
                  className={cn(
                    "font-medium text-sm transition-colors",
                    isActive ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {tab.label}
                </span>
                <p className="text-xs text-muted-foreground line-clamp-1 hidden sm:block">
                  {tab.description}
                </p>
              </div>

              {/* Active indicator */}
              {isActive && (
                <ChevronRight className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-primary opacity-60" />
              )}
            </button>
          )
        })}
      </div>

      {/* Content Area */}
      <div className="rounded-xl border border-border/60 bg-card/80 backdrop-blur-sm p-5 shadow-sm">
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
        {activeSubTab === "money-flow" && (
          <Suspense fallback={<SubtabSkeleton />}>
            <MoneyFlowSubtab symbol={symbol} />
          </Suspense>
        )}
        {activeSubTab === "sector" && (
          <Suspense fallback={<SubtabSkeleton />}>
            <SectorSubtab symbol={symbol} />
          </Suspense>
        )}
      </div>
    </section>
  )
}

export function AdvancedSectionSkeleton() {
  return (
    <section className="space-y-5">
      {/* Header Skeleton */}
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-xl" />
        <div className="space-y-1.5">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-56" />
        </div>
      </div>

      {/* Tabs Skeleton */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>

      {/* Content Skeleton */}
      <div className="rounded-xl border border-border/60 bg-card/50 p-5">
        <SubtabSkeleton />
      </div>
    </section>
  )
}

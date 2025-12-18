"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { BarChart3, Wallet, Users } from "lucide-react"

export type StockDetailTabValue = "overview" | "finance" | "shareholders"

interface StockDetailTabsProps {
  value?: StockDetailTabValue
  onChange?: (value: StockDetailTabValue) => void
  className?: string
}

const tabs = [
  {
    value: "overview" as const,
    label: "Tổng Quan",
    icon: BarChart3,
  },
  {
    value: "finance" as const,
    label: "Tài Chính",
    icon: Wallet,
  },
  {
    value: "shareholders" as const,
    label: "Cổ Đông",
    icon: Users,
  },
]

export function StockDetailTabs({
  value = "overview",
  onChange,
  className,
}: StockDetailTabsProps) {
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>(value)

  const handleTabClick = (tabValue: StockDetailTabValue) => {
    setActiveTab(tabValue)
    onChange?.(tabValue)
  }

  return (
    <div className={cn("w-full", className)}>
      {/* Tab Navigation - Fintech Styled */}
      <div className="flex items-center gap-2 p-1 rounded-xl bg-muted/50 border border-border/50">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.value

          return (
            <button
              key={tab.value}
              onClick={() => handleTabClick(tab.value)}
              className={cn(
                // Base styles
                "relative flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg",
                "text-sm font-medium transition-all duration-200 ease-out",
                "flex-1 min-w-0",
                // Focus ring
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                // Active state - elevated with shadow and primary accent
                isActive && [
                  "bg-background text-foreground",
                  "shadow-sm",
                  "border border-border/80",
                ],
                // Inactive state - subtle and clickable
                !isActive && [
                  "text-muted-foreground",
                  "hover:text-foreground hover:bg-background/50",
                  "active:scale-[0.98]",
                ]
              )}
            >
              {/* Active indicator - subtle blue glow */}
              {isActive && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
              )}

              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors duration-200",
                  isActive ? "text-primary" : "text-muted-foreground"
                )}
              />
              <span className="truncate">{tab.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// Skeleton for loading state
export function StockDetailTabsSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-2 p-1 rounded-xl bg-muted/50 border border-border/50">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex-1 h-10 rounded-lg bg-muted animate-pulse"
          />
        ))}
      </div>
    </div>
  )
}

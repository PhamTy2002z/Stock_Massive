"use client"

import { cn } from "@/lib/utils"

export type StockDetailTabValue =
  | "overview"
  | "orderflow"
  | "finance"
  | "shareholders"
  | "volume"

interface StockDetailTabsProps {
  value?: StockDetailTabValue
  onChange?: (value: StockDetailTabValue) => void
  className?: string
}

const tabs: { value: StockDetailTabValue; label: string }[] = [
  { value: "overview", label: "Tổng quan" },
  { value: "orderflow", label: "Dòng lệnh" },
  { value: "finance", label: "Tài chính" },
  { value: "shareholders", label: "Cổ đông" },
  { value: "volume", label: "Khối lượng" },
]

/**
 * Underline tabs, per the design system: the section rail sits on the same
 * hairline that separates the toolbar from the content, so switching views
 * moves a 2px marker rather than repainting a pill row.
 *
 * Controlled by `value` — the parent owns which tab is open, so a symbol change
 * or a deep link cannot leave the marker pointing at the wrong panel.
 */
export function StockDetailTabs({
  value = "overview",
  onChange,
  className,
}: StockDetailTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Nội dung chi tiết cổ phiếu"
      /* No rule of its own: the tab row sits on the hairline its container
         already draws, so the active marker lands on that same line. */
      className={cn("flex items-center gap-[22px] overflow-x-auto", className)}
    >
      {tabs.map((tab) => {
        const isActive = value === tab.value

        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange?.(tab.value)}
            className={cn(
              "-mb-px shrink-0 whitespace-nowrap border-b-2 pb-2 text-[13px] leading-[1.29] tracking-[-0.208px]",
              "transition-colors duration-150",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              isActive
                ? "border-interactive font-semibold text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

// Skeleton for loading state
export function StockDetailTabsSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-[22px]", className)}>
      {[64, 60, 56, 48, 72].map((width) => (
        <div
          key={width}
          style={{ width }}
          className="mb-2 h-4 animate-pulse rounded bg-muted"
        />
      ))}
    </div>
  )
}

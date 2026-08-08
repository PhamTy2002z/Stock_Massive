"use client"

import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Badge } from "@/components/ui/badge"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"
import { formatRatio, getSectorHeaderColor } from "./shared"
import { SpikeStockTable } from "./spike-stock-table"
import { useSortedPagedRows } from "./use-sorted-paged-rows"

// Industry Spike Group Component
export function IndustrySpikeGroup({
  group,
  isOpen,
  onToggle,
}: {
  group: IndustryVolumeSpikeGroup
  isOpen: boolean
  onToggle: () => void
}) {
  const table = useSortedPagedRows(group.stocks)
  const headerColorClass = getSectorHeaderColor(group.avg_spike_ratio)

  return (
    <Collapsible open={isOpen} onOpenChange={onToggle}>
      <CollapsibleTrigger className="w-full">
        <div className={cn(
          "flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors",
          headerColorClass
        )}>
          <div className="flex items-center gap-3">
            <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
            <span className="font-medium">{group.icb_name}</span>
            <Badge variant="secondary" className="text-xs">
              {group.spike_count} CP
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>TB: {formatRatio(group.avg_spike_ratio)}</span>
          </div>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <SpikeStockTable table={table} className="mt-2" />
      </CollapsibleContent>
    </Collapsible>
  )
}

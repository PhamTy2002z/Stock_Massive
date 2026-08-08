"use client"

import { ChevronsUpDown } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"

// Sort type for sector groups
export type SectorSortType = "spike_count" | "avg_spike_ratio" | "name"

// Sector Group Header Component with controls
export function SectorGroupHeader({
  sectorCount,
  sectorSort,
  onSortChange,
  selectedSector,
  onSectorFilterChange,
  allSectors,
  expandAll,
  onExpandAllToggle,
}: {
  sectorCount: number
  sectorSort: SectorSortType
  onSortChange: (value: SectorSortType) => void
  selectedSector: string
  onSectorFilterChange: (sector: string) => void
  allSectors: { code: string; name: string }[]
  expandAll: boolean
  onExpandAllToggle: () => void
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">Theo ngành ICB</h2>
        <Badge variant="secondary" className="text-xs">
          {sectorCount} ngành
        </Badge>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Sort Selector */}
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Sắp xếp:</Label>
          <Select value={sectorSort} onValueChange={(v) => onSortChange(v as SectorSortType)}>
            <SelectTrigger className="w-[120px] h-8 text-xs bg-background">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="spike_count">Số CP</SelectItem>
              <SelectItem value="avg_spike_ratio">Tỷ lệ TB</SelectItem>
              <SelectItem value="name">Tên A-Z</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Sector Filter */}
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Ngành:</Label>
          <Select value={selectedSector} onValueChange={onSectorFilterChange}>
            <SelectTrigger className="w-[140px] h-8 text-xs bg-background">
              <SelectValue placeholder="Tất cả" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              {allSectors.map((s) => (
                <SelectItem key={s.code} value={s.code}>
                  {s.name.length > 18 ? s.name.slice(0, 16) + "..." : s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Expand All Toggle */}
        <Button
          variant="outline"
          size="sm"
          onClick={onExpandAllToggle}
          className="h-8 text-xs gap-1"
        >
          <ChevronsUpDown className="h-3 w-3" />
          {expandAll ? "Thu gọn" : "Mở rộng"}
        </Button>
      </div>
    </div>
  )
}

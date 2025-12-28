import { cn } from "@/lib/utils"
import type { HealthScoreDimension } from "@/lib/api"

interface ScoreBreakdownProps {
  dimensions: Record<string, HealthScoreDimension>
}

const DIMENSION_CONFIG: Record<string, { label: string }> = {
  profitability: { label: "Sinh lời" },
  liquidity: { label: "Thanh khoản" },
  leverage: { label: "Đòn bẩy" },
  efficiency: { label: "Hiệu quả" },
  valuation: { label: "Định giá" },
}

function getScoreColor(score: number): string {
  if (score >= 70) return "text-green-500"
  if (score >= 50) return "text-yellow-500"
  return "text-red-500"
}

function getProgressColor(score: number): string {
  if (score >= 70) return "bg-white"
  if (score >= 50) return "bg-yellow-500"
  return "bg-red-500"
}

export function ScoreBreakdown({ dimensions }: ScoreBreakdownProps) {
  return (
    <div className="space-y-3">
      {Object.entries(dimensions).map(([key, dim]) => (
        <div key={key} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {DIMENSION_CONFIG[key]?.label || key}
            </span>
            <span className={cn("font-medium", getScoreColor(dim.score))}>
              {dim.score}
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", getProgressColor(dim.score))}
              style={{ width: `${dim.score}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

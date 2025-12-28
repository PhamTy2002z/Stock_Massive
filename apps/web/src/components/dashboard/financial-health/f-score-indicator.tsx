import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle } from "lucide-react"
import type { FScoreDetails } from "@/lib/api"

interface FScoreIndicatorProps {
  score: number
  details: FScoreDetails
}

const FSCORE_LABELS: Record<keyof FScoreDetails, string> = {
  positive_roa: "ROA duong",
  positive_cfo: "Dong tien duong",
  roa_improving: "ROA tang",
  accrual_quality: "Chat luong loi nhuan",
  leverage_decreasing: "Don bay giam",
  liquidity_improving: "Thanh khoan tang",
}

function getFScoreLabel(score: number): { text: string; color: string } {
  if (score >= 7) return { text: "Manh", color: "text-[hsl(var(--accent-orange))]" }
  if (score >= 4) return { text: "Trung binh", color: "text-yellow-500" }
  return { text: "Yeu", color: "text-red-500" }
}

export function FScoreIndicator({ score, details }: FScoreIndicatorProps) {
  const { text, color } = getFScoreLabel(score)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Piotroski F-Score</span>
        <span className={cn("font-bold", color)}>
          {score}/9 ({text})
        </span>
      </div>

      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            score >= 7 ? "bg-[hsl(var(--accent-orange))]" : score >= 4 ? "bg-yellow-500" : "bg-red-500"
          )}
          style={{ width: `${(score / 9) * 100}%` }}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        {Object.entries(details).map(([key, passed]) => (
          <div
            key={key}
            className={cn(
              "flex items-center gap-1",
              passed ? "text-green-500" : "text-muted-foreground"
            )}
          >
            {passed ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <XCircle className="h-3 w-3" />
            )}
            <span>{FSCORE_LABELS[key as keyof FScoreDetails]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

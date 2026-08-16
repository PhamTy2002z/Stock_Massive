import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle } from "lucide-react"
import type { FScoreDetails } from "@/lib/api"

interface FScoreIndicatorProps {
  score: number
  details: FScoreDetails
}

const FSCORE_LABELS: Record<keyof FScoreDetails, string> = {
  positive_roa: "ROA dương",
  positive_cfo: "Dòng tiền dương",
  roa_improving: "ROA tăng",
  accrual_quality: "Chất lượng lợi nhuận",
  leverage_decreasing: "Đòn bẩy giảm",
  liquidity_improving: "Thanh khoản tăng",
}

function getFScoreLabel(score: number): { text: string; color: string } {
  if (score >= 7) return { text: "Mạnh", color: "text-positive" }
  if (score >= 4) return { text: "Trung bình", color: "text-caution" }
  return { text: "Yếu", color: "text-negative" }
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
            score >= 7 ? "bg-positive" : score >= 4 ? "bg-caution" : "bg-negative"
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
              passed ? "text-positive" : "text-muted-foreground"
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

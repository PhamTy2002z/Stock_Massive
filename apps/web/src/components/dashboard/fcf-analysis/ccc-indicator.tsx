import { cn } from "@/lib/utils"

interface CCCIndicatorProps {
  ccc: number | null
  dso: number | null
  dio: number | null
  dpo: number | null
}

export function CCCIndicator({ ccc, dso, dio, dpo }: CCCIndicatorProps) {
  if (ccc === null) {
    return (
      <div className="text-center text-muted-foreground text-sm py-4">
        CCC không áp dụng (ngân hàng/tài chính)
      </div>
    )
  }

  const getCCCColor = (days: number) => {
    if (days <= 30) return "text-foreground"
    if (days <= 60) return "text-caution"
    return "text-negative"
  }

  return (
    <div className="space-y-3">
      <div className="text-center">
        <div className="text-sm text-muted-foreground">Cash Conversion Cycle</div>
        <div className={cn("text-2xl font-bold", getCCCColor(ccc))}>
          {ccc.toFixed(0)} ngày
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground">DSO</div>
          <div className="font-medium">{dso?.toFixed(0) || "-"} ngày</div>
        </div>
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground">DIO</div>
          <div className="font-medium">{dio?.toFixed(0) || "-"} ngày</div>
        </div>
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground">DPO</div>
          <div className="font-medium">{dpo?.toFixed(0) || "-"} ngày</div>
        </div>
      </div>
    </div>
  )
}

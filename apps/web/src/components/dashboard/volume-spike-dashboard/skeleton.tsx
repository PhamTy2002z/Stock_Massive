import { cn } from "@/lib/utils"
import { VolumeSpikeChartSkeleton } from "../volume-spike-chart"

// Skeleton
export function VolumeSpikeDashboardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex justify-between">
        <div>
          <div className="h-8 w-48 bg-muted animate-pulse rounded" />
          <div className="h-4 w-32 bg-muted animate-pulse rounded mt-2" />
        </div>
        <div className="h-9 w-9 bg-muted animate-pulse rounded" />
      </div>
      <div className="flex gap-4">
        <div className="h-9 w-32 bg-muted animate-pulse rounded" />
        <div className="h-9 w-32 bg-muted animate-pulse rounded" />
        <div className="h-5 w-20 bg-muted animate-pulse rounded" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
      <div className="space-y-2">
        <div className="h-10 w-64 bg-muted animate-pulse rounded" />
        <VolumeSpikeChartSkeleton />
      </div>
      <div className="space-y-3">
        <div className="h-6 w-32 bg-muted animate-pulse rounded" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
    </div>
  )
}

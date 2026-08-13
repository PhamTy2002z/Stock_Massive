import { cn } from "@/lib/utils"

// Skeleton
export function VolumeSpikeDashboardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex justify-between">
        <div>
          <div className="h-8 w-48 bg-muted animate-pulse rounded" />
          <div className="h-4 w-64 bg-muted animate-pulse rounded mt-2" />
        </div>
        <div className="h-9 w-9 bg-muted animate-pulse rounded" />
      </div>
      <div className="h-9 w-72 bg-muted animate-pulse rounded" />
      <div className="flex gap-4">
        <div className="h-9 w-32 bg-muted animate-pulse rounded" />
        <div className="h-9 w-32 bg-muted animate-pulse rounded" />
      </div>
      {/* The coverage band has a place in the skeleton too: it is part of every
          answer, so a layout that only makes room for it sometimes would shift
          the table under the reader once the data lands. */}
      <div className="h-20 bg-muted animate-pulse rounded-lg" />
      <div className="space-y-2">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
    </div>
  )
}

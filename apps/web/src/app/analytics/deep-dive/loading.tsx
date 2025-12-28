import { Skeleton } from "@/components/ui/skeleton"
import { ChartSkeleton } from "@/components/ui/skeletons"

export default function Loading() {
  return (
    <div className="p-6 space-y-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartSkeleton height={320} />
        <ChartSkeleton height={320} />
      </div>
    </div>
  )
}

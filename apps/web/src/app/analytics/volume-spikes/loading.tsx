import { Skeleton } from "@/components/ui/skeleton"
import { CardSkeleton, ChartSkeleton } from "@/components/ui/skeletons"

export default function Loading() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-32" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {Array(3)
          .fill(0)
          .map((_, i) => (
            <CardSkeleton key={i} />
          ))}
      </div>
      <ChartSkeleton height={384} />
    </div>
  )
}

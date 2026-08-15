import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

/**
 * The rail before its first answer.
 *
 * Three rows rather than ten: guessing the user's real count would make the
 * list jump when the answer lands, and the count beside the cap is the one
 * number this screen must not appear to know before it does.
 */
export function WatchlistRailSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-5 w-12" />
      </div>
      <Skeleton className="h-9 w-full" />
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((row) => (
          <Skeleton key={row} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    </div>
  )
}

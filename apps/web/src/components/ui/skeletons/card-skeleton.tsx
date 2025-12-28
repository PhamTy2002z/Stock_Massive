import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface CardSkeletonProps {
  className?: string
  hasHeader?: boolean
}

export function CardSkeleton({ className, hasHeader = true }: CardSkeletonProps) {
  return (
    <Card className={cn("w-full", className)}>
      {hasHeader && (
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
      )}
      <CardContent>
        <Skeleton className="h-24" />
      </CardContent>
    </Card>
  )
}

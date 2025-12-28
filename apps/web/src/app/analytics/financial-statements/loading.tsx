import { Skeleton } from "@/components/ui/skeleton"
import { TableSkeleton } from "@/components/ui/skeletons"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export default function Loading() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64 mt-2" />
        </div>
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <TableSkeleton rows={10} columns={5} />
        </CardContent>
      </Card>
    </div>
  )
}

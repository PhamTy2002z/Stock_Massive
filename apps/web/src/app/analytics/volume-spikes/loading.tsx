import { Skeleton } from "@/components/ui/skeleton"

// Mirrors the shape the page settles into: scope switch, filters, the coverage
// band, then the table. A fallback laid out differently moves the content under
// the reader at the moment the data lands.
export default function Loading() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-9 w-9" />
      </div>
      <Skeleton className="h-9 w-72" />
      <div className="flex gap-4">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-9 w-32" />
      </div>
      <Skeleton className="h-20 w-full" />
      <div className="space-y-2">
        {Array(6)
          .fill(0)
          .map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
      </div>
    </div>
  )
}

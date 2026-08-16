"use client"

import { useState } from "react"
import { ChevronDown, Loader2 } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { useRunningJobs } from "@/hooks/use-jobs-status"
import { cn } from "@/lib/utils"

export function JobProgressBar() {
  const runningJobs = useRunningJobs()
  const [isOpen, setIsOpen] = useState(false)

  if (runningJobs.length === 0) return null

  const primaryJob = runningJobs[0]
  const hasMultiple = runningJobs.length > 1

  return (
    <div className="border-b bg-surface-sunken px-4 py-2">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="flex items-center gap-3">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium truncate">
                {hasMultiple
                  ? `Đang chạy ${runningJobs.length} jobs...`
                  : primaryJob.displayName}
              </span>
              <span className="text-xs text-muted-foreground ml-2">
                {primaryJob.progress}%
              </span>
            </div>
            <Progress value={primaryJob.progress} className="h-1.5" />
          </div>

          {hasMultiple && (
            <CollapsibleTrigger className="p-1 hover:bg-muted rounded">
              <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
            </CollapsibleTrigger>
          )}
        </div>

        {hasMultiple && (
          <CollapsibleContent className="mt-2 space-y-2 pl-7">
            {runningJobs.map((job) => (
              <div key={job.jobId} className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground w-32 truncate">
                  {job.displayName}
                </span>
                <Progress value={job.progress} className="h-1 flex-1" />
                <span className="text-xs text-muted-foreground w-12 text-right">
                  {job.processedItems}/{job.totalItems}
                </span>
              </div>
            ))}
          </CollapsibleContent>
        )}
      </Collapsible>
    </div>
  )
}

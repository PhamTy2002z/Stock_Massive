"use client"

import { Bell, CheckCircle2, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useCompletedJobsToday, useRunningJobs } from "@/hooks/use-jobs-status"
import { formatDistanceToNow } from "date-fns"
import { vi } from "date-fns/locale"

export function NotificationPanel() {
  const runningJobs = useRunningJobs()
  const completedJobs = useCompletedJobsToday()
  const hasActivity = runningJobs.length > 0 || completedJobs.length > 0

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {hasActivity && (
            <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Lịch sử Jobs hôm nay</DropdownMenuLabel>
        <DropdownMenuSeparator />

        <div className="max-h-80 overflow-y-auto p-2 space-y-2">
          {completedJobs.length === 0 && runningJobs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              Chưa có job nào hôm nay
            </p>
          ) : (
            <>
              {completedJobs.map((job) => (
                <div
                  key={job.jobId}
                  className="flex items-start gap-2 p-2 rounded-md bg-muted/50"
                >
                  {job.status === "completed" ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between">
                      <span className="text-sm font-medium">{job.displayName}</span>
                      <span className="text-xs text-muted-foreground" suppressHydrationWarning>
                        {job.completedAt && formatDistanceToNow(new Date(job.completedAt), {
                          addSuffix: true,
                          locale: vi,
                        })}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {job.status === "completed"
                        ? `${job.processedItems} items`
                        : job.message || "Lỗi không xác định"}
                    </p>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

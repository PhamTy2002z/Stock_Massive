# Phase 2: Frontend Progress UI

**Effort:** 2h | **Dependencies:** Phase 1 complete

## Objective

Implement inline progress bar and notification dropdown using React Query polling.

---

## Task 2.1: Add ShadCN Progress Component (10 min)

**File:** `apps/web/src/components/ui/progress.tsx`

```bash
npx shadcn@latest add progress
```

Or manually create:

```tsx
import * as ProgressPrimitive from "@radix-ui/react-progress"
import { cn } from "@/lib/utils"

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <ProgressPrimitive.Root
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-primary/20", className)}
    >
      <ProgressPrimitive.Indicator
        className="h-full bg-primary transition-all duration-300"
        style={{ width: `${value}%` }}
      />
    </ProgressPrimitive.Root>
  )
}
```

---

## Task 2.2: Add API Types & Fetch Function (15 min)

**File:** `apps/web/src/lib/api.ts`

```typescript
// Job Status Types
export type JobStatusType = "pending" | "running" | "completed" | "failed"

export interface JobStatus {
  jobId: string
  displayName: string
  status: JobStatusType
  progress: number
  totalItems: number
  processedItems: number
  message: string | null
  startedAt: string | null
  completedAt: string | null
  elapsedSeconds: number | null
}

export async function fetchJobsStatus(): Promise<JobStatus[]> {
  const data = await fetchApi<{
    job_id: string
    display_name: string
    status: JobStatusType
    progress: number
    total_items: number
    processed_items: number
    message: string | null
    started_at: string | null
    completed_at: string | null
    elapsed_seconds: number | null
  }[]>("/jobs/status")

  return data.map((item) => ({
    jobId: item.job_id,
    displayName: item.display_name,
    status: item.status,
    progress: item.progress,
    totalItems: item.total_items,
    processedItems: item.processed_items,
    message: item.message,
    startedAt: item.started_at,
    completedAt: item.completed_at,
    elapsedSeconds: item.elapsed_seconds,
  }))
}
```

---

## Task 2.3: Create useJobsStatus Hook (20 min)

**File:** `apps/web/src/hooks/use-jobs-status.ts`

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchJobsStatus, JobStatus } from "@/lib/api"

export function useJobsStatus() {
  return useQuery({
    queryKey: ["jobs-status"],
    queryFn: fetchJobsStatus,
    refetchInterval: (query) => {
      // Poll every 10s if any job is running (validated)
      const hasRunning = query.state.data?.some((j) => j.status === "running")
      return hasRunning ? 10000 : 60000 // 10s if running, 60s otherwise
    },
    refetchIntervalInBackground: true,
    staleTime: 4000,
  })
}

// Derived helpers
export function useRunningJobs() {
  const { data } = useJobsStatus()
  return data?.filter((j) => j.status === "running") ?? []
}

export function useCompletedJobsToday() {
  const { data } = useJobsStatus()
  return data?.filter((j) => j.status === "completed" || j.status === "failed") ?? []
}
```

---

## Task 2.4: Create Inline Progress Bar (40 min)

**File:** `apps/web/src/components/layout/job-progress-bar.tsx`

### Behavior

- Visible only when >= 1 job running
- Single job: show name + progress
- Multiple jobs: collapsed summary, expandable

```tsx
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
    <div className="border-b bg-muted/30 px-4 py-2">
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
```

---

## Task 2.5: Create Notification Panel (30 min)

**File:** `apps/web/src/components/layout/notification-panel.tsx`

Replace existing notification dropdown in dashboard-header.tsx:

```tsx
"use client"

import { Bell, CheckCircle2, XCircle, Clock } from "lucide-react"
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
                      <span className="text-xs text-muted-foreground">
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
```

---

## Task 2.6: Integrate into Layout (15 min)

### dashboard-layout.tsx

```tsx
import { JobProgressBar } from "./job-progress-bar"

export function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <DashboardHeader onStockSelect={onStockSelect} />
        <JobProgressBar />  {/* Add here */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
```

### dashboard-header.tsx

Replace existing notification dropdown with `<NotificationPanel />`.

---

## Dependencies to Install

```bash
# In apps/web
pnpm add date-fns
```

---

## Acceptance Criteria

- [ ] Progress bar appears when job running
- [ ] Progress updates every 5s
- [ ] Multiple jobs show expandable list
- [ ] Notification dropdown shows completed jobs
- [ ] Badge indicates activity
- [ ] Responsive on mobile

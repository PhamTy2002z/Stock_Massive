# Research: Job Progress Notification UI - React/Next.js Best Practices

**Date:** 2025-12-24
**Focus:** React Query polling, ShadCN/Tailwind progress UI, slide-in animations, notification dropdowns

---

## 1. React Query Polling Patterns for Job Status

### Best Practice: Conditional Polling with TanStack Query

```tsx
import { useQuery } from '@tanstack/react-query';

function useJobStatus(jobId: string) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobStatus(jobId),
    refetchInterval: (data) => {
      // Stop polling when job completes/fails
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return 2000; // Poll every 2s
    },
    refetchIntervalInBackground: true, // Continue polling when tab inactive
    enabled: !!jobId, // Only poll if jobId exists
  });
}
```

### Key Patterns:
- **Use `setTimeout` over `setInterval`**: Prevents server overload by waiting for response completion
- **Conditional polling**: Stop when job finishes or user navigates away
- **Error handling**: Implement retry logic with exponential backoff
- **Page visibility**: Use `refetchIntervalInBackground` for background polling

---

## 2. Progress Bar UI - ShadCN/Tailwind

### Pattern: Toast with Embedded Progress

```tsx
import { toast } from 'sonner';
import { Progress } from '@/components/ui/progress';

function triggerJobWithProgress(jobId: string) {
  const toastId = toast(
    <div className="space-y-2">
      <p className="font-medium">Processing job...</p>
      <Progress value={0} className="h-2" />
    </div>,
    { duration: Infinity }
  );

  // Update progress via polling
  const interval = setInterval(async () => {
    const status = await fetchJobStatus(jobId);

    toast(
      <div className="space-y-2">
        <p className="font-medium">{status.message}</p>
        <Progress value={status.progress} className="h-2" />
      </div>,
      { id: toastId }
    );

    if (status.completed) {
      clearInterval(interval);
      toast.success('Job completed!', { id: toastId });
    }
  }, 2000);
}
```

### ShadCN Progress Component
```tsx
// components/ui/progress.tsx
import * as ProgressPrimitive from '@radix-ui/react-progress';

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <ProgressPrimitive.Root className={cn("relative h-4 w-full overflow-hidden rounded-full bg-secondary", className)}>
      <ProgressPrimitive.Indicator
        className="h-full w-full flex-1 bg-primary transition-all duration-300"
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}
```

---

## 3. Inline Status Bar - Slide-In Animation

### Pattern: Fixed Bottom Notification Bar

```tsx
'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Progress } from '@/components/ui/progress';

export function JobStatusBar({ jobs }: { jobs: Job[] }) {
  const activeJob = jobs.find(j => j.status === 'running');

  return (
    <AnimatePresence>
      {activeJob && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="fixed bottom-4 right-4 w-96 rounded-lg border bg-card p-4 shadow-lg"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">{activeJob.name}</span>
            <span className="text-xs text-muted-foreground">{activeJob.progress}%</span>
          </div>
          <Progress value={activeJob.progress} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

### Tailwind Animation Alternative (No Framer Motion)

```tsx
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      keyframes: {
        'slide-up': {
          '0%': { transform: 'translateY(100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        'slide-up': 'slide-up 0.3s ease-out',
      },
    },
  },
};

// Component
<div className={cn(
  "fixed bottom-4 right-4 w-96 rounded-lg border bg-card p-4 shadow-lg",
  activeJob ? "animate-slide-up" : "hidden"
)}>
```

---

## 4. Notification Dropdown UI Patterns

### Pattern: Bell Icon with Dropdown Menu

```tsx
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Bell } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export function NotificationDropdown({ notifications }: { notifications: Notification[] }) {
  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="relative">
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 text-xs">
            {unreadCount}
          </Badge>
        )}
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-80">
        <div className="max-h-96 overflow-y-auto">
          {notifications.map((notif) => (
            <DropdownMenuItem key={notif.id} className="flex-col items-start p-3">
              <div className="flex w-full justify-between">
                <span className="font-medium">{notif.title}</span>
                <span className="text-xs text-muted-foreground">{notif.time}</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">{notif.message}</p>
              {notif.progress !== undefined && (
                <Progress value={notif.progress} className="mt-2 h-1" />
              )}
            </DropdownMenuItem>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

---

## 5. Recommended Libraries

| Library | Purpose | Why |
|---------|---------|-----|
| **Sonner** | Toast notifications | Modern, lightweight, ShadCN-friendly, promise support |
| **TanStack Query** | Polling/data fetching | Built-in polling, conditional refetch, background sync |
| **Radix UI** | Headless primitives | Accessibility, customization (foundation for ShadCN) |
| **Framer Motion** | Animations | Smooth slide-in/out, exit animations |

---

## 6. Complete Implementation Pattern

```tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Progress } from '@/components/ui/progress';
import { useEffect } from 'react';

export function useJobProgressNotification(jobId: string) {
  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobStatus(jobId),
    refetchInterval: (data) => data?.status === 'running' ? 2000 : false,
  });

  useEffect(() => {
    if (!job) return;

    if (job.status === 'running') {
      toast(
        <div className="space-y-2">
          <p className="text-sm font-medium">{job.name}</p>
          <Progress value={job.progress} className="h-1.5" />
          <p className="text-xs text-muted-foreground">{job.progress}% complete</p>
        </div>,
        { id: jobId, duration: Infinity }
      );
    } else if (job.status === 'completed') {
      toast.success(`${job.name} completed!`, { id: jobId });
    } else if (job.status === 'failed') {
      toast.error(`${job.name} failed: ${job.error}`, { id: jobId });
    }
  }, [job, jobId]);

  return job;
}
```

---

## Unresolved Questions
- SSE vs WebSocket choice criteria for real-time updates?
- Optimal polling interval based on job duration?
- Notification persistence strategy (localStorage vs server)?

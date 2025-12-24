# Brainstorm Report: Job Progress Notification System

**Date:** 2024-12-24
**Status:** Finalized
**Approach:** In-Memory Job Status Store + Polling

---

## 1. Problem Statement

User needs to know when background data collection jobs are running and their progress percentage. Currently:
- Jobs run fire-and-forget with no visibility to frontend
- "Notifications" button shows "No new notifications" only
- Dashboard may display stale data while jobs are processing
- No way for user to know if data is current or being updated

---

## 2. Requirements

### Functional
- Track progress of ALL 4 background jobs:
  - `collect_daily_ohlcv_job` (17:00 ICT) - ~1700 symbols, 15-30 min
  - `collect_intraday_data_job` (15:30 ICT) - few symbols, fast
  - `cleanup_old_data_job` (16:00 ICT) - fast, idempotent
  - `collect_financial_statements_job` (Sunday 02:00) - ~1700 symbols
- Display progress as percentage (0-100%)
- Show job status: pending/running/completed/failed
- Show completion results (success count, failed count)
- Persist status for current session (in-memory acceptable)

### Non-Functional
- Update interval: 5-10 seconds (polling)
- Minimal backend changes (non-intrusive to existing job logic)
- Use existing tech stack (React Query, ShadCN, etc.)

---

## 3. Evaluated Approaches

### Approach 1: In-Memory Job Status Store + Polling (SELECTED)

```
Backend:
- Create job_status_store.py (singleton dict)
- Add progress callbacks to existing jobs
- New endpoint GET /api/v1/jobs/status

Frontend:
- Create useJobsStatus() hook with 5s polling
- Enhance Notification dropdown with job progress UI
- Badge on Bell icon when jobs running
```

**Pros:**
- Simple, fast to implement (1-2 days)
- No new infrastructure (Redis, WebSocket)
- Uses existing patterns (React Query polling)
- Non-invasive to existing job code

**Cons:**
- State lost on server restart (acceptable for jobs that run 1x/day)
- Polling adds minimal overhead (payload ~1KB)

### Approach 2: Redis-based Job Status

**Pros:** Durable across restarts
**Cons:** More complex, need to modify Redis layer, overkill for use-case

### Approach 3: Server-Sent Events (SSE)

**Pros:** Real-time updates
**Cons:** Browser compatibility, connection management complexity, overkill

---

## 4. Final Solution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)                                                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ src/core/job_status_store.py                                ││
│  │ ─────────────────────────────                               ││
│  │ class JobStatusStore:                                       ││
│  │   _instance: dict[str, JobStatus]                           ││
│  │                                                             ││
│  │   def start_job(job_id, total_items)                        ││
│  │   def update_progress(job_id, processed, message)           ││
│  │   def complete_job(job_id, result)                          ││
│  │   def fail_job(job_id, error)                               ││
│  │   def get_all_statuses() -> list[JobStatus]                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ src/stocks/jobs.py (modified)                               ││
│  │ ─────────────────────────────                               ││
│  │ from src.core.job_status_store import job_store             ││
│  │                                                             ││
│  │ def collect_daily_ohlcv_job():                              ││
│  │     job_store.start_job("daily-ohlcv", total=len(symbols))  ││
│  │     for i, symbol in enumerate(symbols):                    ││
│  │         # ... existing logic ...                            ││
│  │         job_store.update_progress("daily-ohlcv", i+1)       ││
│  │     job_store.complete_job("daily-ohlcv", result)           ││
│  └─────────────────────────────────────────────────────────────┘│
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ src/stocks/jobs_router.py (new)                             ││
│  │ ─────────────────────────────                               ││
│  │ @router.get("/jobs/status")                                 ││
│  │ def get_jobs_status() -> list[JobStatusResponse]:           ││
│  │     return job_store.get_all_statuses()                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTP GET (polling 5s)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND (Next.js)                                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ src/hooks/use-jobs-status.ts (new)                          ││
│  │ ───────────────────────────────                             ││
│  │ export function useJobsStatus() {                           ││
│  │   return useQuery({                                         ││
│  │     queryKey: ["jobs-status"],                              ││
│  │     queryFn: fetchJobsStatus,                               ││
│  │     refetchInterval: 5000, // 5 seconds                     ││
│  │   })                                                        ││
│  │ }                                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ src/components/layout/notification-panel.tsx (new)          ││
│  │ ─────────────────────────────────────────────               ││
│  │ - Badge on Bell icon (number of running jobs)               ││
│  │ - Dropdown panel with:                                      ││
│  │   - Running jobs section (progress bar + %)                 ││
│  │   - Completed today section                                 ││
│  │   - Failed jobs section (if any)                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Data Models

### Backend: JobStatus

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Any

JobStatusType = Literal["pending", "running", "completed", "failed"]

@dataclass
class JobStatus:
    job_id: str                    # e.g. "daily-ohlcv"
    display_name: str              # e.g. "Daily OHLCV Collection"
    status: JobStatusType
    progress: int                  # 0-100
    total_items: int | None        # e.g. 1700 symbols
    processed_items: int           # e.g. 850 symbols done
    message: str | None            # e.g. "Processing VNM..."
    started_at: datetime | None
    completed_at: datetime | None
    result: dict[str, Any] | None  # Final result on completion
    error: str | None              # Error message if failed
```

### Frontend: JobStatusResponse

```typescript
interface JobStatusResponse {
  jobId: string
  displayName: string
  status: "pending" | "running" | "completed" | "failed"
  progress: number           // 0-100
  totalItems: number | null
  processedItems: number
  message: string | null
  startedAt: string | null   // ISO datetime
  completedAt: string | null
  elapsedSeconds: number | null
}
```

---

## 6. UI Design (Hybrid Pattern - SELECTED)

### Pattern Decision: Inline Status Bar + Notification Dropdown

**Why Hybrid:**
- **Inline Bar**: High visibility for running jobs - user sees immediately without clicking
- **Dropdown**: History of completed/failed jobs - detail on demand
- **Semantic correctness**: "Đang cập nhật dữ liệu" ≠ "notification"
- **Best practice**: Similar to GitHub Actions, Vercel deployment status

### Overall Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HEADER: [Sidebar] [Search...] [Share] [🔔] [Avatar]                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 🔄 Đang cập nhật dữ liệu phiên 24/12...  65%  [██████████░░░░░░░░░░░░░] │ │  ← INLINE BAR
│ └─────────────────────────────────────────────────────────────────────────┘ │    (auto-hide when no running jobs)
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                             │
│ DASHBOARD CONTENT                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component 1: Inline Progress Bar (Running Jobs)

**Location:** Below header, above dashboard content
**Visibility:** Only shown when >= 1 job is running
**Animation:** Slide down/up with 200ms ease-out

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔄 Đang cập nhật dữ liệu phiên 24/12...  65%  [██████████░░░░░░░░░░░░░░░░░] │
│     ↓ Click to expand                                                       │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 📊 Daily OHLCV: 1,105/1,700 symbols • Đang xử lý VNM...                 │ │
│ │ 📈 Financial Statements: 850/1,700 symbols                             │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**States:**
| Running Jobs | Display |
|--------------|---------|
| 0 | Hidden (height: 0, no DOM) |
| 1 | Single line with job name + progress |
| 2+ | Collapsed: summary + expand button; Expanded: all jobs |

### Component 2: Notification Dropdown (Job History)

**Location:** Header, same Bell button position
**Content:** Completed/Failed jobs from TODAY only
**Purpose:** History lookup, not primary status indicator

```
Click [🔔] →
┌────────────────────────────────────────┐
│ 📋 Lịch sử Jobs hôm nay                │
├────────────────────────────────────────┤
│                                        │
│ ✅ HOÀN THÀNH (2)                       │
│ ┌────────────────────────────────────┐ │
│ │ 🧹 Data Cleanup            16:00   │ │
│ │ Đã xóa 234 bản ghi cũ              │ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ 📈 Intraday Collection     15:32   │ │
│ │ 5 symbols, 1,245 bars              │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ❌ THẤT BẠI (0)                         │
│ Không có job lỗi                       │
│                                        │
└────────────────────────────────────────┘
```

**Badge on Bell:**
| Completed Today | Badge Display |
|-----------------|---------------|
| 0 | No badge |
| 1+ | Green dot (not number) |

### Progress Bar Colors

| Status | Color | Usage |
|--------|-------|-------|
| Running | `bg-primary` (blue) | Inline bar, animated |
| Completed | `bg-green-500` | Dropdown items |
| Failed | `bg-destructive` (red) | Dropdown items + inline if any failed |

### Responsive Behavior

| Viewport | Inline Bar | Dropdown |
|----------|------------|----------|
| Desktop (>768px) | Full width, show job details | Standard width (320px) |
| Mobile (<768px) | Full width, compact mode | Full width sheet |

---

## 7. Implementation Considerations

### Backend Changes

1. **job_status_store.py** (new)
   - Thread-safe singleton (use `threading.Lock`)
   - Auto-expire completed jobs after 24h
   - Methods: `start_job`, `update_progress`, `complete_job`, `fail_job`, `get_all`

2. **jobs.py** (modify)
   - Add progress tracking to 4 existing jobs
   - Non-intrusive: wrap existing logic with try/finally
   - Track: symbols processed, elapsed time, success/fail counts

3. **jobs_router.py** (new)
   - Single endpoint: `GET /api/v1/jobs/status`
   - Return list of JobStatus for today only

4. **main.py** (modify)
   - Mount new router

### Frontend Changes

1. **use-jobs-status.ts** (new)
   - React Query hook with 5s polling
   - Auto-pause when no running jobs

2. **lib/api.ts** (modify)
   - Add `fetchJobsStatus` function

3. **notification-panel.tsx** (new, or extract from header)
   - Self-contained component for notifications dropdown
   - Progress bar using shadcn Progress component

4. **dashboard-header.tsx** (modify)
   - Replace inline notification dropdown with `<NotificationPanel />`
   - Pass jobs status to control badge

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Server restart loses job state | Accept for now; jobs run 1x/day, users can check logs. Can migrate to Redis later if needed. |
| Polling overhead | Payload is <1KB, 5s interval is minimal. Can increase to 10s if needed. |
| Progress calculation inaccurate | Use item count (symbols) as progress basis, not time. |
| Thread safety issues | Use `threading.Lock` for in-memory store. |

---

## 9. Success Metrics

1. **Functional**
   - User can see running jobs with % progress
   - Badge updates in real-time (5s delay max)
   - Completed/failed jobs visible until end of day

2. **Performance**
   - Polling request < 100ms
   - No impact on job execution time
   - Memory usage < 10KB for status store

---

## 10. Next Steps

1. **Implementation Plan**: Create detailed plan with file-by-file changes
2. **Backend First**: Implement job_status_store and API endpoint
3. **Frontend Second**: Implement hook and notification panel
4. **Testing**: Manual testing with running jobs
5. **Polish**: UI animations, edge cases

---

## 11. Unresolved Questions

None - all requirements clarified through brainstorming session.

---

**Decision:** Proceed with Implementation Plan using Approach 1 (In-Memory + Polling).

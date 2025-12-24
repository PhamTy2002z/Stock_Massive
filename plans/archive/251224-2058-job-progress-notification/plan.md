---
title: "Job Progress Notification System"
description: "In-memory job status tracking with inline progress bar and notification dropdown"
status: pending
priority: P2
effort: 4h
branch: main
tags: [jobs, notifications, polling, progress-bar, ui]
created: 2025-12-24
---

# Job Progress Notification System

## Overview

Hiển thị tiến trình các background jobs cho user. Giải quyết vấn đề "fire-and-forget" - user không biết jobs đang chạy hay dữ liệu đang cập nhật.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Backend (FastAPI)                                                │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │ job_status_store.py  │ <- │ jobs.py (4 jobs)     │           │
│  │ (thread-safe dict)   │    │ + progress callbacks │           │
│  └──────────────────────┘    └──────────────────────┘           │
│             │                                                    │
│  ┌──────────────────────┐                                       │
│  │ GET /api/v1/jobs/    │ <- Polling endpoint                   │
│  │     status           │                                       │
│  └──────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
                │ HTTP GET (5s polling)
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js)                                               │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │ useJobsStatus()      │ -> │ InlineProgressBar   │           │
│  │ (React Query 5s)     │    │ NotificationDropdown │           │
│  └──────────────────────┘    └──────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Jobs Tracked (4)

| Job ID | Schedule | Duration | Items |
|--------|----------|----------|-------|
| `daily-ohlcv` | 17:00 ICT | 15-30 min | ~1700 symbols |
| `intraday` | 15:30 ICT | < 5 min | 5 symbols |
| `cleanup` | 16:00 ICT | < 1 min | N/A |
| `financial-statements` | Sun 02:00 | 30-60 min | ~1700 symbols |

## Phases

| Phase | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| [Phase 1](./phase-01-backend-job-status-store.md) | Backend: Job status store + API | 1.5h | None |
| [Phase 2](./phase-02-frontend-progress-ui.md) | Frontend: Progress bar + Notification | 2h | Phase 1 |
| [Phase 3](./phase-03-integration-testing.md) | Integration testing + Polish | 0.5h | Phase 2 |

## Key Files

### Backend (New)
- `apps/api/src/core/job_status_store.py` - Thread-safe status store
- `apps/api/src/stocks/jobs_router.py` - Status API endpoint

### Backend (Modified)
- `apps/api/src/stocks/jobs.py` - Add progress callbacks
- `apps/api/src/main.py` - Mount new router

### Frontend (New)
- `apps/web/src/hooks/use-jobs-status.ts` - Polling hook
- `apps/web/src/components/ui/progress.tsx` - ShadCN Progress
- `apps/web/src/components/layout/job-progress-bar.tsx` - Inline bar
- `apps/web/src/components/layout/notification-panel.tsx` - Dropdown

### Frontend (Modified)
- `apps/web/src/lib/api.ts` - fetchJobsStatus function
- `apps/web/src/components/layout/dashboard-layout.tsx` - Add progress bar
- `apps/web/src/components/layout/dashboard-header.tsx` - Replace notification

## Success Criteria

1. User sees progress bar when any job is running
2. Progress updates every 5 seconds
3. Completed/failed jobs visible in notification dropdown
4. No impact on job execution performance
5. < 100ms API response time

## References

- [Brainstorm Report](../reports/brainstorm-251224-2026-job-progress-notification.md)
- [Backend Research](./research/researcher-01-fastapi-job-tracking.md)
- [Frontend Research](./research/researcher-02-react-progress-ui.md)

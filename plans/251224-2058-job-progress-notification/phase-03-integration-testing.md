# Phase 3: Integration Testing & Polish

**Effort:** 0.5h | **Dependencies:** Phase 1 + Phase 2 complete

## Objective

Verify end-to-end functionality and polish edge cases.

---

## Task 3.1: Backend Integration Test (15 min)

### Manual Testing Checklist

```bash
# 1. Start services
docker-compose up -d

# 2. Check API endpoint (should return empty array initially)
curl http://localhost:8000/api/v1/jobs/status
# Expected: []

# 3. Trigger a job manually
curl -X POST http://localhost:8000/api/v1/stocks/analytics/financial-statements/collect

# 4. Immediately poll status (should show running)
curl http://localhost:8000/api/v1/jobs/status
# Expected: [{"job_id": "financial-statements", "status": "running", ...}]

# 5. Wait for completion, poll again
curl http://localhost:8000/api/v1/jobs/status
# Expected: [{"job_id": "financial-statements", "status": "completed", ...}]
```

### Edge Cases to Verify

| Scenario | Expected Behavior |
|----------|-------------------|
| API restart during job | Status lost (acceptable) |
| Concurrent job triggers | Both tracked separately |
| Job fails with exception | Status = "failed", error message captured |
| No jobs today | Empty array returned |

---

## Task 3.2: Frontend Integration Test (10 min)

### Browser Testing Checklist

1. Open dashboard at http://localhost:3000
2. Trigger job via backend or wait for scheduled time
3. Verify:
   - [ ] Progress bar slides in when job starts
   - [ ] Percentage updates every 5s
   - [ ] Progress bar hides when job completes
   - [ ] Notification dropdown shows completed job
   - [ ] Badge on bell icon appears

### Mobile Responsiveness

- [ ] Progress bar full-width on mobile
- [ ] Notification dropdown readable
- [ ] No overflow issues

---

## Task 3.3: Polish & Edge Cases (5 min)

### Error Handling

```typescript
// use-jobs-status.ts - add error handling
export function useJobsStatus() {
  return useQuery({
    queryKey: ["jobs-status"],
    queryFn: fetchJobsStatus,
    refetchInterval: 5000,
    retry: 2,
    retryDelay: 1000,
    // Silently fail - don't break UI if endpoint unavailable
    throwOnError: false,
  })
}
```

### Skeleton Loading (Optional)

If needed, add skeleton state for initial load.

---

## Performance Verification

| Metric | Target | How to Verify |
|--------|--------|---------------|
| API response time | < 100ms | Browser DevTools Network tab |
| Polling overhead | < 1KB/request | Check response size |
| Memory usage | < 10KB store | Log store size |
| No memory leaks | Stable over time | Chrome Memory profiler |

---

## Final Checklist

### Backend

- [ ] `job_status_store.py` thread-safe
- [ ] 4 jobs have progress callbacks
- [ ] API endpoint returns correct data
- [ ] Old jobs auto-cleanup (24h)

### Frontend

- [ ] `use-jobs-status.ts` polling works
- [ ] `job-progress-bar.tsx` shows/hides correctly
- [ ] `notification-panel.tsx` displays history
- [ ] Progress component added to ShadCN

### Documentation

- [ ] README updated (if needed)
- [ ] API docs reflect new endpoint

---

## Rollback Plan

If issues arise:

1. Backend: Remove progress callbacks from jobs.py (jobs still work without tracking)
2. Frontend: Replace NotificationPanel with original static dropdown
3. Remove `/api/v1/jobs/status` endpoint

No database changes = easy rollback.

---

## Future Enhancements (Out of Scope)

- Redis-backed store for persistence
- WebSocket/SSE for real-time updates
- Job cancellation capability
- Historical job analytics

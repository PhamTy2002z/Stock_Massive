# Validation Report: Job Progress Notification System

**Date:** 2025-12-24
**Plan:** plans/251224-2058-job-progress-notification/

---

## Validated Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Polling interval | **10s** (running), 60s (idle) | Cân bằng tốt hơn giữa UX và tài nguyên |
| Job history retention | **Vài ngày** | Hiển thị tất cả jobs trong ngày, cleanup sau 24h |
| UI Language | **Tiếng Việt** | Thu thập OHLCV, Đang xử lý VNM... |
| Progress location | **Inline bar** | Dưới header, auto-hide khi không có job |
| Animation | **Pure Tailwind** | Không thêm framer-motion dependency |
| Error notification | **Toast + Badge** | Toast popup khi fail + badge đỏ trên notification |
| date-fns | **Yes** | Cần cho "X phút trước" formatting với locale vi |

---

## Plan Updates Applied

1. **Phase 2 - useJobsStatus hook**:
   - Changed polling from 5s → **10s** (running)
   - Changed idle polling from 30s → **60s**

2. **Vietnamese display names** confirmed:
   - `Thu thập OHLCV` (daily-ohlcv)
   - `Thu thập Intraday` (intraday)
   - `Dọn dẹp dữ liệu cũ` (cleanup)
   - `Thu thập BCTC` (financial-statements)

3. **Error handling**: Add toast.error() when job fails

---

## Final Confirmation

✅ Plan validated và sẵn sàng implement.

**Next:** Run `/implement` hoặc bắt đầu Phase 1 thủ công.

# Connectors cho VisgniteAI — đề xuất (phương án B)

Ngày: 27/09/2026 · Trạng thái: **được product owner chấp nhận** (quyết định ở cuối file).

## Kết luận

User tự gắn **remote MCP** (Streamable HTTP) để tăng năng lực agent, theo mẫu
claude.ai: danh mục đã duyệt (Khám phá) cộng URL tuỳ chỉnh, **chung một
pipeline**. Tool của user không vào `registry._ENTRIES` global; chúng là overlay
`ResolvedTool` ghép vào surface của từng Turn, luôn `UNTRUSTED`.

## Hiện trạng (bằng chứng)

- `registry._ENTRIES` (`agent/registry.py:493`) là dict global cho cả tiến trình;
  đăng ký tool per-user vào đó là rò giữa user, dính `ToolShadowError` và bump
  generation liên tục.
- `ResolvedToolSurface` (`agent/definitions.py:50`) là snapshot bất biến theo task
  — chỗ ghép overlay mà không đụng registry.
- Permission allow/ask/deny, deny mặc định (`agent/permissions.py`); `register()`
  chặn ASK cho tool không ghi (`registry.py:550`); executor có `APPROVAL_REQUIRED`
  (`executor.py:114`) nhưng chưa có bề mặt duyệt.
- `untrusted.py`, `threat_patterns.py`, chặn `remember_fact` sau nội dung ngoài,
  `is_global` (`tools/web.py:505`) dùng lại được.
- MCP registry cũ (`agent/mcp/`) bị gỡ ở `1e7b936`: cấu hình theo env, global,
  connect lúc boot — không hợp per-user. Không khôi phục.
- `phase-10-conditional-capabilities.md` từng ghi "no generic marketplace" — quyết
  định 1 dưới đây thay thế nó.

## Contract

- **Outcome:** Cài đặt › Kết nối (Của bạn / Khám phá / Thêm), quyền từng tool
  Cho phép / Cần duyệt / Chặn, bật/tắt ở composer, chế độ nạp tool (khi cần / nạp sẵn).
- **Constraints:** chỉ remote MCP HTTP, không stdio; SSRF cả redirect lẫn DNS; token
  mã hoá at-rest; kết quả luôn `UNTRUSTED`; annotation không cấp quyền; gọi connector
  tính vào ngân sách external call của lane, có timeout và cap kích thước; backup DB
  trước migration; `CreateTurnRequest` `extra="forbid"` → đổi schema và client cùng lúc.
- **Non-goals:** stdio/MCP local; connector đặt lệnh/giao dịch; tự expose MCP server;
  marketplace có thanh toán; quyền theo tổ chức.
- **Acceptance:**
  - a. User A gắn connector, user B không thấy tool nào của A.
  - b. Chặn → không có trong schema; Cần duyệt → Turn dừng chờ; từ chối/hết giờ →
    model nhận `APPROVAL_REQUIRED`.
  - c. URL trỏ `localhost`, `10.x`, `169.254.169.254` bị từ chối, kể cả qua redirect
    hay DNS trả IP nội bộ.
  - d. Sau khi đọc kết quả connector, `remember_fact` bị chặn.
  - e. Server đổi mô tả/thêm tool → "cần xác nhận lại", tool mới không tự được cho phép.
  - f. Server chết giữa Turn → Turn settle bình thường với dữ liệu đã có, bảng hiện lỗi.
  - g. Không có token plaintext trong DB.

## Trade-offs

| | Giả định chịu lực | Hỏng trước khi |
|---|---|---|
| A. Chỉ danh mục | Vài nền tảng phổ biến là đủ | Cần nền tảng chưa duyệt — trượt "tự do" |
| **B. Danh mục + URL tuỳ chỉnh** | Lớp untrusted + SSRF + quyền theo tool giữ được server lạ | Server độc đầu độc mô tả tool → giảm bằng quét `threat_patterns` + xác nhận lại khi fingerprint đổi |
| C. Adapter tự viết | Ít nền tảng, cần kiểm soát sâu | Nền tảng thứ ba: chi phí tuyến tính |

Better approaches: none — hướng MCP remote kiểu claude.ai là hướng được yêu cầu;
điểm lệch duy nhất so với cách "ngây thơ" là overlay per-Turn thay vì registry global.

## Quyết định của product owner (27/09/2026)

1. **URL tuỳ chỉnh** sau flag `CONNECTORS_CUSTOM_URL`; bản đầu chỉ profile
   `personal_internal` + allowlist user. Danh mục đã duyệt mở cho mọi user.
2. **Số liệu từ connector:** `connector_catalog.trusted_data` (operator đặt, mặc định
   false). Chỉ connector `trusted_data=true` mới là bằng chứng đã kiểm chứng; mọi
   connector khác (kể cả mọi connector tuỳ chỉnh) luôn "chưa kiểm chứng", kể cả khi số
   khớp. Tất cả ghi ledger kèm connector, tool, `retrieved_at`.
3. **Duyệt trong Turn** qua SSE `approval.requested`; server và web client đổi cùng
   lúc; client không khai báo hiểu sự kiện → deny ngay, không treo.
4. **Tool ghi** có trong bản đầu nhưng luôn Cần duyệt; UI không cho Cho phép. Danh mục:
   operator phân loại đọc/ghi. Tuỳ chỉnh: annotation chỉ siết — `destructiveHint` hoặc
   thiếu `readOnlyHint=true` → khoá Cần duyệt; `readOnlyHint=true` → user được chọn Cho
   phép, UI ghi rõ đó là khai báo của server, chưa kiểm chứng.

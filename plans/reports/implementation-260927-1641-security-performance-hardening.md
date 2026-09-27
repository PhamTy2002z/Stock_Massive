# Triển khai hardening security, performance, concurrency

**Ngày:** 27/09/2026 · **Nhánh:** `feat/host-owned-numbers` (chưa commit; session `stock-massive-15` sẽ commit gộp)
**Nguồn:** `plans/reports/security-260927-1509-full-codebase-audit.md` · **Plan:** `plans/260927-1516-security-performance-hardening/plan.md`

## Kết quả

Mọi phát hiện trong audit (C1, H1–H7, M1–M21, L1–L20) đã được sửa, trừ ba mục ghi rõ ở phần "Không đổi". Sau đó một lượt review độc lập tìm thêm 10 lỗi trong chính các bản sửa, gồm 2 High, và cả 10 đã được sửa.

| Kiểm chứng | Kết quả |
|---|---|
| Backend `make test` | 2990 passed, 0 failed (baseline trước khi sửa: 2775) |
| Web lint, type-check | sạch |
| Web vitest | 617 passed, 2 skipped |
| Web production build (`.next-verify`) | pass |
| `pnpm audit` / `pip-audit` | không còn lỗ hổng |
| `docker compose config` (dev + prod), `caddy validate` | hợp lệ |
| Migration `f2b8c4d61a37` | đã áp lên DB Docker, backup ở `backups/stockmassive-260927-pre-f2b8c4d61a37.dump`; upgrade → downgrade → upgrade đã thử trên cluster nháp |
| Container api tạo lại | healthy trên `127.0.0.1:8000`; `/capabilities` trả 401 khi chưa đăng nhập; web gửi đủ CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, và không còn `X-Powered-By` |

## Theo phát hiện

| # | Cách sửa |
|---|---|
| C1 | `next` 15.5.26, `sharp` 0.35.4, `js-yaml` 4.3.2, `vitest` 4.1.11; `images.unoptimized` |
| H1 | Prod không còn publish cổng 8000/3000; limiter chỉ tin XFF từ proxy tin cậy (`TRUSTED_PROXY_CIDRS`, prod ghim subnet `172.28.0.0/16`) |
| H2 | Redis trong compose prod; limiter cho endpoint đăng nhập fail-closed, có fallback trong process |
| H3 | Dev bind `127.0.0.1` (db, api, web, `next dev -H 127.0.0.1`) |
| H4 | Ảnh Markdown chỉ còn alt text; favicon chỉ tải cho host có trong kết quả tool của chính Turn đó; thêm CSP `img-src` |
| H5 | Grounding chạy trên thread, có index theo độ lớn: nhanh hơn khoảng 28 lần (5,86s → 0,21s), kết quả giống hệt từng byte (đối chiếu 1963 report với code cũ) |
| H6 | Ghi settle retry 3 lần rồi vẫn phát sự kiện kết thúc; heartbeat 20s, reaper 60s |
| H7 | Pool riêng cho tool chặn luồng (`core/blocking_pool.py`); watchdog deadline tổng cho fetch (22s xuyên suốt chuỗi redirect) và cho favicon; default executor 32 thread |
| M1 | Bỏ fallback `:-0` của các trần LLM trong compose |
| M2 | Từ chối `AUTH_SECRET` yếu ngoài dev; `ENVIRONMENT` mặc định là production; JWT bắt buộc `exp`/`sub`/`type` |
| M3 | Giới hạn mật khẩu 72 byte; nhánh dummy hash không còn raise |
| M4 | Next và server action chuyển tiếp một IP client đã kiểm tra; limiter đăng nhập theo tài khoản, chỉ đếm lần thất bại |
| M5 | Caddy `request_body 6MB`; api trả 411 khi thiếu Content-Length và đọc có trần; proxy Next đếm byte |
| M6 | `DbSession` (`scope="function"`): commit trước khi gửi response |
| M7 | File tải lên bật taint trước round 1 (`TurnPermissionState.for_turn`) |
| M8 | Sau taint, `fetch_url` chỉ nhận URL xuất hiện nguyên văn trong kết quả tìm kiếm, trang đã đọc hoặc lời người dùng; URL tool lặp lại từ tham số không được tính |
| M9 | Tạo Turn khoá advisory rồi đếm lại; POST lặp cùng id bỏ qua bước admission |
| M10 | Sweep và reaper chỉ settle Turn có heartbeat cũ hơn 90s (dùng đồng hồ DB) |
| M11 | Partial index cho Turn active, index cho hai FK message |
| M12 | Redis ra khỏi event loop, timeout 1s, backoff 30s khi khởi tạo lỗi |
| M13 | Single-flight: bên đến sau chờ tối đa 10s |
| M14 | Chỉ redirect stdout ở lần import vnstock đầu tiên, có lock |
| M15, M18–M21 | Probe backoff, Stop/busy gắn với Thread đang mở, dùng lại idempotency key, tách context, health cùng origin |
| M16, M17 | Security header ở Next và Caddy; `safeRedirectPath` so sánh origin |
| L1–L20 | Đã sửa hết (chi tiết ở từng test); L7: trần 1000 Thread mỗi lần liệt kê, id kiểu int giới hạn trong khoảng BIGINT |

## Quyết định cần biết

- **`session_search` chỉ trả lời chính người dùng đã nói.** Grounding miễn kiểm tra số liệu từ tool này (`EXEMPT_TOOLS`), nên nếu trả cả câu trả lời cũ thì số liệu chưa kiểm chứng sẽ lọt qua. `SUMMARY_LABEL`, docstring compaction và prompt đã sửa cho khớp.
- **Sau taint, agent chỉ đi theo URL mà nó đã thấy.** `fetch_url` không giữ `href`, nên một link chỉ có trong `<a href>` sẽ không đi theo được sau taint. Muốn mở rộng thì trích href vào kết quả.
- **Refresh token dùng lại cùng lúc giờ bị coi là reuse** và đăng xuất mọi phiên. Single-flight phía web che được trường hợp này khi chỉ chạy một process Next.

## Không đổi (có lý do)

- **Info về compaction:** chi phí compaction không tính vào trần chi phí theo user. Đổi cách hạch toán ngân sách là quyết định sản phẩm; hiện nó vẫn nằm trong envelope của lane.
- **Rủi ro khi chạy nhiều worker** (cancel giữa các worker): prod chạy 1 worker; chưa làm.
- **`.env` local** vẫn đặt trần LLM là 0 (không giới hạn) và không có `AUTH_SECRET`. Đây là cấu hình máy của người dùng nên không sửa.

## Việc vận hành còn lại

1. Chạy lại `pnpm dev` để `next dev` bind vào `127.0.0.1` và dùng Next 15.5.26 (process hiện tại khởi động từ trước khi đổi).
2. Trước khi tạo lại container db: đặt `POSTGRES_PORT=5433` trong `.env`, nếu không cổng `127.0.0.1:5432` sẽ đụng Postgres Homebrew.
3. Từ giờ dùng `docker compose up -d --no-deps api` thay cho `restart`. Container cũ không có `ENVIRONMENT`, nên với mặc định production nó sẽ từ chối secret dev.
4. Prod: `docker compose down` một lần để áp subnet đã ghim; đặt `AUTH_SECRET` mạnh.
5. Build image api dev từ đầu đang lỗi vì PyPI không còn `vnstock==4.0.5`. Lỗi này có từ trước, không do đợt sửa này.

## Câu hỏi còn mở

- Next 15.5.26 có abort `request.signal` khi client ngắt kết nối SSE không? Chưa xác minh lúc chạy (L18).
- Có nên settle Turn thành incomplete khi probe gặp 404/403 (Turn đã mất) không?

---
phase: 5
title: "Kho đính kèm, quota và trần"
status: done
priority: P1
effort: "7h"
dependencies: [2, 4]
---

# Phase 05: Kho đính kèm, quota và trần

## Overview

Một bảng, một endpoint nạp, một endpoint đọc — kèm **quota, rate limit và ingress
cap**. Bản đầu chỉ có trần per-file và đẩy dọn rác sang "chưa giải quyết"; red-team
gọi đó là một cửa một chiều, đúng.

## Requirements

- Functional: nạp trả về một id; đọc lại đúng bytes cho đúng chủ; quota per-user
  theo số hàng **và** tổng bytes; hàng không gắn Turn có TTL.
- Non-functional: trần tính từ số đo phase 04, có phép tính ghi cạnh hằng số;
  migration có backup trước và parent đọc lúc thi công.

## Architecture

### Vì sao Postgres — lý do thật

Bản đầu viết *"thư mục upload sẽ chết mỗi lần `docker compose restart api`"*.
**Sai**: `restart` giữ writable layer, và compose đã có named volume
(`docker-compose.yml:160-162`) cho đúng việc này. Tiền lệ `agent_artifact.signal_desk_spec`
cũng **sai**: nó là JSONB, và repo không có một cột `bytea`/`LargeBinary` nào.

Lý do thật, ba cái: một cơ chế chủ quyền (`user_id`, cùng đường mọi bảng khác dùng)
· một backup (`pg_dump` đã là quy trình) · nhất quán giao dịch với `agent_message`.
Ghi đúng ba lý do đó vào bình luận. **Không** để lý do sai đi vào code.

### Vì sao endpoint này cần trần riêng

Mọi `POST` hiện có trong `agent/router.py` bị chặn bởi LLM admission
(`router.py:369`) — một cổng endpoint nạp **không** đi qua, vì nó không gọi model.
Và không có rate-limit middleware: `main.py:100-120` chỉ đăng ký CORS;
`heavy_rate_limit`/`standard_rate_limit` (`core/ratelimit.py:172-181`) có đúng một
consumer, `auth/router.py:35`. Nên endpoint này ship với **không trần nào** nếu
không tự đặt.

Thêm nữa Starlette đã spool xong body trước khi handler kịp trả 413, nên "trần
bytes trả 413" là một kiểm hậu kiểm trên bytes đã nhận. Cần một kiểm
`Content-Length` **trước** khi đọc body.

### Trần — phép tính, không cảm giác

Bản đầu viết `100_000 / 4`. Sai hai lần:

- `MAX_TOOL_ROUNDS = 4` nghĩa **`MAX_TOOL_ROUNDS + 1` = 5 call** (`loop.py:23`,
  `:913`).
- `TURN_CONTEXT_PER_CALL × 5 = 160k > TURN_INPUT_TOTAL = 100_000`, nên
  `TURN_INPUT_TOTAL` là ràng buộc **bó trước**, không phải per-call.

Phép tính đúng đi từ `TURN_INPUT_TOTAL`, trừ chỗ cho system prompt + transcript +
tool result, chia cho số lượt gửi lại, rồi chia cho chi phí token/ảnh **đo được ở
phase 04**. Viết cả phép tính ra cạnh hằng số. Một hằng số không có phép tính bên
cạnh là một hằng số sẽ bị nâng lên khi ai đó thấy nó chật.

### Phục vụ lại: hai loại không sniff được

Whitelist gồm `text/csv` và `text/plain`, hai loại **không có magic byte**. Nên
bytes bất kỳ (HTML, script, SVG) vào được dưới `text/plain`, và đọc lại phục vụ
same-origin với session cookie. Repo không có `nosniff`, không có CSP, `next.config.js`
không khai `headers()`. Chủ quyền hiện giới hạn hại ở tự-hại, nhưng phòng thủ theo
lớp thì không có lớp nào.

## Related Code Files

- Create: `apps/api/src/agent/attachments.py`
- Create: `apps/api/alembic/versions/{rev}_agent_attachment.py` — **parent đọc lúc thi công**
- Modify: `apps/api/src/agent/router.py` — `POST /attachments`, `GET /attachments/{id}`
- Modify: `apps/api/src/agent/schemas.py`
- Create: `apps/api/tests/test_agent_attachments.py`

## Implementation Steps

1. **Đọc head thật:** `docker compose exec -T api alembic heads`. Branch này đang
   mang `a3f7e21b8d54` **chưa commit**, và `upgrade()` của nó raise `RuntimeError`
   nếu `provider_snapshots` có row nhưng khác `{market: 36_528, valuation: 35_245}`
   (`:41-46`, `:66-76`). Nghĩa là: hoặc commit và apply nó trước, hoặc biết rằng
   `alembic upgrade head` sẽ chạy nó trước migration của mình. Không hardcode parent
   từ plan.
2. **Backup trước migration**: `pg_dump` vào `backups/`, không commit.
3. Bảng `agent_attachment`: id · `user_id` · `media_type` · `byte_size` · `filename`
   (đã sanitise) · `bytes` · `created_at` · `attached_turn_id` (nullable). Cột cuối
   là cái làm TTL khả thi: hàng `NULL` quá TTL là rác.
4. Luật kiểm ở `attachments.py`, không ở router: whitelist media type (`image/png`,
   `image/jpeg`, `image/webp`, `text/csv`, `text/plain`) · trần bytes/file · **quota
   per-user: số hàng và tổng bytes, kiểm trước insert** · tên file sanitise.
5. Media type từ **nội dung** cho ảnh (magic bytes). Ghi rõ trong bình luận rằng
   hai loại text **không** sniff được, nên chúng được phục vụ lại dưới
   `application/octet-stream` + `X-Content-Type-Options: nosniff` +
   `Content-Disposition: attachment`. Phase 02 đã cho ba header đó sống sót qua proxy.
6. `POST /attachments`: kiểm `Content-Length` **trước** khi đọc body; rate limit
   bằng `heavy_rate_limit` đã có sẵn (`core/ratelimit.py`), không dựng cái mới.
   Trả `{id, media_type, byte_size, filename}`, không trả bytes.
7. `GET /attachments/{id}`: kiểm chủ quyền như `read_artifact` (`router.py:506-540`).
   404 cho cả "của người khác" và "không tồn tại" — 403 tiết lộ id tồn tại. Viết
   bình luận nói đây là chủ ý.
8. **TTL**: một hàm dọn trong `attachments.py` xoá hàng `attached_turn_id IS NULL`
   quá TTL. Gọi nó từ đâu là quyết định lúc làm (lazy lúc nạp, hay một lệnh
   Makefile) — nhưng hàm phải tồn tại và có test ở phase này.
9. Test: nạp → đọc lại đúng bytes · user khác → 404 · khai sai media type ảnh bị
   từ chối theo magic bytes · vượt trần file → 413 trước khi body được đọc hết ·
   vượt quota số hàng → từ chối · vượt quota tổng bytes → từ chối · một `.csv` chứa
   HTML **không** được phục vụ dưới `text/html` · dọn TTL xoá đúng hàng mồ côi và
   **không** xoá hàng đã gắn Turn.

## Success Criteria

- [ ] `alembic heads` một head sau migration; parent là head đọc được lúc thi công
- [ ] Nạp → đọc lại đúng bytes (so hash), qua proxy Next
- [ ] Quota số hàng và tổng bytes đều từ chối được vòng lặp nạp
- [ ] `Content-Length` bị từ chối trước khi body đọc hết
- [ ] `heavy_rate_limit` áp lên endpoint nạp
- [ ] `.csv` chứa HTML phục vụ dưới `octet-stream` + `nosniff` + `Content-Disposition`
- [ ] Hàm dọn TTL tồn tại, có test, không xoá hàng đã gắn Turn
- [ ] Hằng số trần có phép tính ghi cạnh, dẫn từ `TURN_INPUT_TOTAL` và **5** call
- [ ] Bình luận nêu ba lý do thật chọn Postgres; không nhắc `docker compose restart`
- [ ] `make test` pass; `alembic upgrade --sql` chạy được trong container

## Risk Assessment

**Rủi ro: `alembic upgrade head` abort vì `a3f7e21b8d54` raise.** Nó xoá
`provider_snapshots` và chỉ chịu chạy khi row count khớp đúng hai số đã đo.
*Tín hiệu:* `RuntimeError("refusing to delete: …")` khi migrate.
*Phản ứng đã định:* **không** sửa hai con số đó để đi qua. Đọc thông điệp của nó:
restore là `backups/pre-retire-fiinquant-provider-snapshots-260829.sql.gz`. Nếu DB
này không phải DB nó được đo trên, việc cần làm là tách revision đó ra khỏi đường
migrate của mình, không phải chỉnh số.

**Rủi ro: bytes trong Postgres làm dump phình.** `backups/pre-rip-out-260825.sql.gz`
đang 7.2M.
*Tín hiệu:* kích thước `pg_dump` tăng bất thường giữa hai lần backup.
*Phản ứng đã định:* quota per-user + TTL là cái chặn, và cả hai là điều kiện nghiệm
thu của phase này chứ không phải việc sau. Nếu dump vẫn vượt ~50M vì đính kèm,
chuyển sang object storage là một plan riêng — **không** nới quota để tránh phải
chuyển.

**Rủi ro: quota chặn oan người dùng thật.**
*Tín hiệu:* từ chối nạp trong khi người dùng chỉ đang gửi vài ảnh.
*Phản ứng:* quota tính từ phép tính ở bước trên, nên nó phải cho ít nhất số ảnh mà
một Turn được phép mang, nhân một số Turn hợp lý mỗi ngày. Nếu hai con số đó xung
đột thì trần token là cái đúng và quota là cái phải nới — theo thứ tự đó.

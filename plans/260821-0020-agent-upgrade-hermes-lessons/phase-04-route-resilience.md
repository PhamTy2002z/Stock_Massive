---
phase: 4
title: "Độ bền tuyến LLM"
status: complete
priority: P1
effort: "3-4d"
dependencies: [1]
---

# Phase 4: Độ bền tuyến LLM

## Overview

Biến từng mã lỗi Phase 1 phân loại được thành một hành động phục hồi. Mục tiêu:
36% Turn chết vì route giảm xuống mức mà phần còn lại là lỗi thật của tuyến,
không phải lỗi ta không biết cách phục hồi.

Chạy song song với Phase 5 — không chung file.

## Requirements

- Functional: mỗi mã lỗi có một hành động phục hồi, hoặc một lý do ghi rõ vì sao
  terminal.
- Functional: Collector và API không tự làm nhau chết vì rate limit.
- Functional: hai lần trả rỗng liên tiếp cùng signature → đừng retry, đổi hướng.
- Functional: `cache_control` được set thật để prefix ổn định được cache.
- Non-functional: mọi guard fail-OPEN. Không guard nào được phép làm Turn chết
  thêm so với hiện tại.
- Non-functional: `StreamAssembler` giữ nguyên bất biến — không đoán index tool call.

## Architecture

### 4.1 Bảng hành động phục hồi

Từ taxonomy `FailoverReason` của Hermes (`error_classifier.py`), giữ tên miền của ta:

| Lớp lỗi (Phase 1) | Hành động |
|---|---|
| `ContextOverflow` | **nén, không failover** — Hermes ghi rõ *"compress, not failover"* |
| `OutputCapExceeded` | giảm output cap cho lời gọi này, **không** thu `context_length` |
| `RouteRateLimited` (có) | backoff jittered, ghi vào breaker chung |
| `GatewayTimeout` (có) | **rebuild client** rồi retry — Hermes: `timeout` → rebuild client |
| `ModelUnavailable` | đổi sang model còn lại trong cặp batch/session |
| `ContentPolicyBlocked` | terminal, thông báo riêng, không retry |
| `SchemaRejected` | log loud, terminal — retry sẽ lặp y nguyên |
| `AuthUnavailable` (có) | terminal — ta chỉ có một credential, không có pool để rotate |

### 4.2 Breaker rate-limit xuyên tiến trình — trên Redis

Collector (trong `core/scheduler.py`) và API cùng process nhưng eval và worktree
song song thì không. Hermes giải bằng file chia sẻ; **ta không bắt chước** — ta
đã có khuôn tốt hơn.

`core/quota.py:1` mở đầu: *"One Redis arbiter over the whole vnstock account
allowance"*, và lý do tồn tại (`:3`): *"Before this module there were three pacers
and none of them was the quota"* — đúng bài toán này, một tầng khác. Dựng breaker
cho tuyến LLM theo cùng khuôn: khoá Redis, Lua nguyên tử, và **fail-closed khi
Redis chết** giống `quota.py` đã chọn.

Lưu ý ngược chiều: `quota.py` fail-closed là đúng cho hạn mức trả tiền. Với
breaker LLM, fail-closed nghĩa là không gọi được model khi Redis chết — cân nhắc
fail-open ở đây vì hậu quả là Turn trắng. **Cần quyết định**, ghi ở câu hỏi mở.

### 4.3 Guard rỗng xác định

Mẫu `empty_response_guard.py` (NS-503 — *"charged ~$2.33 for an empty answer"*).
Hai guard, cả hai fail-open:

- Hai lần rỗng liên tiếp, **cả hai** có usage và `output_tokens == 0`, cùng
  `(model, route, finish_reason)` → coi là xác định, bỏ retry còn lại, đổi model.
- Thiếu usage, hoặc `output_tokens > 0` (model sinh *gì đó*) → **không** xếp là
  xác định, giữ nguyên budget retry.
- Reasoning token tính là sinh thật — response chỉ có reasoning **không** phải rỗng xác định.

Kèm: định giá không bao giờ được làm chết loop (`except Exception` + log debug).

### 4.4 Deadline của ta vs của provider

Hiện `LLM_REQUEST_TIMEOUT_SECONDS=120` là timeout duy nhất, và `gateway_timeout`
gộp "ta bỏ cuộc" với "provider bỏ cuộc". Tách hai thứ, classify khác nhau.

Hai chi tiết kỹ thuật từ `deadline.py` cần giữ:
- `asyncio.wait_for` hẹn hết hạn trên event loop; khi loop bị chặn trong một lời
  gọi đồng bộ thì **mọi** timeout dựa trên asyncio âm thầm mất tác dụng (#84047).
- Timeout lớn overflow `time_t` trong `Lock.acquire(timeout=)` trên macOS, giết cả
  batch (#83220) → clamp ở biên dùng chung.

### 4.5 Bound việc đọc thân lỗi streaming

Mẫu `bounded_response.py` (port từ `openclaw#95108`). `response.read()` trên
stream không giới hạn theo hai hướng: body khổng lồ, và server mở body rồi treo.
`iter_bytes()` chặn **bên trong** socket read nên kiểm giờ giữa các chunk không
cứu được — phải đọc trên daemon thread và đóng response khi hết hạn.

### 4.6 Gắn `cache_control`

`cache_key()` có nhưng không `cache_control` nào được set. Prefix mà
`contract.py::prefix()` cẩn thận tách ra đang không được cache thật. Nếu tuyến
hỗ trợ, đặt breakpoint theo khuôn `prompt_caching.py`: prefix stable của system,
cuối system prompt, và 2 message non-system cuối.

### 4.7 Jittered backoff

Thay backoff cố định. Lý do (`retry_utils.py`): chống thundering-herd khi nhiều
session cùng đập vào một tuyến đã rate-limit.

## Related Code Files

- Modify: `apps/api/src/core/llm/client.py` — bảng hành động, guard rỗng, backoff
- Modify: `apps/api/src/core/llm/transport.py` — deadline tách, bound error body, rebuild client
- Modify: `apps/api/src/core/llm/errors.py` — dùng lớp lỗi Phase 1
- Create: `apps/api/src/core/llm/breaker.py` — breaker Redis, khuôn `core/quota.py`
- Modify: `apps/api/src/core/llm/config.py` — `cache_control`, tách timeout
- Modify: `apps/api/src/agent/loop.py` — nhánh `ContextOverflow` gọi nén thay vì terminal
- Modify: `apps/api/tests/` — test cho từng nhánh

## Implementation Steps

1. Bảng hành động: một commit cho **mỗi** nhánh, mỗi commit có test. Không gộp —
   `pnpm test:e2e` là cổng streaming, gộp thì không biết cái nào phá.
2. `breaker.py` theo khuôn `quota.py`. Chốt fail-open hay fail-closed trước khi viết.
3. Guard rỗng xác định trong `client.py`.
4. Tách deadline; clamp; classify `DeadlineExpired` riêng.
5. Bound error body trên daemon thread.
6. `cache_control` — chỉ khi capability probe xác nhận tuyến hỗ trợ.
7. Jittered backoff.
8. `make test` + `pnpm test:e2e`.

## Success Criteria

- [x] Mỗi lớp lỗi có nhánh phục hồi hoặc lý do terminal ghi trong code —
      `core/llm/recovery.py`, có test đi hết bảng
- [x] `ContextOverflow` → nén và thử lại, không terminal (trần 2 lần)
- [x] `GatewayTimeout` → rebuild client rồi retry
- [x] Breaker Redis: hai client trên một Redis đọc cùng một câu trả lời (test cả
      hai dialect redis-py và Upstash)
- [x] Guard rỗng: 2 lần rỗng cùng signature → đổi model, không retry lần 3
- [x] Guard rỗng fail-open: thiếu usage → giữ nguyên budget; reasoning token
      tính là sinh thật
- [x] Deadline của ta classify khác timeout của provider — `DeadlineExpired`,
      terminal reason `deadline_expired`
- [x] Đọc thân lỗi streaming có trần byte (8 KiB) và trần thời gian (5s)
- [x] `cache_control` có đường đi và có probe check; **cờ mặc định tắt** cho tới
      khi probe xác nhận trên tuyến thật
- [x] `make test` xanh (2686 passed)
- [ ] `pnpm test:e2e` — **chưa chạy**: `pnpm dev` đang mở, mà e2e chạy
      `pnpm build` cùng thư mục nên sẽ phá `.next` của dev; thêm nữa
      `apps/api/.env` đang thiếu
- [ ] Sau 48h: tỉ lệ Turn chết vì route giảm, và phần còn lại có tên — cần thời
      gian chạy thật

## Quyết định đã chốt khi thực thi

- **Breaker fail-OPEN.** Câu hỏi mở của phase này. Chốt fail-open, lý do ghi
  trong docstring `core/llm/breaker.py`: `core/quota.py` fail-closed là đúng cho
  hạn mức tài khoản trả tiền (vnstock `sys.exit()` khi cạn), còn ở đây tuyến tự
  enforce limit của nó nên breaker chỉ tiết kiệm đúng một request đã bị từ chối,
  và giá của việc sai là màn hình trắng. Có cờ tắt `LLM_ROUTE_BREAKER_ENABLED`.
  Hold bị chặn trên ở 300s để một `Retry-After` sai không khoá lane hàng giờ.
- **Rate limit vẫn không retry.** Bảng của plan ghi "backoff jittered" cho
  `RouteRateLimited`, nhưng `errors.py` đã ghi quyết định đo được: tuyến *đã trả
  lời*. Giữ nguyên không retry; cái mới là ghi vào breaker để caller kế tiếp
  không hỏi lại. Backoff jitter áp cho các nhánh thật sự retry.
- **Failover model nằm ở client, không ở transport.** `transport.py` cấm đổi
  model vì nó không hỏi được admission; client hỏi lại được, nên nó reserve lần
  nữa cho model kia dưới workload mà model đó được định giá — và
  `SpendAdmission.reserve` từ chối nếu cặp không khớp.
- **Nén chỉ khi nén thật sự nhường được gì.** Turn ngắn có prompt chiếm phần lớn
  input: hạ trần của ta không đổi được context đã dựng, nên nhánh này raise ngay
  thay vì mua một lần bị từ chối y hệt.
- **Bound thân lỗi bằng `asyncio.wait_for`, không dùng daemon thread.** Mẫu
  Hermes dùng thread vì transport của họ đồng bộ; ở transport async, đọc socket
  nhường lại event loop nên timer nổ được và response đóng được dưới nó.

## Sửa sau review (`code-reviewer`, cùng phiên)

Bốn lỗi suite không phủ, đã sửa và có test riêng:

- **`rebuild()` đóng client dùng chung** → giết call đang bay của mọi Turn khác,
  và lỗi đó lại classify thành `GatewayTimeout` nên Turn kia cũng rebuild → một
  con 504 cascade khắp process. Nay: client bị thay bị *ngưng dùng* ngay và đóng
  sau `request_timeout + 5s`, rebuild có lock và cooldown 30s.
- **Lua của breaker lưu millisecond phân số** → Redis thật từ chối `PX` phân số,
  nên mọi 429 *gia hạn* một hold đang có đều fail âm thầm (breaker chết sau hold
  đầu tiên). Nay floor cả hai số; `tests/fake_redis.py` từ chối `PX` phân số để
  mirror không còn dễ tính hơn thứ nó mirror.
- **`ConstructedContextTooLarge` lọt ra khỏi nhánh nén** → Turn kết thúc
  `turn_failed`, mất chính cái classification phase này sinh ra. Nay raise lại
  `ContextOverflow` gốc. Kèm: mỗi round có trần thời gian riêng
  (`ROUND_TIMEOUT_MULTIPLE`), vì 5 call ở trần mỗi call là đủ chạm Turn deadline
  — mà đường đó kết Turn không qua nhánh terminal nào đặt tên được.
- **Ghi 429 vào Redis đồng bộ trên event loop** (`get_redis` trả client sync,
  dialect Upstash là một round trip HTTPS, và `ping()` không có connect timeout).
  Nay qua `asyncio.to_thread`.

Kèm các mục nhỏ: `cache_control` giờ **thật sự** tới prefix ổn định (`Transcript`
mang biên, loop truyền `contract.prefix()` — trước đó chỉ probe set segment nên
cờ bật lên là mua rủi ro 400 mà không có cache); `route_key` dùng `hostname` nên
userinfo trong base URL không vào key/log; test bảng recovery đi theo cây class
thay vì theo chính key của bảng; `RouteAttempt.attempts` đếm mọi attempt trả
tiền; probe cache check xét *chấp nhận field*, không xét model có nói gì.

Còn để nguyên có chủ ý: nhánh phục hồi của loop reserve ở lane của caller
(`TURN`) chứ không `EMERGENCY` — nó là một call **khác hình dạng** của cùng
round, không phải retry y nguyên; lane `EMERGENCY` vẫn dành cho retry bên trong
`client.complete`. Reservation `status='reserved'` không được reconcile vẫn tính
worst case vĩnh viễn (hành vi `ADR-0014` có từ trước), nhưng số attempt mỗi Turn
tăng nên rủi ro `BudgetRefusal` giữa round cao hơn — ghi lại để Phase 8 đo.

## Chưa làm (ngoài scope đã ghi ở trên)

- Tách `LLM_REQUEST_TIMEOUT_SECONDS` thành hai biến riêng cho connect/read: hiện
  vẫn một deadline cho mỗi HTTP attempt, nhưng nó đã được **classify** riêng
  khỏi deadline của provider, tức là phần Phase 4 cần cho ops đã có. Thêm biến
  thứ hai là tuning, không phải phục hồi.

## Risk Assessment

**Rủi ro**: nén rồi thử lại có thể vòng vô hạn nếu nén không giảm đủ. **Tín
hiệu**: cùng một Turn nén nhiều lần. **Phản ứng**: trần số lần nén mỗi Turn =
2, sau đó terminal — Hermes có đúng guard này (anti-thrash).

**Rủi ro**: breaker fail-closed làm Turn trắng khi Redis chết. **Tín hiệu**:
Redis down → mọi Turn 503. **Phản ứng**: đây là quyết định phải chốt **trước**
khi viết, không phải sau. Ghi ở câu hỏi mở.

**Rủi ro**: `cache_control` sai chỗ phá cache thay vì tạo cache. **Tín hiệu**:
`cache_read_tokens` không tăng, hoặc giảm. **Phản ứng**: gỡ cờ; đây là thay đổi
một biến.

**Assumption có thể vỡ**: giả định tuyến hiện tại (proxy OpenAI-compatible) hỗ
trợ prompt caching. Nếu không, mục 4.6 vô nghĩa và bỏ khỏi phase.

## Rollback

Mỗi mục là một commit độc lập, revert riêng được. `breaker.py` có cờ tắt.

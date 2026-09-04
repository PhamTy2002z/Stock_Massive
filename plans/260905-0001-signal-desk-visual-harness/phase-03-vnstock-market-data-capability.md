---
phase: 3
title: "Vnstock Market Data Capability"
status: todo
priority: P1
effort: "8h"
dependencies: [1]
---

# Phase 3: Vnstock Market Data Capability

## Context Links

- `plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`
- `apps/api/src/agent/tools/web.py` — pattern của một tool đã ship (declaration, trust, cap)
- `apps/api/src/agent/registry.py::ToolEntry` — `check_fn`, `requires_env`, `is_async`, `content_trust`, `max_result_size_chars`
- `apps/api/src/agent/evidence/pipeline.py::evidence_from_calls`
- `apps/api/src/agent/evidence/ledger.py` — `_PRIMARY_CLASSES`, `_temporal_valid`, `_numbers_supported`
- `apps/api/src/agent/toolsets.py`, `apps/api/src/agent/domain/vn_equity.py`
- `apps/api/src/core/config.py`

## Overview

Một tool read-only `get_market_data`, **một dataset `ohlcv`**, một symbol mỗi
call, bounded rows, backed by Vnstock Community pinned, chỉ bật ở profile
personal internal.

Không phải market terminal: không ingestion, cache, scheduler, indicator.

**Chỉ `ohlcv`.** `trades` không có consumer nào trong Phase 5–7 (visual là
candlestick + volume). `quote` bị intraday ohlcv 15m phủ (vnstock có lịch sử
intraday tới 1 năm, một request, tier free) — cắt nó xoá luôn bài toán hai thang
giá (ohlcv nghìn VND vs quote VND đầy đủ), case "quote không có timestamp", hai
normalizer và một nửa test matrix. Thêm `quote` khi một câu hỏi thật cần độ mới
dưới 15 phút; thêm `trades` khi có claim về order flow.

## Ledger Findings (đọc code, không suy đoán)

Ba fact quyết định hình dạng evidence. Sai một cái là mọi số market thành
`UNSUPPORTED` và chart không bao giờ render:

| Fact trong code | Hệ quả bắt buộc |
|---|---|
| `SourceClass.STORE` **không** nằm trong `_PRIMARY_CLASSES` (`ledger.py:30`) | Material claim chỉ có market evidence → verdict `SINGLE_SOURCE`, không bao giờ `VERIFIED`. **Chốt: không sửa `_PRIMARY_CLASSES`** — xem "Vì sao SINGLE_SOURCE là đúng" bên dưới. Phase 5 visual gate nhận `SINGLE_SOURCE` trở lên. |
| `_temporal_valid`: `published_at is None` + material → `False` | Mỗi market evidence phải set `published_at` = thời điểm đóng của bar (ICT). Không set = mọi claim material thành `TEMPORALLY_INVALID`. |
| `_numbers_supported` yêu cầu số xuất hiện trong `evidence.excerpt` và khớp unit | `excerpt` là **các dòng bar đã render thành text** với đúng thang số claim dùng, không phải JSON dump. |

`EvidenceKind.STORE_FIGURE` và `SourceClass.STORE` đã có trong enum, chưa ai
dùng — phase này là consumer đầu tiên, không cần sửa `contracts.py`.

### Vì sao `SINGLE_SOURCE` là đúng, không phải hạn chế

Số đến từ `kbbuddywts.kbsec.com.vn` (KB Securities) và `trading.vietcap.com.vn`
(Vietcap) — feed công ty chứng khoán, **không phải HOSE/HNX**. Research report:
"Vnstock là technical connector, không bán/trao quyền source data" và "Không
được trả lời 'nguồn chính thức' chỉ vì Vnstock đã normalize row". Gọi nó
`EXCHANGE`/primary là dán nhãn sai đường đi dữ liệu — đúng thứ
`_PRIMARY_CLASSES` tồn tại để chặn.

`SINGLE_SOURCE` không chặn sản phẩm: `report.valid` chỉ phụ thuộc
duplicate/invalid evidence/errors, và `render_claim_ledger` hiện nó là "Một
nguồn" **trong phần kết luận** (chỉ `UNSUPPORTED` bị đẩy xuống "Chưa kiểm
chứng").

**Đường lên `VERIFIED` đã có, không cần amend:** `_accepted_verdict` cho
`VERIFIED` khi có ≥ 2 publisher độc lập. KBS và VCI là hai publisher, và probe
đã thấy rows khớp nhau. Nếu Phase 7 đo được "Một nguồn" làm chất lượng answer
yếu thì bật cross-check hai provider cho số material — vẫn không chạm truth
contract.

**Bẫy khi làm cross-check:** đừng phó cho publisher-count. `_numbers_supported`
chỉ cần MATCHED ở *một* evidence và `_accepted_verdict` chỉ đếm publisher, nên
hai provider lệch số mà một cái khớp thì vẫn ra `VERIFIED`. So sánh phải xảy ra
ở tầng tool: lệch quá tolerance → `quality=conflict` + gap, emit **một**
evidence, không emit hai.

## Toolset Wiring

Đăng ký bundle trong `TOOLSETS` nhưng **không** thêm vào
`domain/vn_equity.py::PACK.toolsets`. `_check_the_selection_matches_the_pack`
buộc `CHAT_TOOLSETS == CORE_TOOLSETS + pack.toolsets`, nên thêm vào pack =
chat cũng nhận được tool. Phase 4 chọn bundle này riêng cho signal_desk.

Không sửa `registry.py`: `ToolEntry` đã có `check_fn` (availability probe có
cache, exception = unavailable), `requires_env`, `is_async=False` cho handler
blocking, `content_trust`, `max_result_size_chars`, `permission_rules`.

## Requirements

- Arguments đúng `symbol` (HOSE/HNX/UPCOM đã normalize), `start`, `end`,
  `interval` trong allowlist đã chứng minh bằng contract test. Không có
  provider, URL, method hay method-name nào model chọn được.
- Từ chối: ngày đảo, range vượt cap, interval ngoài allowlist, symbol không
  hợp lệ, output provider ngoài bounds đã hỏi.
- Envelope trả về: source, package version, provider, requested/actual bounds,
  retrieved_at, timezone, currency, unit/scale, adjustment, row count, quality
  state, `content_sha256` của **raw payload** provider.
- Một hash, không hai: `build_evidence_ref` tự dẫn `excerpt_sha256`; normalized
  rows suy ra deterministic từ raw nên hash thứ hai là con số không ai so.
- Giữ tên field raw để hash/audit; chỉ expose field normalized đã allowlist ra
  model và visual.
- Security: credential backend-only — không vào schema, model context, result,
  trace, browser, log.
- Availability: `True` chỉ khi profile là `personal_internal` **và** flag bật
  **và** import/version check pass. Production/staging fail-closed dù có key.
- Budget: network/read/idempotent, đếm external call, timeout hữu hạn, cap
  rows và serialized chars, không `get_all`/pagination loop.

## Tool Contract

```json
{
  "name": "get_market_data",
  "arguments": {
    "symbol": "FPT",
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD",
    "interval": "1D | 15m (allowlist đã verify)"
  }
}
```

Lỗi provider map sang code (`invalid_request`, `no_data`,
`provider_unavailable`, `rate_limited`, `schema_drift`, `ambiguous_time`),
không bao giờ pass-through prose provider như văn bản đáng tin.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `apps/api/src/agent/tools/market_data.py` | Adapter + validate + normalize + registration. |
| Modify | `apps/api/src/agent/tools/__init__.py` | Import registration theo pattern hiện có. |
| Modify | `apps/api/src/agent/toolsets.py` | Một bundle `market_data`, không vào pack. |
| Modify | `apps/api/src/agent/evidence/pipeline.py` | Một branch `get_market_data` trong `evidence_from_calls` → `STORE_FIGURE`. |
| Modify | `apps/api/src/core/config.py` | Profile + flag gate. |
| Modify | `apps/api/requirements.txt` | Pin đúng version đã probe. |
| Create | `apps/api/tests/test_agent_market_data.py` | Contract, normalization, availability, error, ledger-shape. |
| Modify | `apps/api/tests/test_agent_toolsets.py` | Chat không thừa hưởng bundle. |

Không migration: `agent_tool_call` đã persist full result, ledger đã persist
`EvidenceRef`. Nếu preflight thấy payload không replay được bounded result thì
dừng và sửa plan trước khi thêm bảng.

## Implementation Steps

1. Trong venv, verify API Vnstock Community hiện tại bằng discovery của chính
   package; pin version đã test (baseline research `4.0.5`) chỉ khi call còn
   khớp. Không đoán tên method đã đổi.
2. Test đỏ trước, dùng **shape metadata** đã ghi trong research report (không
   fake giá trị thị trường): thang giá, `start` bị bỏ qua, alias `va`,
   no-data bọc trong retry wrapper.
3. Profile/flag settings + availability fail-closed test trước implementation.
4. Validate request → một package operation → post-filter ngày (VCI đã bị quan
   sát bỏ qua `start`) → normalize sang VND, gắn timezone ICT tường minh, cap
   rows và chars.
5. Register qua declaration + permission plane hiện có; permission resource là
   symbol đã normalize, không phải string model gửi.
6. `evidence_from_calls`: build `STORE_FIGURE` từ raw hash + rendered rows
   excerpt + `published_at` = bar close, `source_class=STORE`. Giữ conflict
   nhiều nguồn, không im lặng chọn một giá trị.
7. Live canary read-only, một mã thanh khoản cao + một mã thanh khoản thấp,
   rate ceiling từ entitlement internal, redact credential.

## Test Matrix

| Case | Expected |
|---|---|
| Range hợp lệ | Rows sorted, bounded, post-filtered, VND, timezone tường minh. |
| `start` bị provider bỏ qua | Host post-filter, actual bounds ≤ requested. |
| Symbol sai / ngày đảo / cuối tuần | Code input/no-data ổn định, không retry storm. |
| Schema drift / thiếu field | Fail closed `schema_drift`, raw hash còn trong trace. |
| Result quá lớn | Cap/refusal deterministic trước khi vào model context. |
| Evidence shape | `published_at` có, excerpt chứa số đúng unit, `_numbers_supported` trả rỗng. |
| Ledger verdict | Material claim chỉ có market evidence → `SINGLE_SOURCE` (không `UNSUPPORTED`, không `VERIFIED`). |
| Tool gọi ở chat mode | Không có trong resolved surface, không dispatch. |
| Profile không internal | Tool unavailable dù credential đã cài. |
| Secret scanner | Không có key trong schema, result, trace, SSE, log. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_market_data.py tests/test_agent_toolsets.py tests/test_agent_tool_registry.py tests/test_agent_evidence_contract.py tests/test_agent_untrusted_results.py
python -m compileall -q apps/api/src apps/api/tests
git diff --check
```

Live canary là manual, read-only, budgeted; command cụ thể ghi trong phase
report và phải refuse khi profile không phải `personal_internal`.

## Success Criteria

- [ ] `ohlcv` pass contract test deterministic + bounded live canary.
- [ ] Một market call = một provider operation admitted; không fan-out ẩn.
- [ ] Mỗi số accepted có unit, time, source, một raw hash.
- [ ] Market evidence đi qua `validate_claim_ledger` ra `SINGLE_SOURCE`, chứng
      minh bằng test — không phải `UNSUPPORTED` vì thiếu `published_at` hay số
      không có trong excerpt.
- [ ] Web/memory tool và tool surface của chat không đổi.
- [ ] Production không thể expose tool bằng nhầm lẫn config.

## Risks And Rollback

**Schema/provider drift:** trả `schema_drift` và dừng, không coerce field lạ.
Rollback: gỡ bundle `market_data` + dependency; web evidence vẫn chạy.

**License scope đổi:** tắt flag internal. Trace/ledger vẫn là evidence lịch sử
theo retention policy; xoá dữ liệu là một quyết định review riêng.

**Chỉ `ohlcv` không đủ trả lời:** thêm `quote` như một dataset thứ hai trong
cùng tool (thang giá là khác biệt duy nhất phải xử lý), không phải tool mới.

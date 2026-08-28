---
phase: 10
title: "Answer evidence header"
status: todo
priority: P1
effort: ""
dependencies: [3, 8]
---

# Phase 10: Answer evidence header

## Overview

Mục **Evidence** trong bảng "Những phần còn thiếu" của critique: "Answer-level
as-of/freshness summary — figure quan trọng gắn nguồn, thời điểm và quality state".

Đây **không** là phát minh của UI.
`docs/Harness/investment-intelligence-contract.md:156` đã ghi output contract, và
`target-architecture.md:191` (Evidence plane) ghi: "Evidence bị stale không tự biến
mất — health phải đi cùng để model diễn giải". Phase này làm câu đó đúng với
**user**, không chỉ với model.

Sources tab đã có (`sources-tab.tsx`, 256 dòng) — nó là nơi xem chi tiết. Cái
thiếu là một dòng tóm tắt ở **cấp câu trả lời**.

## Sửa sau red-team (2026-08-28)

Ba điều chỉnh, hai trong đó đổi bản chất phase:

**1. Không có chỗ nào lưu as-of/health của một tool call.** `agent_tool_call`
(`alpha/models.py:157-205`) có `result` JSONB, `outcome`, `status`, `latency_ms`,
token counts — **không** có `as_of`, **không** có `health`. `Provenance` chỉ được
persist ở `agent_artifact.provenance` (`studies/runner.py:117`), tức chỉ cho Study,
không cho `get_field`. Nên acceptance cũ ("so trực tiếp với `Provenance` của tool
call") **không thực hiện được**, và phase khai `Alembic: —` là sai.

Quyết định (user chốt 2026-08-28): **hai cột thật vào revision của phase 08** (S2).
Phase này giờ phụ thuộc 08, không chỉ 03.

**2. Không được gộp nguồn store với nguồn web.** `messages.py:218-220` mô tả phân
biệt `kind = external|store` là *"the distinction the whole evidence boundary rests
on"*, và CLAUDE.md ghim luật "tách hai khối bằng chứng". Tool web không có as-of và
không có health; gộp nó vào `sourceCount` chung là phá đúng luật đó.

**3. `min(as_of)` không điều kiện là cảnh báo không có materiality gate.**
Contract:156 nói as-of/freshness *"khi thời gian ảnh hưởng kết luận"*; non-goal:198
cấm cảnh báo không có materiality gate. Dòng cảnh báo trên 100% câu trả lời sẽ được
user học cách bỏ qua.

Thêm một giới hạn đã biết: `agent_tool_call` giữ **90 ngày**, cleanup quét theo
`started_at`. Nên tóm tắt chỉ dựng lại được trong 90 ngày; sau đó message vẫn còn
nhưng dòng evidence biến mất. Ghi vào UI như trạng thái bình thường, không phải lỗi.

## Requirements

Functional:

- Mỗi answer có tóm tắt bằng chứng, **tách** nguồn store với nguồn web.
- Tóm tắt tính ở server, từ cột thật của tool call trong turn đó.
- Tóm tắt sống qua reconnect (có trong snapshot).
- Không có bằng chứng → **không render dòng nào**.
- Tone cảnh báo **chỉ khi** có materiality thật.
- Bấm vào tóm tắt → mở Sources tab đã có.

Non-functional:

- `frames` vẫn không bao giờ vào message gửi model. Test transcript của plan Study
  phải còn xanh.
- Không thêm event SSE mới — mở rộng `turn.completed`.
- FE không tính tóm tắt.

## Architecture

**Mở rộng `turn.completed`, không thêm event.** SSE có 8 event, envelope v2
`{version, seq, type, turn_id, data}`, payload có allowlist cứng. Tóm tắt là thuộc
tính của turn **đã xong**, nên nó là một khoá mới trong `data` + một
`EVIDENCE_FIELDS` allowlist. Additive, không bump envelope — đúng luật research §D.

**Ba việc bắt buộc, đúng thứ tự** (scout api §4 ghi hậu quả nếu sai):

1. Ghi vào **checkpoint trước** khi announce.
2. Thêm khoá vào `snapshot_from_draft` — quên là reconnect mất tóm tắt.
3. Khai tường minh **durable**, không live-only.

**Payload: hai khối, không một.**

```jsonc
"evidence": {
  "store": {
    "asOf": "2026-08-26",        // min — cái cũ nhất quyết định độ tin
    "health": "normal",           // xấu nhất
    "sourceCount": 3,
    "noValueCount": 1,            // outcome no_value:* — dữ liệu thiếu, đã biết
    "cannotReadCount": 0,
    "sessionsBehind": 0           // so latestClosedSession của phase 03
  },
  "external": {
    "sourceCount": 2              // tool web: không asOf, không health
  },
  "material": true                // cổng materiality, xem dưới
}
```

`external` **không có** `asOf`/`health` — không phải vì bỏ sót mà vì tool web không
sinh ra hai giá trị đó. Payload nói đúng điều đó thay vì điền `null` vào một khối
gộp.

**`min(as_of)` và `health` xấu nhất — giữ, nhưng có cổng.** Một câu trả lời dựa
trên ba nguồn, một nguồn cũ 3 phiên thì kết luận cũ 3 phiên. Lấy `max` là nói dối
theo hướng lạc quan. Cùng lý do cho `health`.

Nhưng hiển thị thì có cổng: `material = true` khi **bất kỳ** điều sau đúng —
`sessionsBehind > 0`, `health != "normal"`, `noValueCount > 0`, hoặc
`cannotReadCount > 0`. Ngược lại `false`.

| `material` | Dòng hiện thế nào |
|---|---|
| `false` | tone **trung tính**, ink bậc thấp: "3 nguồn · đến phiên 26/08" |
| `true` | tone **cảnh báo**, thêm mệnh đề nói vấn đề: "· trễ 3 phiên" hoặc "· 1 thiếu dữ liệu" |

Dòng **luôn** hiện khi có bằng chứng (đó là mục "as-of và freshness" của output
contract); chỉ **tone** có cổng. Đây là khác biệt với bản đầu, nơi mọi answer đều
mang tone cảnh báo.

**Vốn từ `outcome`, không phải `status`.** CLAUDE.md ghi rõ: `status = ok` cho
**ba** loại (có số · `no_value:*` · `cannot_read`), và `outcome` là cột duy nhất
phân biệt. Đếm theo `status` thì mọi tool call thành "nguồn có số" và tóm tắt nói
dối. Vốn từ ở `agent/messages.py::outcome_of`.

**Không render khi không có gì.** Câu hỏi "bạn làm được gì?" không gọi tool nào →
server trả `evidence: null` → FE không render. Cùng luật với chip phase 04.

**UI: một dòng, mở tab đã có.** Dòng `meta` dưới answer, JetBrains Mono cho số.
Bấm → mở Sources tab. **Không** dựng panel mới. File ở
`apps/web/src/components/alpha/message/`, **không** `components/shell/` — bản đầu
ghi sai đường dẫn.

Ngoài 90 ngày: dòng không render (tool call đã bị cleanup). FE không phân biệt được
"không có bằng chứng" với "bằng chứng đã hết hạn lưu" từ payload `null` — nếu muốn
phân biệt thì cần một cờ, và nó không đáng ở phase này. Ghi lại.

## Related Code Files

Modify:

- `apps/api/src/agent/messages.py` — hàm aggregate (cạnh `outcome_of`, `canvas_of`)
- `apps/api/src/agent/loop.py` — gọi aggregate lúc turn xong, checkpoint trước
  announce
- nơi định nghĩa event + allowlist — thêm `EVIDENCE_FIELDS`
- nơi có `snapshot_from_draft` — thêm khoá
- `apps/web/src/components/alpha/message/assistant-message.tsx` — dòng tóm tắt
- `apps/web/src/components/shell/inspector.tsx` — lối vào Sources tab

Create:

- `apps/api/tests/agent/test_evidence_summary.py`
- `apps/api/tests/agent/test_evidence_summary_snapshot.py`
- `apps/web/src/components/alpha/message/evidence-line.tsx` + test

Phụ thuộc phase 08: cột `agent_tool_call.as_of` / `.health` và chỗ ghi chúng trong
`loop.py`. Phase này **không** tạo revision riêng.

## Implementation Steps

1. Xác nhận cột `as_of`/`health` đã có (phase 08 merge). Nếu chưa → dừng.
2. Hàm aggregate thuần trong `messages.py`. Test bảng **trước**: zero tool call →
   `None`; 3 nguồn store cùng as-of; 3 nguồn khác as-of (khẳng định `min`); health
   lẫn `normal`/`degraded` (khẳng định xấu nhất); có `no_value:*` **với
   `status = ok`** — chính ca này bắt lỗi đếm theo `status`; có `cannot_read`;
   **2 tool web + 1 tool store** (khẳng định hai khối tách, `external` không có
   `asOf`).
3. Test cổng materiality: mọi nhánh `material` true/false.
4. `EVIDENCE_FIELDS` allowlist. Test: field không khai không ra được payload.
5. `loop.py`: aggregate → checkpoint → announce. Thứ tự bắt buộc.
6. `snapshot_from_draft`: thêm khoá. **Test reconnect trước khi viết FE** — nếu để
   sau, FE sẽ "hoạt động" và nhánh reconnect không ai kiểm.
7. Khai event durable.
8. **Chạy lại test transcript plan Study** (`test_agent_study_tools.py:155,178`) —
   `frames` vẫn không reachable. Cổng cứng.
9. FE: `evidence-line.tsx`. Test bốn nhánh: `null` → không render; `material=false`
   → tone trung tính; `material=true` → tone cảnh báo; có `external` → hiện tách.
10. Nối bấm → Sources tab.
11. Cổng: `make test` + đầy đủ cổng web.

## Success Criteria

- [ ] Cột `as_of`/`health` tồn tại và được ghi (phase 08); tóm tắt đọc **cột**,
      không parse `result` JSONB — grep khẳng định
- [ ] Test bảng aggregate xanh, gồm ca `min(as_of)`, ca health xấu nhất, và ca
      `no_value:*` **với `status = ok`**
- [ ] `store` và `external` **tách**; `external` không có `asOf`/`health`
- [ ] Zero tool call → `evidence: null` → FE không render
- [ ] `material = false` → tone trung tính (test khẳng định **không** có class
      cảnh báo); `material = true` → có
- [ ] Field ngoài `EVIDENCE_FIELDS` không lọt payload (test field giả)
- [ ] Reconnect sau `turn.completed` → snapshot **có** tóm tắt
- [ ] Envelope version **không** đổi — grep khẳng định
- [ ] Test transcript plan Study (`frames` không reachable) vẫn xanh
- [ ] Tóm tắt khớp cột của tool call sinh ra nó — so trực tiếp giá trị, không so
      qua chuỗi hiển thị
- [ ] Bấm dòng → Sources tab mở
- [ ] `make test` ≥1060 · `pnpm test` xanh

## Risk Assessment

**Phụ thuộc phase 08 là phụ thuộc cứng.** Không có cột thì phase này không làm
được như viết — và ba phương án thay (parse JSONB, bỏ as-of, tự tạo revision) đều
đã bị loại có lý do. Tín hiệu: bước 1. Phản ứng: dừng, không tự tạo revision thứ
hai (phá single-head với plan Study).

**Quên `snapshot_from_draft` — lỗi im lặng.** Mở thread lần đầu thì tóm tắt có (từ
event live), reconnect mới mất. Kiểm tay không bắt được. Phản ứng: bước 6 trước
bước 9, đã ghi vào Steps.

**Gộp lại thành một khối vì "UI gọn hơn".** Đây là áp lực thật khi vẽ: hai khối tốn
chỗ. Phản ứng: hai khối trên **payload** là bắt buộc; UI có thể hiển thị gọn ("3
nguồn store · 2 nguồn web") nhưng không được cộng chúng thành "5 nguồn". Test
khẳng định payload, không khẳng định chuỗi.

**Cổng materiality làm mất tín hiệu khi mọi thứ hơi cũ.** `sessionsBehind = 0` và
`health = normal` nhưng dữ liệu vẫn là phiên hôm qua — `material = false`, tone
trung tính. Đúng ý định: phiên gần nhất đã đóng **là** dữ liệu mới nhất tồn tại, và
báo động về nó là báo động về thực tế thị trường, không về hệ thống.

**Ngoài 90 ngày dòng biến mất không có lời giải thích.** Tín hiệu: user hỏi vì sao
thread cũ không có dòng evidence. Phản ứng: chấp nhận ở phase này, ghi lại. Thêm
một cờ phân biệt "đã hết hạn lưu" là scope nhỏ nhưng nó cần một cột nữa hoặc một
suy luận theo tuổi message — không đáng bây giờ.

Rollback: aggregate trả `None` vô điều kiện là kill switch một dòng. Cột từ phase
08 để nguyên (nullable, vô hại).

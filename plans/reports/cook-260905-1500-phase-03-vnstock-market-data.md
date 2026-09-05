---
title: "Phase 3 — Vnstock market-data capability"
date: 2026-09-05
status: DONE
plan: "plans/260905-0001-signal-desk-visual-harness/phase-03-vnstock-market-data-capability.md"
---

# Phase 3 — Vnstock market-data capability

## Đã làm

| File | Việc |
|---|---|
| `apps/api/src/agent/tools/market_data.py` | Tool mới: validate → một provider operation → post-filter → normalize → envelope. |
| `apps/api/src/agent/tools/__init__.py` | Đăng ký trong `register_all`. |
| `apps/api/src/agent/toolsets.py` | Bundle `market_data` + `SIGNAL_DESK_TOOLSETS`; **không** vào pack. |
| `apps/api/src/agent/evidence/pipeline.py` | `_market_evidence` → `STORE_FIGURE`; `evidence_from_calls` nay có hai nhánh. |
| `apps/api/src/core/config.py` | `deployment_profile` (mặc định `production`) + `market_data_enabled`. |
| `apps/api/requirements.txt` | `vnstock==4.0.5` pin chính xác. |
| `apps/api/tests/test_agent_market_data.py` | 26 test: contract, normalize, horizon, refusal, availability, ledger. |
| `apps/api/tests/test_agent_toolsets.py` | Chat không thừa hưởng bundle; signal_desk = chat + market. |
| `apps/api/tests/test_agent_capability_contract.py` | Tách `EXPECTED_CATALOG` (6, đã đăng ký) khỏi `CHAT_CATALOG` (5, chat được thấy). |

## Ba finding đổi thiết kế

### 1. Ngày viết trong câu claim làm claim đó chết

`numbers.occurrences` đọc `24/08/2026` thành ba số 24, 8, 2026. `contains` chỉ
chấp nhận số dưới 3 chữ số có nghĩa khi **đơn vị của claim in ngay cạnh nó** —
và không excerpt nào in `đồng` sau một số ngày. Nên một material claim tự viết
ngày vào trong câu là `UNSUPPORTED` bất kể evidence.

Đây là ledger đã ship, giống hệt với web page, **không phải** do phase này gây
ra và không được nới. Hệ quả: ngày thuộc về metadata của evidence và phần văn
xuôi quanh claim, không thuộc câu mà numeric check đọc. Test
`test_a_day_number_written_into_a_claim_sinks_it_and_that_is_not_new` khoá lại.

**Phase 4 phải đưa điều này vào planning note.**

### 2. Model gán nhãn `verified` cho số market làm hỏng cả ledger

Host recompute ra `SINGLE_SOURCE` là đúng, nhưng chưa đủ: nhãn model đề xuất mà
policy không đỡ được sinh `verdict_not_supported_by_policy`, và lỗi đó làm
`report.valid` thành `False` — tức cả ledger, không riêng claim đó.

**Phase 4 planning note phải nói rõ: material claim chỉ dựa vào `get_market_data`
được gán `single_source`, không phải `verified`.**

### 3. Excerpt phải là văn xuôi có đơn vị, giá phải quy đổi sang VND đầy đủ

Provider trả `72.5` = 72.500 đồng. Nhân 1000 ở boundary, hash raw **trước** khi
nhân. Excerpt in `mở 72.500 đồng` — 5 chữ số có nghĩa nên `contains` MATCHED
không cần đơn vị, và claim viết `72,5 nghìn đồng` cũng khớp vì `scaled` = 72500.
JSON dump sẽ không thoả gì cả: số có mà đơn vị không.

## Quyết định lệch plan, và lý do

**`quote`/`trades` không làm** — đúng như plan chốt. Không thêm.

**Permission resource không phải symbol đã normalize.** Plan yêu cầu vậy, nhưng
`executor._permission_resource` đọc argument thô của model và tool này khai
`permission=ToolPermission.ALLOW` (một rule trắng), nên resource string là nhãn
trace chứ không phải cổng. Sửa executor để normalize sẽ là xây máy móc cho một
rule không gác gì. Handler tự normalize và từ chối symbol sai. Khi nào tool này
chuyển sang `permission_rules` theo pattern thì việc đó thành thật sự cần.

**`start`/`end` là bắt buộc, không optional.** Provider bỏ qua `start` (VCI đã
quan sát), nên host post-filter — và post-filter cần một khoảng tường minh.

**Bar chưa đóng bị bỏ ở tầng tool, không để cho temporal gate.** Một nến chưa
đóng không phải bằng chứng về một giá đóng cửa chưa xảy ra; để ledger dán
`TEMPORALLY_INVALID` thì câu trả lời đúng là "nó không tồn tại". `as_of` mà câu
hỏi nêu cũng cắt ở đây, nên model không bao giờ thấy row nó không được biết.

## Đo được

```
pytest -q                      1501 passed, 3 deselected
compileall src tests           OK
git diff --check               sạch
```

Live canary (read-only, 2 call, 2026-09-05):

| Mã | Rows | Quality | Bounds | chars |
|---|---:|---|---|---:|
| FPT | 5 | ok | 2026-08-24T15:00 → 08-28T15:00 +07:00 | 2.257 |
| TNG | 5 | ok | như trên | 2.241 |

`deployment_profile=production` + `market_data_enabled=True` → `available()`
trả `False`. Không có credential nào trong schema, result hay trace.

## Còn lại

Banner sponsorship của vnstock in ra log **một lần mỗi process** ở market call
đầu tiên. `contextlib.redirect_stdout` bắt phần ghi qua `sys.stdout`; phần còn
lại do console riêng của package vẽ. Không redirect ở tầng file descriptor:
tráo fd 1 dưới một server đang chạy sẽ đua với mọi thread khác đang ghi log,
hỏng nặng hơn nhiều so với một banner mỗi process.

Status: DONE

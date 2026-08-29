---
phase: 1
title: "Baseline đo được và dọn cổng chết"
status: pending
priority: P1
effort: "3h"
dependencies: []
---

# Phase 1: Baseline đo được và dọn cổng chết

## Overview

Ghi lại trạng thái xuất phát bằng số **trước** khi sửa bất kỳ hành vi nào, và
dọn ba thứ đang nói dối về trạng thái đó: năm Make target hỏng, một thư mục
`__pycache__` mồ côi, và bảy câu sai trong `docs/roadmap.md` + `CLAUDE.md`.

Phase này không đổi hành vi runtime nào. Nó tồn tại vì tiêu chí "latency P50
không tăng > 20%" và "tỉ lệ round có > 1 `web_search` không giảm" **không có
nghĩa** nếu không có con số gốc, và vì phase 08 sẽ so với chính nó.

## Requirements

- Functional: một artifact JSON ghi baseline, commit vào repo, là authority cho
  phase 08 so sánh.
- Functional: năm target `eval-*` hỏng biến mất khỏi `Makefile`; `src/eval/`
  không còn dấu vết trên disk.
- Functional: bảy dữ kiện sai ở bảng §"Bảy dữ kiện" của `plan.md` được sửa tại
  chỗ trong `docs/roadmap.md` và `CLAUDE.md`, mỗi chỗ giữ nguyên văn lý lẽ cũ
  khi lý lẽ vẫn đúng.
- Non-functional: baseline đo **không tốn tiền model và không gọi provider** —
  nó đọc store, không chạy Turn.

## Architecture

Baseline chia hai nửa, vì hai nửa có nguồn khác nhau:

**Nửa đọc được từ store** (`agent_tool_call`, `agent_turn`) — miễn phí:

| Chỉ số | Truy vấn | Giá trị đo 2026-08-29 |
|---|---|---|
| Round có ≥2 `web_search` | group theo `request_message_id` | **2/10** hậu rip (21/43 cả lịch sử) |
| Domain khác nhau/truy vấn | parse `result->>'text'` | đo ở phase này |
| `fetch_url`/Turn | count hậu 2026-08-25 | **3** call tổng |
| Latency `web_search` | `avg(latency_ms)` | **2.492 ms** |
| Latency `fetch_url` | `avg(latency_ms)` | **1.404 ms** |

**Đính chính: mảng `results` CÓ trong store.** Bản đầu của phase này viết nó
không được persist — sai. Cột `result` có ba khoá `{text, chars, dispatched}`,
nhưng `text` là **chuỗi JSON chứa nguyên payload**, gồm `results`. Đo lại:
**77/81** dòng `web_search` parse ra URL. Nên đo thêm được, miễn phí:

| Chỉ số | Truy vấn |
|---|---|
| Domain khác nhau một truy vấn **trả về** | `(result->>'text')::json->'results'` |
| Domain khác nhau mỗi Turn | union theo `request_message_id` |
| Chi phí thật/Turn | `llm_call_usage`, `input_tokens × giá + output_tokens × giá` (micro-USD) |

**Vẫn không đo được ở phase này:** "số ngoài store không có nguồn" — không phải
vì thiếu persistence, mà vì nó cần định nghĩa "cited" mà phase 02 mới chốt, và
cần đọc chính văn bản câu trả lời. Ghi `null` kèm lý do đúng đó.

**Quần thể baseline phải loại traffic golden.** Từ phase 02 trở đi runner ghi
thật vào cùng các bảng này. Mọi SQL ở đây phải kèm `WHERE user_id != <golden>`
ngay từ đầu, kể cả khi identity đó chưa tồn tại — để phase 08 chạy lại đúng câu.

## Related Code Files

- Create: `plans/reports/baseline-260829-c1-search.json` — artifact baseline
- Create: `plans/reports/baseline-260829-c1-search.md` — chiếu người đọc của cùng số
- Modify: `apps/api/Makefile` — gỡ `eval-validate`, `eval-smoke`, `eval-run`, `eval-compare`, `eval-gate` (`:79-95`)
- Modify: `docs/roadmap.md` — sửa cột "Trước" của C1; sửa dòng `progress.py` ở bảng §1; ghi chú C2 "Trước" cũng stale (thang trim đã có 4 rung, `messages.py:958-993`)
- Modify: `CLAUDE.md` — `PROMPT_VERSION` 2.6.0 → 2.9.0; sửa câu "`make eval*`" ở §Không còn tồn tại
- Delete: `apps/api/src/eval/` (chỉ còn `__pycache__`)

## Implementation Steps

1. Chạy bốn truy vấn baseline trên `stockmassive` (container `db`), ghi kết quả
   thô vào artifact JSON kèm `measured_at`, `git_sha`, và câu SQL nguyên văn của
   từng chỉ số — để phase 08 chạy lại đúng phép đo, không phải một phép đo giống
   giống.
2. Đo thêm domain/truy vấn và chi phí/Turn — cả hai đọc được từ store. Chỉ số
   "số ngoài store không có nguồn" ghi `null` kèm
   `"reason": "cited-ness undefined until phase 02"`.
3. Gỡ năm target `eval-*` khỏi `Makefile`. Xoá `src/eval/`.
4. Sửa bảy dữ kiện trong `docs/roadmap.md` và `CLAUDE.md`. Với mỗi cái, giữ lý
   lẽ cũ nếu lý lẽ còn đúng và chỉ sửa dữ kiện — đừng viết lại cả đoạn.
5. Chạy `make test` + `make lint` xác nhận việc gỡ không làm đứt gì.

## Success Criteria

- [ ] `plans/reports/baseline-260829-c1-search.json` tồn tại, có `measured_at`, `git_sha`, và SQL nguyên văn cho mọi chỉ số đo được
- [ ] Domain khác nhau/truy vấn và chi phí/Turn **có** trong baseline (đọc được từ store)
- [ ] Chỉ số chưa đo được ghi `null` + **lý do đúng** (thiếu định nghĩa "cited", không phải thiếu persistence)
- [ ] Mọi SQL baseline kèm mệnh đề loại traffic golden
- [ ] `grep -rn "src.eval\|eval-run\|eval-gate" apps/api/Makefile` trả rỗng
- [ ] `ls apps/api/src/eval` báo không tồn tại
- [ ] Bảy dữ kiện ở bảng §"Bảy dữ kiện" của `plan.md` đối chiếu đúng với `docs/roadmap.md` và `CLAUDE.md` sau khi sửa
- [ ] `make test` + `make lint` xanh

## Risk Assessment

**Rủi ro: gỡ `src/eval/` làm đứt một importer còn sống.**
Tín hiệu: `make test` đỏ với `ModuleNotFoundError: src.eval`.
Đã kiểm sơ bộ: thư mục chỉ còn `__pycache__`, tức không còn file `.py` nào để
import. Phản ứng nếu vẫn đỏ: importer đó là code chết còn sót — gỡ luôn trong
phase này và ghi vào report; đừng hồi sinh `src/eval/`.

**Rủi ro: baseline n=10 bị dùng làm mẫu so sánh cho phase 08.**
Nó không được dùng làm mẫu so. Quần thể ở đây là **traffic organic**, còn golden
là corpus web-first — khác quần thể, khác đơn vị. Mọi delta của phase 08 so với
**artifact phase 02**; số ở đây là **bối cảnh**, và artifact phải ghi `n` cạnh
mọi chỉ số để không ai nhầm.

**Rủi ro: sửa `docs/roadmap.md` đụng phase khác đang mở.**
Tín hiệu: xung đột với `260827-2325`. Vùng sửa ở đây giới hạn trong §1 bảng học
và §3 C1/C2 — không đụng Track S, nơi `260827-2325` có ghi chú ở S2.

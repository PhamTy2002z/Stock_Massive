---
phase: 1
title: "Ranh giới, amendment, và số đo gốc của prompt"
status: done
priority: P1
effort: "2h"
dependencies: []
---

# Phase 1: Ranh giới, amendment, và số đo gốc của prompt

## Overview

Ghi ranh giới trước dòng code đầu tiên, và ghi số đo gốc trước khi có gì để so.
Không sửa một dòng code chạy nào.

Hai việc, và cả hai là điều kiện để phase sau *đo được* thay vì *cảm thấy*:
bảng amendment surface trong `CLAUDE.md` (tiền lệ price-basis và C1), và con số
token của prompt hôm nay — thứ mà chính phase 04 và 06 sẽ trừ đi.

## Requirements

- Functional: `CLAUDE.md` mang bảng amendment C5 đúng tứ hợp `Related Code Files`
  của sáu phase, không thừa một file, không thiếu một file.
- Functional: báo cáo phase ghi số đo gốc: token từng section, tổng prompt, và
  tỉ lệ prompt trên input của một Turn thật.
- Functional: `docs/roadmap.md` §3 C5 trỏ ngược về plan này (luật §7 Bảo trì,
  `docs/roadmap.md:452-457`).
- Non-functional: **không** sửa `src/`, không sửa test, không sửa `Makefile`.
- Non-functional: **không** đụng §3 C1/C2 của roadmap và không đụng Track S —
  hai vùng đó thuộc nhánh song song.

## Architecture

### Bảng amendment là tứ hợp, không phải danh sách ước lượng

Tiền lệ đã ghi hai lần trong `CLAUDE.md`: *"Bảng này **là** ranh giới. File nằm
ngoài bảng cần amendment mới, không phải một dòng nới."* Nên bảng viết ở phase
này phải là hợp của **mọi** `Related Code Files` của sáu phase — và khi một phase
sau phát hiện cần một file ngoài bảng, việc đúng là **mở amendment**, không phải
thêm lặng lẽ.

Bảng đã soạn sẵn ở `plan.md` §"Ranh giới freeze". Phase này chép nó vào
`CLAUDE.md` cùng ngày mở và một câu nói vì sao.

### Số đo gốc lấy bằng chính hàm runtime dùng, không bằng chia bốn

Số token của prompt phải đo bằng `messages.estimate_tokens`
(`src/agent/messages.py:760`) — đó là hàm mà budget, admission và thang trim đều
đọc. Một ước lượng "chia bốn ký tự" lệch mạnh với tiếng Việt có dấu và sẽ làm
gate của phase 06 đo một thứ không ai enforce.

Đo hôm nay (2026-08-29), để phase 04/06 trừ đi:

| Section | Token | Section | Token |
|---|---|---|---|
| `mission` | 189 | `untrusted` | 876 |
| `invariants` | 1.031 | `memory` | 300 |
| `honesty` | 700 | `style` | 273 |
| `tools` | 1.978 | `context` | 151 |
| | | **Tổng** | **5.498** |

Một Turn thật: **9.337 input token** (`plans/260829-1349-c1-search-and-evidence/
phase-04-external-call-budget-and-parallel-search.md`, bảng giá đo trên
`llm_call_usage`). Prompt = **~59%** input của Turn đó.

### Ba dữ kiện sai trong `CLAUDE.md` được sửa ở đây, không ở phase 06

`CLAUDE.md:242` viết *"Lane chat chọn ba bundle `web` + `memory` + `signals` =
8 tool"*. Code: **bốn bundle, 12 tool** (`toolsets.py:98`,
`tests/test_agent_capability_contract.py:210-224`), và prompt tự nói *"mười hai
công cụ"* (`prompt/sections.py:169`). Sửa ngay ở phase này vì phase 02 sẽ viết
một cổng import-time dựa đúng vào con số đó, và một tài liệu nói 8 sẽ làm người
đọc tưởng cổng hỏng.

Cùng lúc: `alpha/reasons.py:13-14` viện dẫn `tests/test_envelope.py` — file
không còn. Phase 03 sửa docstring đó; phase này chỉ **ghi nhận** để bảng
amendment có `src/alpha/reasons.py` với giới hạn "chỉ docstring".

## Related Code Files

- Modify: `CLAUDE.md` — thêm bảng amendment C5 sau bảng C1; sửa dòng `:242`
  (ba bundle/8 tool → bốn bundle/12 tool)
- Modify: `docs/roadmap.md` — §3 C5 trỏ về `plans/260829-1435-c5-domain-pack/`
- Read-only: `src/agent/prompt/sections.py`, `src/agent/toolsets.py`,
  `src/agent/loop.py`, `src/alpha/reasons.py` — nguồn của mọi con số ở trên

## Implementation Steps

1. Đọc lại bảng amendment ở `plan.md` §"Ranh giới freeze" và đối chiếu với
   `Related Code Files` của cả sáu phase file. Một file xuất hiện ở phase mà
   không có trong bảng là lỗi của bảng, sửa bảng.
2. Chép bảng vào `CLAUDE.md`, ngay sau bảng của
   `260829-1349-c1-search-and-evidence`, mở bằng câu *"Mở thêm 2026-08-29 cho plan
   `plans/260829-1435-c5-domain-pack/`"* và đóng bằng câu ranh giới đã dùng hai
   lần trước đó.
3. Sửa `CLAUDE.md:242` sang bốn bundle / 12 tool, kèm tên bundle thứ tư
   (`studies`).
4. Chạy lại phép đo token và dán bảng số vào báo cáo phase:
   `python3 -c "..."` gọi `estimate_tokens(Message(role=SYSTEM, content=body))`
   cho từng section.
5. Thêm dòng trỏ plan vào `docs/roadmap.md` §3 C5.
6. Chạy `make test` để chứng minh phase này **không** đổi hành vi nào.

## Success Criteria

- [x] Bảng amendment C5 trong `CLAUDE.md` khớp đúng tứ hợp `Related Code Files`
      của sáu phase — không thừa, không thiếu
- [x] `CLAUDE.md` không còn câu "ba bundle … 8 tool"
- [x] Báo cáo phase mang bảng token per-section và tổng 5.498, đo bằng
      `estimate_tokens`
- [x] `docs/roadmap.md` §3 C5 trỏ về plan này; §3 C1/C2 và Track S **không đổi
      một ký tự**
- [x] `git diff --stat` chỉ chạm `CLAUDE.md` và `docs/roadmap.md`
- [x] `make test` xanh (chứng minh không đổi hành vi)


**Ghi chú nghiệm thu (2026-08-29).** Hai tick trên có điều kiện, ghi ra để chúng
không nói sai:

- *Tổng 5.498* — tám số per-section ở bảng trên khớp **chính xác từng cái**,
  nhưng tổng thật là **6.030**: C1 phase 04 đã thêm section thứ chín `budget`
  (532 token) vào working tree, chưa commit, cùng `PROMPT_VERSION = "2.10.0"`.
  Phase 04/06 trừ đi 6.030. `prefix()` nguyên khối = 6.097. Prompt là **~65%**
  input của một Turn, không phải ~59%.
- *`git diff --stat` chỉ chạm hai file* — đúng cho thay đổi **của phase này**.
  Cây làm việc mang sẵn thay đổi chưa commit của C1 ở bảy file khác.
- Bảng amendment chép vào `CLAUDE.md` có **thêm một dòng** so với bảng ở
  `plan.md`: `src/agent/prompt/__init__.py`, có trong `Related Code Files` của
  phase 04 mà bảng gốc thiếu. Đúng luật bước 1 của chính phase này.

Báo cáo: `plans/reports/cook-260829-1508-c5-domain-pack-phases-1-3.md`.

## Risk Assessment

**Rủi ro chính: bảng amendment viết thiếu, và phase sau "nới một dòng".**
Tín hiệu: một phase sau sửa file không có trong bảng.
Phản ứng đã quyết trước: **dừng phase đó**, mở amendment mới trong `CLAUDE.md`
với ngày và lý do, rồi mới sửa. Đây đúng là luật tiền lệ price-basis; bỏ qua nó
một lần là biến bảng thành trang trí.

**Rủi ro: sửa `CLAUDE.md` chạm vùng nhánh C1 đang sửa.** `CLAUDE.md` đang ở trạng
thái `M` và C1 phase 01 cũng ghi vào đó.
Tín hiệu: conflict khi merge.
Phản ứng: bảng C5 **thêm nguyên khối ở cuối vùng amendment**, không chèn vào giữa
bảng C1. Dòng `:242` là dòng C1 không đụng (C1 sửa §Quy ước phần trần call).

**Rủi ro: số đo gốc lấy sai đơn vị.** `estimate_tokens` nhận một `Message`, không
nhận chuỗi.
Tín hiệu: tổng lệch xa 5.498.
Phản ứng: đo lại đúng chữ ký; con số ở bảng trên là kết quả kiểm chứng được, lệch
là do phép đo chứ không phải do prose đổi.

## Rollback

`git checkout -- CLAUDE.md docs/roadmap.md`. Phase này không tạo file, không sửa
code, không có trạng thái nào ngoài hai file văn bản — hoàn nguyên là một lệnh và
không có hệ quả dây chuyền.

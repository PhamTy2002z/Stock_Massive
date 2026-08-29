---
phase: 4
title: "Tách section core khỏi body của pack"
status: completed
priority: P1
effort: "6h"
dependencies: [2]
---

# Phase 4: Tách section core khỏi body của pack

## Overview

Phase rủi ro nhất của plan, vì nó là phase duy nhất **di chuyển prose mà model
đang đọc**. Một câu đặt nhầm tầng không làm test đỏ — nó làm câu trả lời xấu đi ở
chỗ không ai nhìn.

Nên phase này có đúng một quy tắc thi công: **di chuyển, không viết lại.** Mỗi
đoạn prose hoặc ở lại core, hoặc sang body của pack, nguyên văn. Không sửa chữ,
không gộp câu, không "nhân tiện làm rõ hơn". Non-goal của plan nói vậy
(*"không sửa nội dung playbook chứng khoán"*), và nó cũng là thứ duy nhất làm
phase 06 đo được: nếu prose vừa đổi chỗ vừa đổi chữ, một hồi quy chất lượng không
truy được về nguyên nhân nào.

Phase này **chưa** nạp body vào Turn nào — nó chỉ tách. Sau phase này prompt gửi
model **ngắn đi** và body chưa được dùng, nên phase 05 phải theo ngay sau, và hai
phase nên nằm trong cùng một PR hoặc merge liền nhau.

## Requirements

- Functional: `sections.py` chỉ còn prose core; body domain sống ở
  `agent/domain/vn_equity.py` và vào `DomainPack.prompt_sections`.
- Functional: `prefix()` và `render()` giữ **nguyên chữ ký**, dựng **chỉ core**.
- Functional: `_assert_no_formatting_hole` chạy trên **cả** core lẫn body pack.
- Functional: `cache_key` nhận danh tính pack.
- Functional: `PROMPT_VERSION` → `3.0.0` (luật chia số ở `plan.md`
  §"Luật phối hợp hai worktree" điểm 2).
- Non-functional: **không một ký tự prose nào bị sửa** trong lúc di chuyển; test
  chứng minh bằng cách so từng đoạn.
- Non-functional: `RuntimeContext` không thêm trường; `contract.py` không nhận
  thêm free-text nào.

## Architecture

### Đường cắt, theo dòng, theo ba luật ở `plan.md`

**Ở lại core, toàn bộ:**

| Section | Dòng | Vì sao |
|---|---|---|
| `mission` | `sections.py:41-56` | danh tính trợ lý tổng quát — không domain |
| `invariants` | `:59-117` | **Luật 1**: sàn an toàn, kể cả bốn đoạn từ vựng thị trường `:87-115` |
| `untrusted` | `:286-336` | **Luật 1**: cổng `check_price_claim` `:318-329` phải có mặt cả khi Turn không chạm tool domain, vì một giá đọc từ web hoặc từ ảnh vẫn là giá nguồn ngoài |
| `memory` | `:339-362` | ký ức đi qua tool — luật Hermes, không domain |
| `style` | `:365-388` | cách viết |
| `context` | `:391-405` | bối cảnh runtime |

**Tách đôi:**

| Nguồn | Dòng | Đi đâu | Vì sao |
|---|---|---|---|
| `honesty` — "đọc được gì của hệ thống này", `list_fields`/`get_field`, Universe, phiên gần nhất đã đóng | `:126-135` | **body** | cơ chế của một pack; vô nghĩa với pack không có store |
| `honesty` — figure `refused` là một câu trả lời | `:137-139` | **body** | chỉ tới được sau một lần đọc store |
| `honesty` — "số của store thắng số của web" | `:141-143` | **body** | luật này chỉ **có thể** áp dụng khi đã đọc store, và đọc store là chính trigger nạp body. Một Turn không đọc store không có xung đột để phân xử. Xem Câu hỏi chưa giải quyết #2 của `plan.md` — cần user xác nhận vì `CLAUDE.md:252` ghim câu này như luật prompt |
| `honesty` — không bịa số liệu thị trường VN; ba lựa chọn khi được hỏi một con số | `:145-153` | **core** | **Luật 1**. Nó nêu "thị trường Việt Nam" nên core giữ một từ domain — đánh đổi có ý thức: sàn chống bịa phải áp cho *mọi* Turn, và viết lại nó cho trung tính là sửa prose, thứ phase này cấm |
| `honesty` — không suy ra số; nói không biết là câu trả lời hoàn chỉnh | `:155-160` | **core** | luật trung thực chung |
| `tools` — danh mục mười hai công cụ, bốn loại | `:169-222` | **core** | **Luật 2**: schema vẫn được chào đủ mọi Turn, nên catalog phải kể đủ. Gồm cả đoạn Signal Desk `:210-215` — 90 token, không đáng đảo một quyết định cache đã ghi và đã có test (`test_agent_prompt.py:82-95`) |
| `tools` — ranh giới `get_field` ↔ `run_study`, kỷ luật headline | `:203-208` | **body** | luật về hai tool của pack |
| `tools` — "Hỏi store trước khi hỏi web" | `:225-227` | **core** | **Luật 3**: đây là câu **gây ra** lời gọi tool domain. Ở body thì deadlock |
| `tools` — store có ba trục, web là nguồn duy nhất cho định tính, đọc field rồi tra web | `:229-239` | **body** | playbook sâu của pack |
| `tools` — không biết thì tra · nêu thời điểm đừng nêu nguồn · chỉ nhắc tên trang khi danh tính là nội dung · tra có mục đích · gộp lượt · lỗi tool là dữ kiện · số lượt có hạn · việc không cần tool · nói trước khi tra | `:241-282` | **core** | luật dùng tool chung, không domain. `:261-266` ("cùng một lượt gọi") có test pin nó phải ở `prefix()` (`test_agent_prompt.py:243-264`) — giữ nguyên |

Body dự kiến ≈ **900 token**; core còn ≈ **4.600** trên 5.498 đo ở phase 01.

### Prose của pack sống ở đâu

Ở `agent/domain/vn_equity.py`, **không** ở `sections.py`.

`sections.py` mở đầu bằng *"The canonical prose of the system prompt, and nothing
else… no imports of application code"* (`:1-19`). Giữ nguyên tính chất đó cho
**core**, và để prose của pack nằm cạnh pack là điều làm C8 hiển nhiên: pack thứ
hai mang prose thứ hai, và không ai phải sửa file prose của pack thứ nhất.

Chiều import: `agent/domain/vn_equity.py` → `agent/prompt.sections.PromptSection`
(một dataclass, `sections.py:32-38`). `sections.py` vẫn không import gì. Không có
vòng.

### `_assert_no_formatting_hole` phải chạy trên body

`contract.py:97-112` chạy nó trên `SECTIONS` **lúc import**, và đó là bằng chứng
đứng sau câu "không gì chèn được vào system prompt". Body pack đi vào cùng một
message với model, nên nó phải qua cùng một cổng. Gọi ở `domain/pack.py` lúc
validate — `pack.py` import `prompt.contract._assert_no_formatting_hole`, và
`contract.py` không import `domain`, nên không vòng.

Hàm hiện là private (`_`-prefix). Đổi tên thành công khai hay import private?
**Công khai hoá** (`assert_no_formatting_hole`), giữ alias cũ nếu có caller nào —
grep cho thấy đúng một caller (`contract.py:112`). Một hàm được hai module gọi mà
mang tên private là một lời nói dối rẻ tiền.

### `cache_key` nhận danh tính pack

`cache_key(model, tool_signature)` (`contract.py:162-172`) ghép `model |
PROMPT_VERSION | PROMPT_HASH | tool_signature`. Sau phase này hai Turn cùng model,
cùng tool signature, **khác pack** có prefix khác nhau — nên khoá phải mang
`pack.identity` (phase 02). Không có caller runtime nào (chỉ
`tests/test_agent_prompt.py:155-166`), nên thêm tham số **bắt buộc**, không thêm
tham số mặc định: một mặc định ở đây là một chỗ để C2 vô tình bỏ qua pack.

### `PROMPT_VERSION` → `3.0.0`

`sections.py:25-28` viết luật: major number di chuyển khi prompt mới *"không so
sánh được"* với bản cũ. Prompt hai tầng đúng là như vậy. Và luật chia số với C1
(`2.10.0`) là thứ giữ hai nhánh không cùng ghi một số — xem `plan.md`
§"Luật phối hợp hai worktree" điểm 2.

`tests/test_agent_prompt.py:67-79` pin số và giải thích *cái gì đổi*. Docstring
mới phải nói: prompt tách hai tầng, core luôn nạp, body theo pack — và **không**
xoá hai đoạn giải thích 2.9.0/2.8.0 đang có.

## Related Code Files

- Modify: `apps/api/src/agent/prompt/sections.py` — rút `:126-143`, `:203-208`,
  `:229-239` ra khỏi `honesty`/`tools`; `PROMPT_VERSION` `:29` → `3.0.0`
- Modify: `apps/api/src/agent/prompt/contract.py` — công khai hoá
  `_assert_no_formatting_hole` (`:97`), `cache_key` (`:162`) nhận danh tính pack;
  `render`/`prefix` **không đổi chữ ký**
- Modify: `apps/api/src/agent/prompt/__init__.py` — export tên mới
- Modify: `apps/api/src/agent/domain/vn_equity.py` — hai `PromptSection` body và
  `prompt_sections` của pack
- Modify: `apps/api/src/agent/domain/pack.py` — validate gọi
  `assert_no_formatting_hole` trên `prompt_sections`
- Modify: `apps/api/tests/test_agent_prompt.py` — version mới + docstring; test
  "không câu nào mất"; test "sàn an toàn ở core"; test brace mở rộng sang body.
  **Thêm ở cuối file**; hai test đang pin `prefix()` (`:82-95`, `:243-264`) phải
  xanh **nguyên văn**
- Modify: `apps/api/tests/test_agent_domain_pack.py` — body pack có mặt, không
  brace, không rỗng

## Implementation Steps

1. Chép nguyên văn ba khối prose sang `vn_equity.py` thành hai `PromptSection`
   (`store` — cơ chế đọc store; `playbook` — khi nào một con số, khi nào một bức
   tranh, và store có ba trục). **Copy trước, xoá sau**, để bước 3 so được.
2. Xoá đúng các dòng đó khỏi `sections.py`. Đọc lại hai section bị cắt từ đầu tới
   cuối: chỗ nối phải còn đọc trôi, không hụt chủ ngữ, không còn "Nhưng" mở đầu
   một đoạn mà vế trước đã đi mất (`:229` bắt đầu bằng "Nhưng store chỉ có ba
   trục" — nó đi cùng khối chuyển sang body, kiểm lại vế trước nó ở core còn tự
   đứng được).
3. Viết test "không câu nào mất": một danh sách các câu load-bearing (mọi câu mà
   test hiện tại đang pin, cộng câu mở của mỗi khối di chuyển) và assert mỗi câu
   có mặt **hoặc** ở `prefix()` **hoặc** ở body pack. Đây là lưới an toàn của cả
   phase; viết nó **trước** bước 4.
4. Viết test "sàn an toàn ở core": mỗi câu thuộc Luật 1 phải nằm trong `prefix()`
   — cụ thể là câu cấm chỉ thị hành động cho vị thế (`:94-97`), luật bảng điều
   kiện (`:110-115`), câu chống bịa (`:145-149`), và cổng `check_price_claim`
   (`:318-324`).
5. Công khai hoá `assert_no_formatting_hole`; gọi trong `pack.py`; mở rộng test
   brace (`test_agent_prompt.py:274-279`) sang `PACK.prompt_sections`.
6. Đổi `cache_key` + test của nó (`:155-166`).
7. Bump `PROMPT_VERSION` và viết lại docstring của test pin.
8. `make test` + `make lint`. Đọc **bằng mắt** prompt render ra (`python3 -c
   "print(render(RuntimeContext(today=date.today())))"`) một lần — không có test
   nào bắt được một đoạn văn cụt.

## Success Criteria

- [x] `prefix()` + body pack chứa **mọi** câu load-bearing của danh sách bước 3
- [x] Mọi câu thuộc Luật 1 nằm trong `prefix()`; test đỏ khi chuyển thử một câu
      trong số đó sang body (phép chứng minh bắt buộc)
- [x] `test_agent_prompt.py:38-46` (prefix byte-identical), `:82-95` (Signal Desk
      trong prefix), `:243-264` (gộp lượt trong prefix) xanh **nguyên văn**
- [x] Không brace ở cả core lẫn body
- [x] `render()` vẫn chỉ nhận `RuntimeContext`; `RuntimeContext` không thêm trường
- [x] `cache_key` mang danh tính pack; hai pack khác nhau cho hai khoá khác nhau
- [x] `PROMPT_VERSION == "3.0.0"`; `PROMPT_HASH` đổi
- [x] Core **5.449** token (`prefix()` nguyên khối), body **685**; tổng thân
      section **6.037** so tổng cũ 6.030 — lệch **+7**, trong ±20. Con số đầu là
      5.345/789; code review kéo đoạn *"Bạn KHÔNG đọc được…"* về core theo Luật 1
      (một tuyên bố không-năng-lực là luật an toàn), đổi 104 token.
      Gốc là 6.030/6.097 chứ không phải 5.498: phase 01 đã ghi chú rằng con số
      5.498 thiếu section thứ chín (`budget`, 532 token) của C1 — phần lệch duy nhất được phép là dòng tiêu đề của section
- [x] `git diff` của prose là **thuần di chuyển**: mọi dòng bị xoá ở `sections.py`
      xuất hiện nguyên văn ở `vn_equity.py`
- [x] `make test` + `make lint` xanh; năm cổng xanh

## Risk Assessment

**Rủi ro chính (xấu nhất của cả plan): một luật an toàn rơi xuống body.**
Hệ quả: mọi Turn không kích trigger chạy **không có** luật đó — và đó là nhóm Turn
trả lời bằng trí nhớ, tức nhóm rủi ro cao nhất. Không test hành vi nào bắt được;
nó chỉ hiện ra trong một câu trả lời tồi.
Tín hiệu: test bước 4 đỏ, hoặc `prefix()` không còn chứa một trong bốn câu.
Phản ứng đã quyết trước: test bước 4 là **gate cứng**, và cách sửa sai là chuyển
câu về core, **không** phải nới test.

**Rủi ro: prose cụt sau khi cắt.**
Tín hiệu: đoạn văn mở bằng liên từ mà vế trước đã đi mất.
Phản ứng: bước 2 đọc lại toàn văn hai section bị cắt; bước 8 đọc prompt render.
Không có test nào thay được hai bước đó, và plan nói vậy thay vì giả vờ có.

**Rủi ro: prose bị "cải thiện" trong lúc di chuyển.**
Tín hiệu: `git diff` không phải thuần di chuyển.
Phản ứng: revert đoạn đó về nguyên văn. Sửa prose là scope khác, và trộn nó vào
đây làm hồi quy chất lượng ở phase 06 không truy được nguyên nhân.

**Rủi ro: prompt ngắn đi mà body chưa được nạp (khoảng giữa hai phase).**
Sau phase 04 và trước phase 05, model **mất** playbook domain.
Tín hiệu: bất kỳ Turn thật nào chạy trên nhánh ở giữa hai phase.
Phản ứng đã quyết trước: hai phase merge cùng nhau, hoặc nhánh giữa **không được
deploy**. Ghi vào PR description, không dựa vào trí nhớ.

**Rủi ro: xung đột với C1 phase 04 trên cùng file.**
Tín hiệu: conflict ở `sections.py` và ở `test_agent_prompt.py:79`.
Phản ứng: luật đã ghi ở `plan.md` §"Luật phối hợp hai worktree" điểm 1–2 và 6 —
section của C1 là luật chung nên vào **core**, số version giải theo thứ tự merge.

## Rollback

`git revert` phase này hoàn nguyên prompt về một tầng: `sections.py` nhận lại ba
khối prose, `PROMPT_VERSION` về `2.9.0`, `cache_key` về hai tham số. Không có dữ
liệu nào ghi theo prompt version (không cột DB nào lưu nó — `grep -rn
"prompt_version" src` = 0), nên không có hàng nào trở thành không đọc được.

Nếu phase 05 đã merge, revert phase 04 **một mình** để lại một pack có body và một
loop đi tìm body — nên thứ tự revert bắt buộc là **05 trước, 04 sau**.

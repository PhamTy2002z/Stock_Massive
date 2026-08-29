---
phase: 5
title: "Dedup domain và giữ citation qua trim"
status: done
priority: P1
effort: "8h"
dependencies: [3]
---

# Phase 5: Dedup domain và giữ citation qua trim

## Overview

Hai việc cùng một chủ đề: một câu trả lời trích ba nguồn khác nhau chỉ có nghĩa
nếu ba nguồn đó **thật sự khác nhau**, và nếu chúng còn sống sót đến lúc model
viết câu cuối.

Đây cũng là phase mở khoá grader rủi ro nhất của phase 02 —
`uncited_external_number` — vì chỗ phân biệt số của store với số ngoài store
nằm ở đây.

## Requirements

- Functional: `display_results` gộp kết quả trùng và dedup theo domain, giữ bản
  tốt nhất thay vì bản đầu tiên.
- Functional: nguồn đang được trích dẫn **sống sót** qua thang trim history.
- Non-functional: luật `kind = external|store` không đổi ý nghĩa — nó là thứ cả
  ranh giới bằng chứng đứng trên (`messages.py:218-220`).
- Non-functional: không đổi số rung của thang trim, không đổi
  `keep_intact_turns = 2`.

## Architecture

### Dedup ở tầng trình bày, không ở tầng tool

`display_results()` (`messages.py:287-332`) đã cắt còn `MAX_DISPLAY_RESULTS = 10`
item và `DISPLAY_SNIPPET_CHARS = 280`. Dedup thuộc về đây, không thuộc
`tools/web.py`: tool trả về thứ nguồn trả về, còn việc hai truy vấn song song
cùng nhặt được một trang là việc của tầng gộp.

Luật gộp:

- Trùng **URL** sau chuẩn hoá (bỏ fragment, bỏ tracking param) → một item.
- Cùng **domain**, URL khác → giữ cả hai nhưng đánh dấu, để grader
  `distinct_domains` không đếm hai lần.
- Bản "tốt nhất" khi trùng: `rank` nhỏ hơn thắng; hoà thì `published_at` mới hơn
  thắng. Cả hai trường đến từ phase 03.

### Dedup ở đây sửa PHÉP ĐẾM, không sửa hành vi đọc

Tách hai claim mà bản đầu gộp làm một. Model đọc `result_text` nguyên văn qua
`shown_result`/`wrap_result`; `display_results` là *"the part of one tool's
result that may be put on a screen"* (`messages.py:287-296`) — projection cho
người đọc và cho event.

Nên dedup tại đây đổi **cách đếm** và **cách vẽ**. Model vẫn thấy hai bản của
cùng một URL và vẫn có thể fetch trùng. Hành vi chọn domain khác nhau thuộc câu
prompt của **phase 04**, không phải phase này.

Muốn model bớt fetch trùng thì dedup phải vào payload model đọc — một quyết định
khác, phải khai riêng, **không** làm ở đây.

### `_source_of()` KHÔNG phải phép lấy hostname

Bản đầu viết *"dùng lại `_source_of()` cho phần host"*. Sai:
`messages.py:557-563` loop qua `("url", "query")` và trả **giá trị argument
thô** — với `web_search` nó trả nguyên câu truy vấn.

Phép lấy hostname đang sống là `urlsplit(url).hostname` (`tools/web.py:469`,
`:503`), và trường `results[].source` **đã là hostname** do backend dựng sẵn.
Dedup domain dùng trường đó; đừng parse lại, và đừng gọi `_source_of()`.

### Citation sống sót qua trim

Thang trim đã có **bốn rung** (`messages.py:958-993`), không phải "summary 2 lần
rồi bó tay" như `docs/roadmap.md` mô tả ở C2:

1. nguyên vẹn · 2. gộp kết quả cũ · 3. bỏ Turn cũ · 4. gộp cả Turn được bảo vệ

Rung 2 gộp kết quả cũ thành
`f"called {call.name} with arguments {_compact(call.arguments)}"`
(`messages.py:910-911`). Nghĩa là **`url` của `fetch_url` và `query` của
`web_search` đã sống sót** — chúng nằm trong `arguments`.

Thứ **thật sự mất** là mảng URL/title của **kết quả** search. Bản đầu viết "giữ
định danh nguồn (url + title + domain)" — một nửa việc đó đã có sẵn, và làm lại
cả cụm chỉ phình token vô ích.

Cách sửa nhỏ nhất, thu hẹp về đúng phần thiếu: rung 2 giữ **danh sách URL của
kết quả** bị gộp, bỏ title và snippet. Model mất nội dung nhưng giữ được cái để
trỏ tới.

Đây không phải prune deterministic của C2 — đó là phase khác, chủ đề khác.

## Related Code Files

- Modify: `apps/api/src/agent/messages.py`
  - `display_results()` (`:287-332`) — dedup + gộp
  - thang trim (`:958-996`) rung 2 (`:910-911`) — giữ danh sách URL của kết quả
  - dedup dùng `results[].source` (đã là hostname, `tools/web.py:503`); **không** gọi `_source_of()` — nó trả argument thô, kể cả câu query
- Modify: `apps/api/tests/test_agent_messages.py` (tên thật xác nhận lúc làm)
- Modify: `apps/api/golden/grade.py` — bật `uncited_external_number` nếu phase 02 đã hoãn nó

## Implementation Steps

1. Viết chuẩn hoá URL (bỏ fragment, bỏ tracking param). Phần host lấy từ
   `results[].source` backend đã dựng — **không** gọi `_source_of()`.
2. Dedup trong `display_results()`. Test: hai truy vấn song song trả cùng một
   URL → một item; `rank` nhỏ hơn thắng.
3. Test: cùng domain khác URL → hai item, nhưng `distinct_domains` đếm một.
4. Sửa rung 2: giữ **danh sách URL của kết quả** khi gộp; `arguments` (url/query)
   đã sống sót sẵn, đừng làm lại.
5. Test replay: một transcript dài vượt context, nguồn được trích ở Turn đầu
   vẫn trỏ được ở Turn cuối.
6. Nếu `uncited_external_number` bị hoãn ở phase 02 — bật nó bây giờ, trên
   `kind = external|store` đã có sẵn.
7. `make golden-run` + `golden-grade`, so `distinct_domains` với phase 04.

## Success Criteria

- [ ] Hai truy vấn trả cùng URL → một item; bản `rank` nhỏ hơn thắng (test)
- [ ] Cùng domain khác URL → hai item, `distinct_domains` đếm một (test)
- [ ] Dedup dùng `results[].source`; `grep "_source_of" ` trong code dedup trả rỗng
- [ ] Rung 2 giữ danh sách URL kết quả; **không** thêm lại url/query đã có trong `arguments`
- [ ] Test `estimate_tokens`: fix rung 2 không làm token/Turn tăng quá mức đo được
- [ ] Test replay: nguồn trích ở Turn đầu còn trỏ được sau khi trim chạm rung 2
- [ ] Số rung thang trim **không đổi**; `keep_intact_turns` **không đổi**
- [ ] `kind = external|store` giữ nguyên nghĩa — test cũ xanh nguyên
- [ ] `uncited_external_number` chạy được, có case pass và case fail
- [ ] `distinct_domains` trên golden ≥ 3 cho họ tổng-hợp-nhiều-nguồn
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro: dedup quá tay, bóp số nguồn xuống dưới 3.**
Tín hiệu: `distinct_domains` **giảm** so phase 04.
Phản ứng: dedup theo URL là an toàn; dedup theo domain thì **không gộp item**,
chỉ ảnh hưởng cách đếm. Nếu số vẫn giảm, thứ sai là chuẩn hoá URL đang gộp hai
trang thật sự khác — nới chuẩn hoá, đừng nới grader.

**Rủi ro: bỏ tracking param làm hỏng URL của một số site.**
Tín hiệu: `fetch_url` trả 404 cho URL đã chuẩn hoá.
Phản ứng: chuẩn hoá **chỉ dùng để so trùng**, URL gửi đi vẫn là URL gốc. Đây là
ràng buộc thiết kế, không phải thứ chờ hỏng rồi sửa.

**Rủi ro: sửa rung 2 làm token/Turn tăng.**
Giữ danh sách URL tốn ~15–25 token mỗi kết quả bị gộp (chỉ URL, không title/snippet). Tín hiệu: token/Turn
trong artifact tăng rõ.
Phản ứng: giữ định danh **chỉ cho nguồn đã được trích ít nhất một lần**, không
cho mọi kết quả bị gộp. Cần một dấu vết "đã trích" — nếu chưa có, đó là công
việc thật của phase này chứ không phải một dòng thêm vào.

**Rủi ro: `uncited_external_number` vẫn không deterministic.**
Nếu tách số của store khỏi số ngoài store vẫn nhập nhằng sau khi có
`kind = external|store`, grader này **ra khỏi bộ** và tiêu chí "0 số không
citation" hạ xuống thành một phép đếm được báo cáo chứ không phải gate. Ghi
quyết định vào report; đừng để một grader luôn-pass ở lại trong bộ.

---
phase: 8
title: "Nghiệm thu so baseline"
status: done
priority: P1
effort: "6h"
dependencies: [2, 3, 4, 5, 6, 7]
---

# Phase 8: Nghiệm thu so baseline

## Overview

Chạy Golden Set trên code đã xong, so với artifact baseline của phase 01–02, và
**chốt ngưỡng** — thứ mọi phase trước cố tình không làm.

Đây cũng là chỗ trả lời câu hỏi C1 có tốt nghiệp hay không bằng số, và cập nhật
`docs/roadmap.md` đổi nhãn C1 từ **Target** sang **Current** nếu đạt.

## Requirements

- Functional: một lượt `golden-run` đầy đủ trên code cuối, artifact commit.
- Functional: bảng so sánh baseline ↔ kết quả, mọi chỉ số, kèm `n`.
- Functional: ngưỡng chốt cho từng grader, **đặt sau khi nhìn phân phối**.
- Functional: `docs/roadmap.md` C1 đổi nhãn nếu đạt; nếu không đạt, ghi rõ chỉ
  số nào trượt và nó thành phase kế.
- Non-functional: năm cổng xanh.

## Architecture

### Ngưỡng đặt sau, không đặt trước

Bộ eval trước chết một phần vì *"threshold và baseline mechanics tinh vi, nhưng
chúng đo bài thi lạc hậu"* (`260823-1744/plan.md:44-45`). Luật rút ra và giữ ở
plan này: **không ngưỡng nào trước khi phân phối sạch được nhìn.** Phase 02–07
chỉ đo và báo cáo; ngưỡng sinh ra ở đây, từ dữ liệu thật.

### Luật n ≥ 30 đã bị bỏ — vì sao

Bản đầu viết "n ≥ 30 thì gate, n < 30 thì tín hiệu". Số học phá luật đó: corpus
20 câu cho n = 20 ở **năm** trong sáu chỉ số; chỉ `parallel_rate` (đơn vị round,
≤ 4 round/Turn) chạm n ≥ 30. Áp luật đó nghĩa là C1 tốt nghiệp với đúng **một**
gate thật.

"Chạy thêm lượt" không cứu: `WebLane` cache search fresh 30 phút, URL fresh 24h
(`core/web_lane.py:19-22`) — lượt hai trong ngày đọc lại cache, mẫu tương quan,
n hiệu dụng vẫn ≈ 20.

**Luật thay thế:** chỉ số dạng "case đạt hay không đạt" gate theo **nhị thức
trên 20 case** — hợp lệ ở n = 20. Chỉ số phân phối liên tục là tín hiệu kèm
khoảng.

### Sáu chỉ số

| Chỉ số | Loại | Tiêu chí khởi điểm |
|---|---|---|
| `distinct_domains` | **gate** nhị thức | ≥ 18/20 case có ≥ 3 domain |
| `uncited_external_number` | **gate** nhị thức | ≥ 18/20 case không có số thiếu nguồn |
| `read_depth` | **gate** nhị thức | ≥ 15/20 case có `fetch_url` ≥ 2 |
| `parallel_rate` | **gate** | không giảm so artifact phase 02 |
| latency P50 | tín hiệu + khoảng | tăng > 20% phải giải thích |
| chi phí/Turn | tín hiệu + khoảng | dưới `TURN_COST_MICRO_USD` |

**Mọi delta so với artifact phase 02**, không so số store của phase 01 — khác
quần thể (organic vs web-first) và khác đơn vị (per-call vs per-Turn).

## Related Code Files

- Create: `plans/reports/phase-08-260829-c1-verification.md` — bảng so sánh + ngưỡng chốt + lý do
- Create: `apps/api/golden/artifacts/<ngày>-final.json` — artifact lượt cuối, commit
- Modify: `apps/api/golden/README.md` — ngưỡng chốt, một chỗ, là authority
- Modify: `docs/roadmap.md` — C1 đổi nhãn; cột "Sau" mang số thật đo được
- Modify: `CLAUDE.md` — §Quy ước nhận con số cuối; §Roadmap harness nhận trạng thái C1
- Modify: `plans/260829-1349-c1-search-and-evidence/plan.md` — trạng thái phase, kết quả

## Implementation Steps

1. Chạy `make golden-run` đầy đủ trên code cuối, trần chi tiêu tường minh.
2. `make golden-grade` trên artifact mới **và** trên artifact baseline, cùng một
   phiên bản grader. So hai kết quả của cùng một grader, không so hai grader.
3. Nếu grader đã đổi giữa phase 02 và bây giờ: chạy grader **mới** trên artifact
   **cũ**. Đó là phép so duy nhất có nghĩa.
4. Dựng bảng so sánh, mỗi chỉ số kèm `n`, kèm delta, kèm gate-hay-tín-hiệu.
5. Chốt ngưỡng cho từng grader từ phân phối. Ghi lý do từng ngưỡng.
6. Ghi ngưỡng vào `golden/README.md` — một chỗ, là authority. Không rải ngưỡng
   vào code grader.
7. Đổi nhãn C1 trong `docs/roadmap.md` nếu đạt. Nếu không đạt: ghi chỉ số trượt,
   giữ nhãn Target, và mở phase kế trong plan này thay vì tuyên bố xong.
8. Cập nhật `CLAUDE.md` với con số cuối.
9. Năm cổng.

## Success Criteria

- [ ] Artifact lượt cuối commit; `make golden-grade` chạy lại được trên nó cho kết quả **giống hệt** (deterministic)
- [ ] Bảng so sánh có đủ sáu chỉ số, mỗi chỉ số kèm `n` và nhãn gate/tín-hiệu
- [ ] Grader dùng để so là **cùng một phiên bản** trên cả hai artifact
- [ ] Mọi ngưỡng có lý do viết ra; không ngưỡng nào đặt trước phase này
- [ ] Gate là nhị thức per-case, không phải ngưỡng trên trung bình
- [ ] Không delta nào so với số store của phase 01
- [ ] Ngưỡng sống ở `golden/README.md`, không rải trong code grader
- [ ] `docs/roadmap.md` C1 mang nhãn đúng với kết quả thật, không phải nhãn mong muốn
- [ ] `CLAUDE.md` mang con số cuối
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro: một hoặc hai chỉ số không đạt và có áp lực gọi C1 là xong.**
Tín hiệu: đề xuất hạ ngưỡng ở chính phase này để vừa kết quả.
Phản ứng đã quyết trước: ngưỡng đặt từ **phân phối**, không từ kết quả mong
muốn — và nếu một chỉ số trượt, C1 giữ nhãn Target. Cửa vào C4 và Track S phụ
thuộc C1 thật sự đạt, nên một nhãn Current sai ở đây trả giá ở ba phase sau.
Đây là đúng cái sai đã giết bộ eval lần trước theo chiều ngược lại.

**Rủi ro: grader đổi giữa phase 02 và 08 làm hai artifact không so được.**
Tín hiệu: grader mới ném lỗi trên artifact cũ vì thiếu trường.
Phản ứng: grader phải chịu được artifact thiếu trường và trả `unavailable` cho
chỉ số đó, không crash. Chỉ số `unavailable` trên baseline nghĩa là **không có
baseline** cho nó — ghi vậy, đừng lấy 0 làm baseline.

**Rủi ro: lượt chạy đầy đủ vượt trần chi tiêu.**
Tín hiệu: lượt chạy dừng `incomplete`.
Phản ứng: chia thành nhiều lượt nhỏ, gộp artifact. **Không** nới trần và không
chấm một lượt `incomplete` — luật "không lượt xanh một nửa" của phase 02 áp ở
đây mạnh nhất.

**Rủi ro: phase 06 chưa xong.**
Progress event không đổi số nào của bốn grader. Phase 08 chạy được không có nó;
ghi rõ trong report rằng C1 tốt nghiệp thiếu mục progress, và mục đó thành plan
rời. Đừng chặn nghiệm thu vì một mục P2 không đo bằng grader nào.

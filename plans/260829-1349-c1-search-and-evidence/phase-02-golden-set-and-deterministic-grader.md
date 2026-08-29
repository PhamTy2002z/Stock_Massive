---
phase: 2
title: "Golden Set và grader deterministic"
status: pending
priority: P1
effort: "12h"
dependencies: [1]
---

# Phase 2: Golden Set và grader deterministic

## Overview

Dựng bộ đo tối thiểu — corpus câu hỏi web-first, một runner tự bắt trajectory,
và grader deterministic — đủ để C1 tốt nghiệp bằng số. Đây là **C4-lite**:
phần cơ chế của C4, không phải C4.

Phase này chạy trên shape **hiện tại** của `web_search`/`fetch_url`. Nó phải
sinh ra được một artifact "trước" trước khi phase 03 đổi shape, nếu không phase
08 không có gì để so.

## Requirements

- Functional: corpus 15–20 câu web-first, JSON, mỗi câu khai kỳ vọng **quan sát
  được** — không khai văn bản trả lời mong muốn.
- Functional: runner chạy corpus qua **entry point thật** của lane chat và ghi
  một artifact JSON gồm trajectory đầy đủ (mọi truy vấn, mọi URL trả về, mọi
  trang đọc, token, latency, chi phí).
- Functional: grader là hàm thuần trên artifact — không mạng, không DB, không
  model.
- Functional: hai `make` target — một chạy, một chấm. Chạy và chấm **tách rời**,
  vì chấm phải lặp lại được miễn phí trên một artifact cũ.
- Non-functional: **trần chi tiêu cứng**. Runner từ chối bắt đầu nếu không được
  đưa trần, và dừng khi chạm trần.
- Non-functional: **không có lượt chạy xanh một nửa.** Thiếu câu, chạm trần,
  grader không chạy được, hay lệch version → trạng thái nói rõ, không phải pass.

## Architecture

**Nơi đặt: `apps/api/golden/`.** Ngoài `src/`, nên production **không thể**
import — biến luật "runtime không bao giờ phụ thuộc eval" thành sự thật vật lý.
Chiều ngược lại được phép: golden đọc seam công khai của `src.agent`.

Không dùng lại tên `src/eval/`: nó chết hai lần (rip `1974c24` 2026-08-22, rồi
rip lại ở pivot 2026-08-25) và mang theo kỳ vọng về một bộ máy lớn hơn nhiều so
với thứ cần ở đây.

```
apps/api/golden/
  web_first.json      corpus: câu hỏi + kỳ vọng quan sát được
  run.py              chạy corpus qua TurnService thật -> artifact
  grade.py            hàm thuần: artifact -> findings
  artifacts/          lượt chạy, gitignore trừ baseline được chốt
```

### Runner ĐỌC store, không bọc `LLMClient`

Bản đầu viết *"bọc `LLMClient` thật để ghi token và giá, quan sát tool call tại
chỗ"*. Red-team chỉ ra hai lý do việc đó vừa thừa vừa hỏng:

**Thừa** — mọi thứ cần đã được runtime ghi:

| Cần | Đọc ở đâu |
|---|---|
| Trajectory: truy vấn, URL, domain, snippet | `agent_tool_call.result->>'text'` — chuỗi JSON chứa nguyên payload gồm mảng `results`. Đo: **77/81** dòng parse được |
| Token và giá thật | `llm_call_usage` — có `owner_id`, `input_tokens`, `output_tokens`, `reserved_micro_usd` |
| Round, số nguồn | `agent_tool_call` + payload `tool.call` |

**Hỏng** — `TurnService` không phải seam tự đủ. Ctor đòi `loop_factory`
(`turns.py:354-366`), factory thật là closure trên nội bộ `AgentLoop(client,
config, slots, checkpoint, publisher, trace)` (`service.py:121-131`), và
`build_alpha_desk(config=…, store=…)` (`service.py:97-101`) **không nhận tham số
client** — client dựng bên trong. Bọc client nghĩa là chép lại composition root
(đúng như `tests/e2e/server.py:236-253` đang làm), tức coupling vào ctor của
`AgentLoop` và vỡ đúng ở phase 04.

→ `run.py` gọi `build_alpha_desk(config=…)` **nguyên trạng**, chạy corpus, rồi
**đọc lại** store để dựng artifact. Zero coupling nội bộ.

### Ba trần per-user chặn lượt chạy — phải giải ở đây

`core/llm/config.py:218-222`:

| Trần | Giá trị | Hệ quả |
|---|---|---|
| `turn_starts_per_day` | **20** | Corpus 20 câu chạm **đúng** trần. Một lần thử lại là vỡ. **Đây là trần binding, không phải tiền** |
| `active_turns_per_user` | **1** | Runner **phải tuần tự** |
| `daily_usd` | 3,0 | Mềm hơn: một Turn đo được $0,021 → 20 câu ≈ $0,4–1,2 |
| `rolling_30d_usd` | 15,0 | Cả chiến dịch nhiều lượt phải nằm dưới |

→ Runner chạy dưới **identity riêng** (user golden), và phase này quyết cách nới
trần cho đúng identity đó — override config hay nhiều identity. Ghi id vào
artifact.

Identity riêng giải luôn một vấn đề thứ hai: golden ghi thật vào `agent_turn`/
`agent_tool_call`/`llm_call_usage`, tức **làm bẩn chính baseline nó phục vụ**.
Mọi SQL baseline phải `WHERE user_id != <golden>`.

### Web sống phá tính so được giữa hai artifact

Bộ eval cũ có luật *"no live request in baseline, comparison"* và plan này đảo
nó. Artifact phase 02 và phase 08 cách nhau nhiều tuần; `WebLane` cache search
fresh **30 phút**, URL fresh **24h** (`core/web_lane.py:19-22`). Delta phase 08
= Δcode + Δweb + Δsampling, không tách được trên n=20.

→ **Record/replay tại seam `WebLane.read`.** Lượt đầu ghi payload lane vào
artifact; lượt sau phát lại. LLM vẫn sống (ta đang đo model chọn gì), web đóng
băng (ta không đo Internet trôi).

### "Cited" phải có định nghĩa quan sát được TRƯỚC khi viết grader

Prompt **cấm** dẫn nguồn trong văn bản. Định nghĩa dùng ở đây:

> Một số ngoài store được coi là **có nguồn** khi nó xuất hiện trong một trang
> Turn đó đã đọc, hoặc trong một kết quả store của chính Turn đó.

Tập nguồn = `display_results()` của Turn — thứ `SourceList` vẽ cạnh câu trả lời.
Viết định nghĩa này vào `golden/README.md` **trước** dòng grader đầu tiên.

**Bốn grader, tất cả deterministic:**

| Grader | Chấm gì | Nguồn dữ kiện trong artifact |
|---|---|---|
| `distinct_domains` | số domain khác nhau được trích/câu | hostname của URL đã đọc và đã trích |
| `uncited_external_number` | số ngoài store xuất hiện trong câu trả lời mà không nguồn | đối chiếu số trong answer với số trong text đã nạp |
| `read_depth` | `fetch_url`/Turn | đếm call |
| `parallel_rate` | tỉ lệ round có > 1 `web_search` | group theo round |

Grader **không rẽ theo id câu hỏi.** Dữ liệu của case chọn check nào áp dụng;
logic grader chung cho mọi case. Đây là điều bộ cũ làm đúng và phải giữ.

**Corpus khai kỳ vọng quan sát được, không khai câu trả lời.** Ví dụ shape:

```json
{
  "id": "wf-004",
  "question": "...",
  "family": "conflicting_sources",
  "expect": {
    "min_distinct_domains": 3,
    "must_cite_external_numbers": true,
    "forbidden": ["chỉ thị hành động cho vị thế cụ thể"]
  },
  "why_a_fluent_answer_fails": "..."
}
```

Mỗi case **phải** ghi `why_a_fluent_answer_fails`. Case nào không viết được câu
đó thì nó không phân biệt được gì và không vào corpus.

## Related Code Files

- Create: `apps/api/golden/web_first.json`
- Create: `apps/api/golden/run.py`
- Create: `apps/api/golden/grade.py`
- Create: `apps/api/golden/README.md` — luật anti-repeat, một trang
- Create: `apps/api/tests/golden/test_grade.py` — test cho chính grader, trên artifact fixture nhỏ
- Modify: `apps/api/Makefile` — thêm `golden-run` và `golden-grade` (vào chỗ năm target `eval-*` vừa gỡ ở phase 01)
- Modify: `apps/api/.gitignore` hoặc `.gitignore` gốc — `golden/artifacts/` trừ baseline đã chốt

## Implementation Steps

1. Đọc `plans/260823-1744-investment-intelligence-eval-replay-harness/plan.md`
   §"Why the previous harness failed" và §"Anti-repeat contract" trước khi viết
   dòng nào. Chép luật anti-repeat vào `golden/README.md` bằng lời của phase này.
2. Viết `grade.py` **trước** `run.py`. Grader là hàm thuần nên test được ngay
   trên artifact fixture viết tay, không cần chạy Turn thật.
3. Viết `test_grade.py`: mỗi grader có case pass và case fail rõ ràng.
4. Viết `run.py`: gọi entry point thật của lane chat, bọc `LLMClient` thật để
   ghi token và giá, quan sát tool call tại chỗ. Trần chi tiêu là **tham số bắt
   buộc**, không có mặc định.
5. Viết corpus 15–20 câu. Bốn họ, cân nhau: *fact có as-of* · *tổng hợp nhiều
   nguồn* · *nguồn mâu thuẫn / thiếu* · *đối kháng (nội dung web có injection,
   số bịa)*. Mỗi case ghi `why_a_fluent_answer_fails`.
6. Thêm `golden-run` và `golden-grade` vào `Makefile`, cả hai đòi tham số tường
   minh như `backfill-daily` đang làm (`Makefile:66-68`).
7. Chạy một lượt thật với trần nhỏ → artifact "trước". Chốt nó thành baseline,
   commit.
8. Ghi phân phối quan sát được vào `plans/reports/`. **Không đặt ngưỡng ở phase
   này** — ngưỡng chốt ở phase 08.

## Success Criteria

- [ ] `make golden-grade` chạy được trên một artifact có sẵn, **không** chạm mạng, **không** gọi model
- [ ] `make golden-run` từ chối chạy khi không có trần chi tiêu
- [ ] Lượt chạy chạm trần kết thúc ở trạng thái `incomplete`, không phải `pass`
- [ ] `grep -rn "golden" apps/api/src/` trả **rỗng** — production không import golden
- [ ] Corpus có 15–20 case, mọi case có `why_a_fluent_answer_fails` không rỗng
- [ ] Bốn họ đều có ≥ 3 case
- [ ] `test_grade.py` có case pass và case fail cho từng grader trong bốn grader
- [ ] Artifact baseline commit vào repo, phase 08 trỏ được tới nó
- [ ] Report ghi phân phối; **không** ngưỡng nào được đặt ở phase này
- [ ] `run.py` gọi `build_alpha_desk(config=…)` nguyên trạng — **không** dựng `AgentLoop` thủ công, **không** bọc `LLMClient`
- [ ] Định nghĩa "cited" viết trong `golden/README.md` **trước** grader đầu tiên
- [ ] Runner chạy dưới identity riêng; id ghi vào artifact
- [ ] Lượt 20 câu chạy hết **không** chạm `turn_starts_per_day`
- [ ] Mọi SQL baseline lọc bỏ traffic golden
- [ ] Record/replay `WebLane.read` hoạt động: chạy lại cùng artifact cho **cùng** payload web
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro lớn nhất: lặp lại cái chết của bộ cũ — chấm một contract runtime không
phát ra.**
Tín hiệu: một grader luôn trả `unavailable` hoặc luôn pass bất kể input.
Phản ứng: grader đó ra khỏi bộ ngay, không "để đó chờ phase sau". Luật cứng:
**không grader nào cho một trường chưa tồn tại trong artifact thật.** Ba grader
`distinct_domains` / `read_depth` / `parallel_rate` đọc được ngay hôm nay;
`uncited_external_number` là cái rủi ro nhất — nếu nó không tách được số ngoài
store khỏi số của store một cách deterministic, nó **hoãn sang phase 05** (chỗ
`display_results` phân biệt `kind = external|store`), không được ép chạy sớm.

**Rủi ro: corpus tự viết đo sai thứ cần đo.**
Không có người hiểu thị trường VN chấm (roadmap câu hỏi mở #4). Giảm thiểu:
`why_a_fluent_answer_fails` bắt mỗi case tự chứng minh nó phân biệt được gì.
Đây là nợ ghi rõ ở `plan.md` §Câu hỏi chưa giải quyết, không phải nợ đã trả.

**Rủi ro: chi phí lượt chạy vượt envelope.**
Tín hiệu: trần chạm trước khi hết corpus. Phản ứng: giảm số case của lượt chạy,
**không** nới trần. Trần là tham số bắt buộc chính vì lý do này.

**Rủi ro: `run.py` phụ thuộc chi tiết nội bộ của `AgentLoop` rồi vỡ ở phase 04.**
Tín hiệu: phase 04 đổi `MAX_EXTERNAL_TOOL_CALLS` làm `run.py` đỏ.
Phản ứng: `run.py` chỉ được gọi qua seam công khai (`TurnService`), không đọc
hằng số của `loop.py`. Nếu nó cần một hằng số, nó **đọc từ runtime lúc chạy** và
ghi vào artifact như một dữ kiện của lượt chạy — đó cũng là thứ phase 08 cần để
biết hai artifact có so được với nhau không.

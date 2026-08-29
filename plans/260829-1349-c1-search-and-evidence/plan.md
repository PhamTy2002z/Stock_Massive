---
title: "C1 Search And Evidence"
description: "Lane chat tìm rộng hơn, đọc nhiều hơn, và mọi số ngoài store có citation truy được — cộng bộ đo tối thiểu để phase này tốt nghiệp bằng số thay vì bằng cảm giác."
status: done
priority: P1
effort: "8 phase"
tags: [harness, web, search, evidence, security, measurement]
created: 2026-08-29
relatedTo: [260827-2325-evidence-led-chat-surface]
blocks: [260827-2325-evidence-led-chat-surface]
---

# Plan: C1 — Search & tổng hợp có bằng chứng

Roadmap authority: `docs/roadmap.md` §3 / **C1**. Đây là cạnh duy nhất rời khỏi
C0 trong đồ thị phụ thuộc §6, và là cửa vào C4 — thứ gác toàn bộ Track S trả phí.

Contract mở phase chốt với user 2026-08-29 (brainstorm, không có report rời):

- **Outcome.** 2–3 truy vấn web song song một round, 3–4 trang đọc có dedup
  domain, mọi số ngoài store có citation, progress event mang nội dung thật,
  và lớp bảo mật thứ 5 (quét pattern injection, fail-open). Kèm **C4-lite**:
  Golden Set web-first + grader deterministic đủ để C1 tốt nghiệp bằng số.
- **Non-goals.** LLM judge · CI fail-closed · prune/cache (C2) · research tier
  selector UI (`260827-2325` phase 09, chạy **sau** plan này) · không đụng
  bundle `signals`/`studies`.

## Bảy dữ kiện roadmap và CLAUDE.md ghi sai

Đo lại trên code và store thật 2026-08-29, **trước** khi viết một dòng plan nào.
Ba trong bảy cái đảo hẳn hình dạng của phase. Ghi ra đây vì bộ eval trước chết
đúng vì lý do này — nó chấm một contract mà runtime không còn phát ra.

| # | Roadmap / CLAUDE.md viết | Đo lại |
|---|---|---|
| 1 | *"1 truy vấn mỗi round"* | **Song song đã chạy.** Hậu rip-out: 2/10 round có ≥2 `web_search`. Cả lịch sử: 21/43 round (48,8%), tối đa 5 truy vấn một round. `executor.py:268-278` `asyncio.gather`, `plan_segments()` `:156-180` gom `READ + PARALLEL_SAFE`, `web_search` khai `PARALLEL_SAFE` (`tools/web.py:339`), trần fan-out `MAX_EXTERNAL_CALLS_PER_ROUND = 8` (`executor.py:86`). **Cơ chế không thiếu gì.** |
| 2 | *"ưu tiên nguồn whitelist"* | Repo có **denylist**, không có whitelist: `web_domain_denylist` (`core/config.py:153`), áp ở `tools/web.py:174-176`. "Ưu tiên whitelist" không có chỗ bám. |
| 3 | *"`progress.py` dựng được, phát ra chưa đủ"* | File **không tồn tại**. `EventType` có đúng **8** member (`events.py:74-88`), không member nào là progress. Dựng mới. |
| 4 | *"web hiển thị timeline gập"* (việc phải làm) | `components/alpha/message/reasoning-timeline.tsx` **đã có, 622 dòng**, gập được, gộp theo round, spinner sống tới call cuối. Việc là **nạp nội dung tốt hơn**, không phải dựng surface. |
| 5 | *"`PROMPT_VERSION` 2.6.0"* (CLAUDE.md) | **2.9.0** (`prompt/sections.py:29`). |
| 6 | *"snippet 700 ký tự, không xếp hạng"* | `published_at` **đã có** (`tools/web.py:503`). Thiếu đúng hai thứ: `rank` và `domain_trust`. |
| 7 | *"`make eval*` đã gỡ"* (CLAUDE.md) | **Năm target còn sống** và cả năm hỏng: `eval-validate/smoke/run/compare/gate` (`Makefile:79-95`) gọi `python -m src.eval`, mà `src/eval/` chỉ còn `__pycache__`. |

Hệ quả: **nút thắt của C1 không phải concurrency.** Nó là hai thứ khác — ngân
sách và thói quen đọc.

## Nút thắt thật, đo được

| Đo | Số | Nghĩa |
|---|---|---|
| `MAX_EXTERNAL_TOOL_CALLS` | **6**/Turn (`loop.py:293`) | Mục tiêu 2–3 search + 3–4 fetch = **5–7 call**. Trần 6 cắt ngang giữa mục tiêu. Đây là ngân sách **tiền** trên envelope $45/tháng, không phải con số tuỳ ý. |
| `fetch_url` hậu rip-out | **3 call** (so 8 `web_search`) | Model **tìm mà gần như không đọc**. Khoảng cách lớn nhất so mục tiêu "3–4 trang". Snippet 700 ký tự đủ để nó thấy đã đủ. |
| `MAX_RESULTS` | 5 (`tools/web.py:64`) | Trần kết quả mỗi truy vấn. |
| `MAX_PAGE_TEXT_CHARS` | 20.000 (`tools/web.py:71`), cắt ở `:134` | Cắt **20k đầu trang**, không theo câu hỏi. |

## "Citation" ở sản phẩm này nằm ở UI, không nằm trong văn bản

Đây là đính chính quan trọng nhất của cả plan, tìm ra ở red-team và xác minh
trực tiếp. Prompt 2.9.0 **cố ý cấm** dẫn nguồn trong câu trả lời:

> *"Tra rồi thì nêu thời điểm, **đừng nêu nguồn**. Giao diện đã hiển thị các
> trang bạn vừa tra ngay cạnh câu trả lời […] nên một dòng dẫn nguồn trong văn
> bản chỉ là bản sao xấu hơn của thứ người đọc đã thấy."* (`prompt/sections.py:246-248`)
>
> *"**Không viết phần dẫn nguồn.** Không dòng bắt đầu bằng Nguồn, không đường
> dẫn dán vào văn bản, không chú thích đánh số […] Việc đó là của giao diện."*
> (`:381-383`)

Nên câu *"mỗi con số ngoài store có citation"* của roadmap **không** có nghĩa
là chú thích trong văn bản. Nó có nghĩa: **danh sách nguồn hiển thị cạnh câu
trả lời phải phủ được số mà câu trả lời dùng.**

Đó là một hợp đồng **đã tồn tại và quan sát được**, không phải thứ phải phát
minh:

```
display_results()          →  ToolCall.results  →  SourceList
messages.py:287-332           types.ts:81          source-list.tsx
```

Grader chấm trên chuỗi đó. Nếu không chốt điều này trước khi viết grader, C1
lặp lại **đúng** nguyên nhân số 1 giết bộ eval cũ — chấm một contract runtime
không phát ra (`260823-1744/plan.md:37-40`).

## Baseline: cái gì đọc được từ lịch sử, cái gì không

Bản đầu của plan này viết *"`agent_tool_call.result` không có mảng `results`"*.
**Sai.** Cột `result` có ba khoá `{text, chars, dispatched}`, nhưng `text` là
**chuỗi JSON chứa nguyên payload**, gồm cả mảng `results`. Đo lại:
**77/81 dòng** `web_search` parse ra được URL. Trim ở `SEARCH_RESULT_CHARS = 8_000`
(`tools/web.py:76`) và payload 5 kết quả ≈ 4–4,5k ký tự nên gần như không bị cắt.

| Chỉ số | Đọc được từ lịch sử? |
|---|---|
| Domain một truy vấn **trả về** | **Được** — parse `result->>'text'` |
| `read_depth`, `parallel_rate`, latency | Được |
| Chi phí thật | Được — bảng `llm_call_usage` |
| Domain **được phủ** trong danh sách nguồn của câu trả lời | Được, nhưng **n = 10** |

Nên lý do duy nhất còn đứng là **mẫu quá nhỏ**: lane chat hậu rip-out chỉ có
**10 round** gọi `web_search` và **3** `fetch_url`. Không phải vì thiếu dữ liệu
persist.

Hệ quả cho thiết kế runner: nó **không cần** tự bắt trajectory. Nó đọc chính
những chỗ runtime đã ghi — `agent_tool_call.result` và `llm_call_usage` — nên
không phải đục vào nội bộ `AgentLoop`. Xem phase 02.

## Trần ngân sách chặn lượt chạy trước khi trần golden kịp có tác dụng

Ba trần per-user đang sống (`core/llm/config.py:218-222`):

| Trần | Giá trị | Hệ quả cho một lượt golden 20 câu |
|---|---|---|
| `turn_starts_per_day` | **20** | Corpus 20 câu chạm **đúng** trần. Một lần thử lại là vỡ. |
| `active_turns_per_user` | **1** | Runner **phải tuần tự**, không song song hoá câu hỏi được |
| `daily_usd` | **3,0** | Ràng buộc mềm hơn: một Turn đo được $0,021, nên 20 câu ≈ $0,4–1,2 |
| `rolling_30d_usd` | 15,0 | Cả chiến dịch nhiều lượt phải nằm dưới đây |

`turn_starts_per_day = 20` là trần binding, không phải tiền. Phase 02 **phải**
giải nó (identity riêng cho runner + override), nếu không mọi lượt chạy kết
thúc `incomplete` và luật "không chấm lượt xanh một nửa" khoá cứng cả plan.

## C4-lite — học từ hai lần chết

`plans/260823-1744-investment-intelligence-eval-replay-harness/` là bản ghi thất
bại đầy đủ. Bộ eval chết **hai lần**: rip 2026-08-22 (commit `1974c24`), dựng
lại theo plan đó, rồi rip lại ở pivot harness-first 2026-08-25. Bốn nguyên nhân
gốc nó tự ghi (`plan.md:31-46`), và C4-lite né từng cái:

| Nguyên nhân bộ cũ chết | C4-lite né thế nào |
|---|---|
| Chấm contract runtime không còn phát ra | **Chỉ chấm thứ chính plan này làm runtime phát ra.** Không grader nào cho một trường chưa tồn tại. Phase 02 chạy trên shape **hiện tại**, các phase sau mới làm số tốt lên. |
| Fixture 160k–190k dòng, buộc identity vào schema store | Corpus là **một file JSON ~15–20 câu**. Không snapshot store, không freeze row. |
| Chèn state eval vào persistence + admission production | **Không bảng DB, không migration, không lane budget, không hook lifecycle.** Artifact là file JSON cục bộ. |
| Ngưỡng tinh vi trên bài thi lạc hậu | **Không ngưỡng trước khi có baseline.** Phase 02 chỉ đo; ngưỡng chốt ở phase 08 sau khi nhìn phân phối. |

**Nơi đặt: `apps/api/golden/`, không phải `src/eval/`.** Hai lý do: cái tên đó
đã chết hai lần, và nằm ngoài `src/` thì production **không thể** import nó —
biến luật *"runtime không bao giờ phụ thuộc eval"* thành sự thật vật lý chứ
không phải một lời hứa. Chiều ngược lại vẫn được: golden đọc seam công khai của
`src.agent`.

## Ranh giới freeze — plan này CẦN amendment

Bản đầu viết *"surface mới chỉ có `golden/*` và `progress.py`"*. **Sai.** Bốn
file các phase khai sẽ sửa nằm trong bảng surface của
`260829-0010-composer-attachments` — plan đó **đã đóng 10/10**, và tiền lệ
price-basis là *plan xong thì surface đóng; file ngoài bảng cần amendment mới,
không phải một dòng nới*.

`src/agent/*` chưa bao giờ freeze nên phần harness tự do. Plan này **không
đụng** `src/stocks/*` và không đụng bundle `signals`/`studies`.

**Bảng amendment C1 — phase 01 ghi vào CLAUDE.md trước dòng code đầu tiên:**

| Surface | Giới hạn |
|---|---|
| `apps/api/golden/*` (mới) | corpus + runner + grader; **không** importer nào từ `src/` |
| `apps/api/Makefile` | gỡ năm target `eval-*` chết, thêm `golden-run`/`golden-grade`; không đụng target nào đang chạy |
| `src/agent/tools/web.py` | `rank` · trích đoạn theo câu hỏi; **không** đổi SSRF, denylist, `MAX_REDIRECTS` |
| `src/agent/{loop,guardrails}.py` | đúng hai con số đi cùng nhau; không đổi `MAX_TOOL_ROUNDS` |
| `src/agent/{messages,untrusted}.py` + `threat_patterns.py` (mới) | dedup hiển thị · lớp quét fail-open; **không** đổi `wrap_result` |
| `src/agent/prompt/sections.py` | một section + bump version |
| `apps/web/src/lib/alpha-desk/types.ts` · `components/alpha/message/reasoning-timeline.tsx` · `hooks/use-live-turn.ts` | **chỉ** vẽ dữ liệu `tool.call` đã có trên dây; không đụng `SignalDeskToggle` |
| `docs/roadmap.md` · `CLAUDE.md` | §1, §3 C1/C2 — **không** đụng Track S |

Bảng này **là** ranh giới. File ngoài bảng cần amendment mới.

## Số học gate — vì sao bỏ luật n ≥ 30

Với corpus 20 câu, một lượt cho `distinct_domains` n=20 · `read_depth` n=20 ·
latency n=20 · chi phí n=20 · `uncited_external_number` n=20. **Chỉ**
`parallel_rate` (đơn vị round, ≤4 round/Turn) chạm n ≥ 30. Một luật "n<30 thì
không gate" biến năm trong sáu tiêu chí thành phi-gate, tức C1 tốt nghiệp bằng
cảm giác.

"Chạy thêm lượt" không cứu: `WebLane` cache search fresh **30 phút**, URL fresh
**24h** (`core/web_lane.py:19-22`), nên lượt hai trong ngày đọc lại cache — mẫu
tương quan, n hiệu dụng vẫn ≈ 20.

**Luật thay thế:** tiêu chí dạng "0 vi phạm" hoặc "≥ ngưỡng" gate theo **case
pass/fail nhị thức trên 20 case**. Đó là gate hợp lệ ở n=20. Chỉ số dạng phân
phối liên tục (latency P50, chi phí) đọc là **tín hiệu kèm khoảng**, và nói vậy.

## Luật phải giữ

- **Event mới khai tường minh durable hay live-only.** Mọi `*.delta` phải có
  `*.ended` làm biên replay. Nhớ vào checkpoint **trước** khi announce, và thêm
  khoá vào `snapshot_from_draft` — quên là reconnect mất event. (Luật ghim ở
  `260827-2325/plan.md` §Nguyên tắc; `events.py:431-464` là chỗ subscribe chụp
  snapshot.)
- **Quét injection fail-open**: gắn cờ, không chặn. Hermes tách hai lớp và chỉ
  lớp bọc là cứng (`docs/hermes/hermes-web-security-260820-2352.md:96-109`).
- **Frames không bao giờ vào message gửi model.**
- Nới trần external call **phải kèm phép đo chi phí** trên envelope $45/tháng.

## Phases

| # | Phase | Vùng | Dep | Trạng thái |
|---|---|---|---|---|
| 01 | [Baseline đo được và dọn cổng chết](./phase-01-baseline-and-dead-gates.md) | docs + build | — | **done** |
| 02 | [Golden Set và grader deterministic](./phase-02-golden-set-and-deterministic-grader.md) | golden | 01 | **done** |
| 03 | [Kết quả tìm mang rank và độ tin cậy domain](./phase-03-search-results-carry-rank-and-domain-trust.md) | api | 02 | **done** — `domain_trust` chốt là không làm |
| 04 | [Ngân sách external call và tìm song song](./phase-04-external-call-budget-and-parallel-search.md) | api | 02, 03 | **done** — trần 6 → 7 |
| 05 | [Dedup domain và giữ citation qua trim](./phase-05-dedup-domains-and-keep-citations-through-trim.md) | api | 03 | **done** — dedup là phạm vi **Turn**, không phải phạm vi call |
| 06 | [Rail hiện số nguồn và domain đã có trên dây](./phase-06-progress-events-carry-what-the-turn-is-doing.md) | **web-only** | 03 | **done** — chỗ trống thật là branch row của một round |
| 07 | [Quét pattern injection trên text đã nạp](./phase-07-scan-fetched-text-for-injection-patterns.md) | api | — | **done** — chốt đường **C**, không phải A hay B |
| 08 | [Nghiệm thu so baseline](./phase-08-verification-against-the-baseline.md) | cả hai | 02–07 | **done** — 3/4 gate đạt, **C1 không tốt nghiệp** |

Phase 07 không phụ thuộc phase nào. Quyết định chỗ chứa cờ đã chốt 2026-08-29 và
**không phải A cũng không phải B**: `TurnToolCall.as_wire()` đã được ghi vào
`agent_message.content` JSONB (`turns.py:231`), nên một khoá `scan` ở đó là
durable, mở lại thread vẫn thấy, `golden/run.py` đọc lại được — mà không
migration, không cột trên bảng nóng, không backup DB, và không đụng bất biến của
`agent_tool_call.result`.

**Một tiền đề nữa của phase 05 bị đảo, cùng cách sáu tiền đề đầu bị đảo.**
Architecture của nó đặt dedup trong `display_results()` — một hàm **per-call** —
trong khi Implementation Step 2 đòi test "hai truy vấn song song trả cùng một
URL → một item", thứ chỉ đúng nếu dedup ở **phạm vi Turn**. Đo trên tape thật
trước khi viết dòng đầu tiên: **0/53** call search trả URL trùng trong cùng một
payload, còn **21/223** URL (9,4%) xuất hiện ở nhiều call. Nên dedup per-call là
code không bao giờ chạy — đúng thứ luật "không để lại grader luôn-pass" cấm. Đã
làm theo phép đo: một `set` per-Turn (`_TurnState.shown_sources`) truyền vào
`display_results(seen=...)`.

Phase 06 đã co từ 8h/api+web xuống 3h/web-only sau red-team: query nguyên văn
**đã hiện** trên rail qua trường `summary`, và số nguồn + domain **đã có** trong
payload `tool.call` — chỉ chưa được vẽ.

Red-team đầy đủ: `plans/reports/red-team-260829-1411-c1-search-and-evidence.md`
— hai reviewer, 20 finding, sáu tiền đề của bản đầu bị đảo và đã sửa tại chỗ.

## Kết quả nghiệm thu — 2026-08-29

> **Kế nhiệm, 2026-08-29 muộn hơn cùng ngày:** C1 **đã tốt nghiệp `Current`** qua
> `plans/260829-1945-c1-evidence-graduation/`. Kết luận bên dưới **đúng tại thời
> điểm chạy** và giữ nguyên, không viết lại. Hai điều plan kế nhiệm đo lại được:
> (1) *"grader thấy được số suy diễn"* — việc plan này giao lại — là **ngõ cụt đã
> chứng minh**, tiêu chí citation chuyển sang **C4** dưới dạng claim-provenance
> contract; (2) con số *"grader sai 5/5"* đúng ra là **4/5** — `wf-012` là finding
> thật. Chi tiết:
> `plans/260829-1945-c1-evidence-graduation/reports/graduation-report.md`.

**Tám phase thi công xong. C1 KHÔNG tốt nghiệp; nhãn roadmap giữ `Target`.**
Báo cáo đầy đủ: `plans/reports/phase-08-260829-c1-verification.md`.
Ngưỡng chốt: `apps/api/golden/README.md`.

| Chỉ số | phase 02 | after 03-04 | cuối 05-07 | Ngưỡng | |
|---|---|---|---|---|---|
| `distinct_domains` (bar từng case) | 19/20 | 19/20 | **19/20** | ≥ 18/20 | đạt |
| `read_depth` (bar từng case) | 11/20 | 19/20 | **18/20** | ≥ 16/20 | đạt |
| `read_depth` ≥ 2 phẳng | 6/20 | 16/20 | **14/20** | — | dưới khởi điểm 15/20 |
| `parallel_rate` | 34% | 63% | **63%** | ≥ 50% | đạt |
| latency P50 | 51,0 s | 63,0 s | **52,4 s** | tín hiệu | đạt |
| chi phí/Turn P50 | 45.484 | 60.107 | **58.222** µUSD | < 500.000 | đạt |
| `uncited_external_number` | 11/16 | 12/16 | **11/16** | **không gate** | công cụ hỏng |

**Vì sao không tốt nghiệp.** Tiêu chí *"số ngoài store không citation = 0"* mất
công cụ đo: grader sai **5/5** — mọi case nó đánh trượt là câu trả lời trung thực,
số bị gắn cờ đều **suy ra** từ số đã có nguồn (hiệu hai nguồn · phần trăm · đổi
đơn vị `tỷ`→`nghìn tỷ`). Phase 05 đã ghi trước điều kiện gỡ nó khỏi bộ gate; điều
kiện xảy ra, nặng hơn dự đoán. Không hạ ngưỡng để vừa kết quả.

**Confound phải đọc kèm mọi delta.** Lượt cuối ở `PROMPT_VERSION` 3.0.0, lượt
trước 2.10.0 — chênh lệch của **C5**, không phải phase 05–07. Số duy nhất quy chắc
chắn cho C1: **nguồn/lượt tìm 5,13 → 3,96 (−22,8%)** ở `MAX_RESULTS = 5` không
đổi, `distinct_domains` giữ 19/20.

**Hai ngưỡng của plan này phát biểu sai mẫu số** (tìm ra khi đọc corpus, trước khi
chấm): `uncited_external_number` có `decided = 16` chứ không 20 → "≥ 18/20" bất khả
về số học; `distinct_domains` "≥ 3 domain" chỉ mô tả nửa corpus (corpus khai bar 2
cho mười case, 3 cho mười case).

## Success Criteria

Gate nhị thức trên 20 case (xem §Số học gate). Mọi delta so với **artifact
phase 02**, không so số store của phase 01 — hai bên khác quần thể và khác đơn vị.

Soát 2026-08-29 lúc đóng plan. **Tám trên mười đạt; hai gate trượt, và plan đóng
với chúng trượt** — nhãn C1 giữ `Target`, không hạ ngưỡng để vừa kết quả.

- [x] **Gate** — ≥ 18/20 case có ≥ 3 domain khác nhau — **19/20**
- [ ] **Gate** — ≥ 18/20 case mọi số ngoài store phủ được — **11/16. TRƯỢT, và công
      cụ đo không hợp lệ**: grader sai 5/5 (số suy diễn — hiệu hai nguồn, phần trăm,
      đổi đơn vị). Mẫu số cũng sai: `decided = 16`, nên "18/20" bất khả về số học
- [ ] **Gate** — ≥ 15/20 case có `fetch_url` ≥ 2 — **14/20. TRƯỢT**, thiếu một case,
      và giảm 2 so lượt trước. Dao động thật ở n = 20, nhưng chưa chứng minh được
- [x] **Gate** — `parallel_rate` không giảm so artifact phase 02 — **34% → 63%**
- [x] **Tín hiệu** — latency P50 kèm khoảng — **52,4 s [17,9–81,6]**, −16,9% so lượt trước
- [x] **Tín hiệu** — chi phí/Turn kèm khoảng — **58.222 µUSD [9.978–128.188]**, trần 500.000
- [x] Grader chạy bằng `make golden-grade`, chạy lại cho kết quả **giống hệt** (kiểm bằng `shasum` hai lượt)
- [x] Không grader nào luôn-pass hoặc luôn-`unavailable` — `uncited_external_number`
      có case pass và case fail; `distinct_domains`/`read_depth` quyết trên cả 20.
      **Một ngoại lệ khai rõ:** `parallel_rate` trả `passed=None` cho mọi case vì
      gate của nó là **so giữa hai artifact**, không phải verdict per-case; nó vẫn
      tính giá trị thật cho từng case. Ngưỡng ≥ 50% ở `golden/README.md` do **người
      đọc** áp, không có code nào enforce — đúng luật "không rải ngưỡng vào grader"
- [x] Bảng amendment C1 trong CLAUDE.md khớp file thật — soát lại toàn bộ
      `git status`; bổ sung `.gitignore` (phase 01 sửa mà bảng chưa ghi),
      `events.py`, `source-pill.tsx`, và nới hai dòng `loop.py`/`executor.py`.
      `src/agent/{domain,evidence}/` cùng worktree là của **C5**, không phải C1
- [x] Năm cổng xanh — `make test` **1676 pass** · `make lint` · `pnpm type-check`/`lint`/`test` **824 pass**/`build`

Ngưỡng khởi điểm 18/20 và 15/20 đã được thay bằng ngưỡng chốt từ phân phối thật
(`apps/api/golden/README.md`). Hai gate trượt ở trên đo theo **phát biểu gốc của
plan**, không theo ngưỡng mới — đọc theo ngưỡng mới thì `read_depth` đạt (18/20 so
≥ 16/20 trên bar của từng case), còn `uncited_external_number` không có ngưỡng vì
không gate được.

## Câu hỏi chưa giải quyết

1. **`domain_trust` lấy từ đâu.** Repo chỉ có denylist. Ba lựa chọn ở phase 03:
   bảng tĩnh nhỏ do repo sở hữu · điểm từ Tavily nếu API trả · chỉ dùng
   `published_at` + rank và bỏ hẳn trust. Chốt lúc làm, sau khi đọc response
   thật của Tavily.
2. **Trần external call mới là bao nhiêu.** Là công thức chi phí, chưa là hằng
   số. Chốt ở phase 04 sau khi phase 02 đo giá một Turn web-first.
3. **Ai sở hữu và chấm Golden Set.** Roadmap câu hỏi mở #4 — cần người hiểu thị
   trường VN. C4-lite tự viết corpus đầu; đây là nợ ghi rõ, không phải đã trả.

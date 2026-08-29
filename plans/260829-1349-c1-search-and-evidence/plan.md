---
title: "C1 Search And Evidence"
description: "Lane chat tìm rộng hơn, đọc nhiều hơn, và mọi số ngoài store có citation truy được — cộng bộ đo tối thiểu để phase này tốt nghiệp bằng số thay vì bằng cảm giác."
status: pending
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
| 01 | [Baseline đo được và dọn cổng chết](./phase-01-baseline-and-dead-gates.md) | docs + build | — | pending |
| 02 | [Golden Set và grader deterministic](./phase-02-golden-set-and-deterministic-grader.md) | golden | 01 | pending |
| 03 | [Kết quả tìm mang rank và độ tin cậy domain](./phase-03-search-results-carry-rank-and-domain-trust.md) | api | 02 | pending |
| 04 | [Ngân sách external call và tìm song song](./phase-04-external-call-budget-and-parallel-search.md) | api | 02, 03 | pending |
| 05 | [Dedup domain và giữ citation qua trim](./phase-05-dedup-domains-and-keep-citations-through-trim.md) | api | 03 | pending |
| 06 | [Rail hiện số nguồn và domain đã có trên dây](./phase-06-progress-events-carry-what-the-turn-is-doing.md) | **web-only** | 03 | pending |
| 07 | [Quét pattern injection trên text đã nạp](./phase-07-scan-fetched-text-for-injection-patterns.md) | api | — | pending |
| 08 | [Nghiệm thu so baseline](./phase-08-verification-against-the-baseline.md) | cả hai | 02–07 | pending |

Phase 07 không phụ thuộc phase nào — chạy song song được từ đầu, nhưng **chờ
một quyết định của user** về chỗ chứa cờ (cột mới + backup, hay live-only).

Phase 06 đã co từ 8h/api+web xuống 3h/web-only sau red-team: query nguyên văn
**đã hiện** trên rail qua trường `summary`, và số nguồn + domain **đã có** trong
payload `tool.call` — chỉ chưa được vẽ.

Red-team đầy đủ: `plans/reports/red-team-260829-1411-c1-search-and-evidence.md`
— hai reviewer, 20 finding, sáu tiền đề của bản đầu bị đảo và đã sửa tại chỗ.

## Success Criteria

Gate nhị thức trên 20 case (xem §Số học gate). Mọi delta so với **artifact
phase 02**, không so số store của phase 01 — hai bên khác quần thể và khác đơn vị.

- [ ] **Gate** — ≥ 18/20 case có ≥ 3 domain khác nhau trong danh sách nguồn cạnh câu trả lời
- [ ] **Gate** — ≥ 18/20 case: mọi số ngoài store trong câu trả lời phủ được bởi một trang đã đọc hoặc một kết quả store của chính Turn đó
- [ ] **Gate** — ≥ 15/20 case có `fetch_url` ≥ 2
- [ ] **Gate** — `parallel_rate` không giảm so artifact phase 02
- [ ] **Tín hiệu** — latency P50 kèm khoảng; tăng > 20% thì phải giải thích, không tự động trượt
- [ ] **Tín hiệu** — chi phí/Turn kèm khoảng, dưới `TURN_COST_MICRO_USD`
- [ ] Grader chạy bằng một `make` target, JSON là authority, chạy lại cho kết quả **giống hệt**
- [ ] Không phase nào để lại grader luôn-pass hoặc luôn-`unavailable`
- [ ] Bảng amendment C1 trong CLAUDE.md khớp tứ hợp file thật của tám phase
- [ ] Năm cổng xanh: `make test` + `make lint` (apps/api) · `pnpm type-check`/`lint`/`test`/`build` (apps/web)

Ngưỡng 18/20 và 15/20 là **giá trị khởi điểm**, chốt lại ở phase 08 trên phân
phối thật — xem luật "không ngưỡng trước khi nhìn phân phối".

## Câu hỏi chưa giải quyết

1. **`domain_trust` lấy từ đâu.** Repo chỉ có denylist. Ba lựa chọn ở phase 03:
   bảng tĩnh nhỏ do repo sở hữu · điểm từ Tavily nếu API trả · chỉ dùng
   `published_at` + rank và bỏ hẳn trust. Chốt lúc làm, sau khi đọc response
   thật của Tavily.
2. **Trần external call mới là bao nhiêu.** Là công thức chi phí, chưa là hằng
   số. Chốt ở phase 04 sau khi phase 02 đo giá một Turn web-first.
3. **Ai sở hữu và chấm Golden Set.** Roadmap câu hỏi mở #4 — cần người hiểu thị
   trường VN. C4-lite tự viết corpus đầu; đây là nợ ghi rõ, không phải đã trả.

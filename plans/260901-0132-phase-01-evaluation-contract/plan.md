---
plan: 260901-0132-phase-01-evaluation-contract
title: "Phase 1 — Evaluation contract"
status: done — baseline chạy 2026-09-01, gate đỏ có chủ sở hữu
roadmap: "docs/roadmap.md §10 Phase 1"
branch: feat/phase-01-evaluation-contract
---

# Phase 1 — Evaluation contract

Roadmap authority: [`docs/roadmap.md`](../../docs/roadmap.md) §2 (hợp đồng sự
thật), §3 (rubric), §10 Phase 1, §9 (nguyên tắc thi công).

## Outcome

§2 và §3 trở thành **corpus + grader chạy được bằng một lệnh**, nhiều trial là
mặc định, artifact in pass/fail theo từng dimension. Không dựng framework mới:
mở rộng `apps/api/golden/` (`run.py` + `grade.py` + corpus + tape) đúng như
roadmap yêu cầu.

Phase này **không thêm tính năng user-facing**. Nó thêm khả năng biết mình sai
ở đâu — và một baseline đỏ ở lần chạy đầu là kết quả đúng, không phải lỗi.

## Non-goals

- Không dựng lại `apps/api/eval` (đã xoá hai lần).
- Không thêm bảng, migration, budget lane, lifecycle hook nào cho eval.
- Không sửa runtime để làm grader xanh. Grader đo cái runtime **đang** phát.
- Không khoá threshold quality/latency/cost trước khi có distribution nhiều
  trial kèm confidence interval.
- Không dựng lại evidence-witness grader suy diễn số — đã đo và bác bỏ
  (`plans/260829-1945-c1-evidence-graduation/reports/phase-01-260829-derivation-depth.md`).

## Preflight §9

### 1. Mỗi gate đã có lệnh/metric chạy được chưa?

Có. Gate của phase là một lệnh:

```bash
make golden-release CEILING_USD=<x> TRIALS=<n>
```

Nó chạy corpus → judge → grade → gate, in một bảng pass/fail theo dimension kèm
Wilson 95% CI, và exit code là verdict: `0` xanh, `1` một hard dimension dưới
100% hoặc run `incomplete`, `2` artifact không chấm được.

### 2. Thứ Phase 0 để lại — verify trong code thật

Đã đọc code ngày 2026-09-01, không tin nhãn Done:

| Giả định | Thực tế đo được |
|---|---|
| Tool catalog đúng 5 tool | Đúng — `toolsets.py` `web` + `memory` = `web_search, fetch_url, session_search, remember_fact, recall_facts` |
| Golden runner còn chạy | Đúng — `pytest tests/golden` 46 passed |
| Có artifact baseline dùng được | **Sai.** Artifact mới nhất `web-first-v1-final.json` có `run_study`, `render_signal_desk`, `check_price_claim` trong `tool_calls` → nó **trước teardown Phase 0**. Không tồn tại baseline hậu-teardown |
| `sources[].published_at` có dữ liệu | **Sai.** 0/226 source có `published_at`. Tavily `search_depth=basic`, topic mặc định không trả `published_date` (`tools/web.py:666` đọc đúng field, provider không gửi) |
| Retrieval time đo được | Đúng nhưng chưa vào artifact — `WebLane.read` trả `fetched_at`, tape của `ReplayLane` đã ghi, run.py chưa gắn xuống từng source |
| `cost` có bốn token counter | Đúng trong code hiện tại; artifact cũ chỉ có hai → thêm một bằng chứng nữa rằng artifact cũ đã lỗi thời |

Hệ quả nằm trong plan: **P1.2 phải chạy một record run mới** trước khi bất kỳ
grader nào được tuyên bố là đọc field có thật, và luật của `golden/README.md`
("no grader for a field that is not in a real artifact") được giữ nguyên bằng
cách nghiệm thu từng dimension trên artifact tươi, không trên artifact cũ.

### 3. Unknown

Discoverable → đã scout trong lúc plan (§Scout dưới). Không discoverable → ghi
thành named assumption kèm fallback:

| Assumption | Nếu sai thì làm gì |
|---|---|
| **A1.** Tavily không trả publication time cho phần lớn trang tin VN | Fallback đã thiết kế sẵn: `temporal_validity` đọc **map ngày do corpus đóng băng** trước, field provider sau. Map được curate **sau** record run từ chính tape, không bịa trước |
| **A2.** Một trial full corpus tốn ~1,3–3 USD (ngoại suy từ 20 case = 1,29 USD) | `--ceiling-usd` bắt buộc và dừng đúng ngưỡng; run chạm trần settle `incomplete`, không phải pass thấp |
| **A3.** Model gateway phục vụ được judge pass với JSON strict | Parse fail → `judge.status = "unavailable"`, không bao giờ thành điểm ngầm; gate không phụ thuộc judge |
| **A4.** Trial 2..N replay được tape của trial 1 trong cùng một lần chạy | Miss tape bất kỳ → run `incomplete` (cơ chế đã có trong `ReplayLane`) |
| **A5.** `multi_source_label` và `refusal_policy` đọc được từ `answer_text` bằng marker do corpus khai báo | Marker là **dữ liệu trong corpus**, không phải hằng số trong grader; sai marker sửa corpus, không sửa grader |

### 4. Đường lùi

Mọi thứ nằm trong `apps/api/golden/` + `tests/golden/` + `Makefile`, không có
migration, không có bảng, không đụng `src/`. Dừng giữa phase = `git revert` một
nhánh; runtime production không đổi một dòng. Corpus cũ `web_first.json` và ba
make target cũ giữ nguyên chữ ký, nên đường đo cũ vẫn chạy trong lúc đường mới
xây dở.

## Scout nguồn pattern §7 (bắt buộc trước khi thiết kế grader mới)

Học shape, không port code, không thêm dependency.

| Nguồn | Học được | Áp vào đâu |
|---|---|---|
| **Inspect AI** (UK AISI) | Tách task/solver/scorer; nhiều scorer trên một task rồi *reduce*; epochs = multi-trial mặc định; metric mặc định báo kèm **stderr**; eval log ghi spec (task, model, config) + từng sample đọc lại được | `run.py` là solver, `grade.py` là scorer — cấu trúc **đã đúng**, giữ nguyên. Thêm: `--trials` (epochs), reducer theo dimension (hard = AND mọi trial, soft = median), Wilson CI thay cho stderr trần trụi (đúng hơn cho tỷ lệ nhị thức n nhỏ), provenance block đủ để đọc lại một run cũ |
| **promptfoo** | Gate sống ở **tầng CI/runner**, không nằm trong scorer: scorer in JSON, một lớp mỏng so ngưỡng rồi quyết exit code; artifact JSON/JUnit lưu theo run | `grade.py` giữ nguyên tính chất "báo cáo, không gác cổng" — `gate.py` mới là nơi duy nhất có ngưỡng, và ngưỡng soft bắt đầu rỗng cho tới khi có distribution |
| **Braintrust** | Versioning corpus/experiment để so run này với baseline | `corpus_sha256` đã có; thêm `tape_sha256`, `tool_catalog`, `trials`, `judge` vào provenance để hai artifact chỉ khác nhau ở đúng thứ đã đổi |

Ràng buộc roadmap "không dựng framework mới" giữ nguyên: không có class Task,
không có registry scorer, không có plugin. Bốn file thành sáu.

## Kiến trúc

```text
golden/release.json      corpus release: 11 family, mỗi case đóng băng
    │                    query · as_of · expect · traps · ground truth
    ▼
golden/run.py            solver — chạy corpus × trials qua lane thật
    │                    trial 1 record tape, trial 2..N replay tape
    ▼  golden.artifact@2
golden/judge.py          rubric pass — model độc lập, context sạch
    │                    ghi cases[].judge, không chấm số backend kiểm được
    ▼
golden/grade.py          scorer — pure function của artifact
    │                    12 dimension: 8 mới + 4 signal cũ
    ▼
golden/gate.py           nơi DUY NHẤT có ngưỡng; Wilson CI; exit code
    ▼
golden/release.py        một lệnh: run → judge → grade → gate
```

Quy tắc giữ nguyên từ `golden/README.md`, không cái nào được nới:

1. Grader không bao giờ rẽ nhánh theo case id — dữ liệu của case quyết định.
2. Không grader cho field không có trong artifact thật.
3. Không ngưỡng trước khi có distribution.
4. Grading không chạm network/DB/model. Judge là **pass riêng**, chạy trước
   grade và ghi kết quả vào artifact, nên `grade.py` vẫn pure.
5. Run nửa xanh là `incomplete`, không phải pass thấp.

## Mười hai dimension

Hard = roadmap §10 P1 liệt kê đích danh. Reported = có verdict nhưng chưa gác
cổng cho tới khi baseline nói được ngưỡng.

| # | Dimension | Loại | Đọc field nào |
|---|---|---|---|
| 1 | `settlement` | hard | `turn.status`, `turn.terminal_reason`, `answer_text` |
| 2 | `citation_url` | hard | URL trong `answer_text` vs `sources[].url` |
| 3 | `evidence_identity` | hard | `sources[].url/domain/title`, `from_call` phải giải được về một call có thật |
| 4 | `material_claim` | hard | `ground_truth.values` đóng băng vs số trong `answer_text` |
| 5 | `temporal_validity` | hard | `as_of` của case vs ngày đóng băng của nguồn + `retrieved_at` |
| 6 | `refusal_policy` | hard | `expect.must_refuse` + marker do corpus khai |
| 7 | `budget` | hard | `cost`, `run.ceiling_micro_usd`, `runtime_constants` |
| 8 | `multi_source_label` | reported | `expect.min_distinct_domains`, marker "một nguồn" |
| 9 | `distinct_domains` | reported | giữ nguyên grader cũ |
| 10 | `read_depth` | reported | giữ nguyên grader cũ |
| 11 | `parallel_rate` | reported | giữ nguyên grader cũ |
| 12 | `uncited_external_number` | reported, **không bao giờ gác cổng** | giữ nguyên; lý do đã đo, ghi trong `README.md` |

Rubric judge (§3) chấm năm trục — synthesis, cấu trúc theo intent, chất lượng
phản biện, uncertainty, decision utility — thang 1–5, và **bị cấm** chấm số mà
backend kiểm được. Điểm judge là reported cho tới khi có baseline.

## Kết quả nghiệm thu

1. `make golden-release CEILING_USD=… TRIALS=…` chạy trọn corpus, in bảng
   pass/fail theo dimension kèm CI, exit code phản ánh verdict.
2. Mỗi hard dimension có verdict trên **mọi** case của corpus release — không
   `unavailable`, không field không tồn tại.
3. Artifact ghi đủ provenance: code SHA, prompt version, tool catalog, model,
   config constants, corpus sha, tape sha, trial count, judge model.
4. `pytest tests/golden` xanh, có test cho từng dimension mới trên fixture.
5. Baseline nhiều trial có Wilson CI; threshold soft **chưa** khoá, và file
   ngưỡng nói rõ vì sao chưa.
6. Không import nào từ `src/` vào golden ngoài các seam công khai đã dùng; không
   file nào của `src/` bị sửa.

## Phase

| # | Việc | File |
|---|---|---|
| 1 | Corpus release + hợp đồng dimension | `phase-01-release-corpus.md` |
| 2 | Multi-trial runner + provenance + retrieved_at | `phase-02-runner-trials-provenance.md` |
| 3 | Tám grader deterministic | `phase-03-deterministic-graders.md` |
| 4 | Rubric judge pass | `phase-04-rubric-judge.md` |
| 5 | Một lệnh, gate, Wilson CI | `phase-05-one-command-gate.md` |
| 6 | Record run + baseline + curate ngày | `phase-06-baseline-run.md` |

Phase 6 tiêu tiền thật và cần env của máy chủ (proxy 8317, Tavily, Postgres
Docker qua LAN IP) — nó dừng chờ product owner chốt ceiling, đúng luật cửa một
chiều về chi phí.

## Kết quả

Baseline đầu tiên: `plans/reports/phase-01-260901-release-baseline.md`.
Một lệnh chạy trọn 40 case × 3 trial trong ~12 phút (concurrency 6), chi $3,47,
in bảng 12 dimension kèm Wilson CI, exit code 1.

Gate của phase — một lệnh, pass/fail theo dimension, nửa xanh là incomplete —
**đạt**. Yêu cầu hard 100% chưa đạt và đó là số đo: 3/7 xanh, 2 đỏ (ranh giới
advice, evidence identity), 2 BLIND (ground truth và publication time chưa tồn
tại). Cả bốn đều có chủ sở hữu ở Phase 3 và Phase 6, đúng thứ tự roadmap.

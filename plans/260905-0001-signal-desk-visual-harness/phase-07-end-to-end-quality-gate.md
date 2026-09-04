---
phase: 7
title: "End To End Quality Gate"
status: todo
priority: P1
effort: "12h"
dependencies: [6]
---

# Phase 7: End To End Quality Gate

## Context Links

- `apps/api/golden/README.md` — sở hữu dimension, threshold, và vì sao host khác container
- `apps/api/golden/release.json` — corpus: `families`, `dimensions` (có `class`), `markers`
- `apps/api/golden/graders.py::DIMENSIONS` (hard) và `grade.py::LEGACY_GRADERS` (soft)
- `apps/api/golden/gate.py` — đọc `class` từ report; hard fix ở 100%, không tunable
- `apps/api/golden/thresholds.json` — "No threshold before a distribution", soft đều `null`
- Toàn bộ Findings và fixture của Phase 2–6

## Overview

Tốt nghiệp cả đường đi, không phải từng mảnh: prompt → durable Turn → research
web/Vnstock bounded → ledger đã validate → visual part persisted → Flint compile
chính thức → render pane phải. Phase này hấp thu luôn paid run còn lại của Phase
6 evidence engine để **một** corpus đo đồng thời chất lượng answer, độ thật của
evidence, kỷ luật tool và tính hợp lệ của visual.

## Mở rộng harness hiện có, không dựng cái thứ hai

Đọc `golden/` trước khi lên kế hoạch đổi nó:

| Việc | Cách rẻ nhất trong kiến trúc hiện tại |
|---|---|
| Thêm case | Thêm family vào `release.json`; runner đọc corpus, không hard-code |
| Thêm dimension | Một grader function + tên vào `graders.py::DIMENSIONS` + entry `dimensions` trong `release.json` với `class` |
| Bật/tắt gate | **Không sửa `gate.py`**: nó đọc `class` từ report và fix hard ở 100% |
| Threshold soft mới | **Không set**: `thresholds.json` giữ `null` cho tới khi có distribution nhiều trial |
| Kiểm Flint compile | Một vitest đọc artifact JSON, đúng cách Phase 2 đã compile |
| Chạy paid | `make golden-release CEILING_USD=… TRIALS=…` hiện có |

Nên cắt khỏi bản trước: `golden/visual_grade.py`, `apps/web/src/lib/flint/grade-visuals.ts`
(một trong hai là đủ, và web là nơi Flint chạy được), sửa `gate.py`, sửa
`Makefile`.

**Cắt một hard gate không chạy được.** "Call intent: 100% external call map tới
một evidence need đang mở tại thời điểm admission" không đo được: `gaps` chỉ tồn
tại *sau* research pass, còn call xảy ra *trước* nó. CLAUDE.md: một gate không
quy về được command chạy được hay ngưỡng số là một roadmap bug — nên nó bị bỏ,
không phải viết grader đoán. Kỷ luật tool vẫn được đo bằng duplicate dispatch,
bound tuyệt đối và no-progress ladder.

## Release Corpus

Giữ nguyên 40 case evidence hiện có làm mẫu số. Thêm một slice visual tối thiểu
12 case như family mới trong `release.json`:

| Family | Case tối thiểu | Nguồn/output bắt buộc |
|---|---:|---|
| Price/volume history | 3 | Vnstock OHLCV + Flint chart có evidence |
| Event explanation | 3 | Narrative primary/web + OHLCV khi cần |
| Multi-symbol comparison | 2 | Cùng unit/interval → multi-series line, hoặc refusal trung thực |
| Source/provider conflict | 1 | Cả hai identity hiện; không âm thầm chọn một |
| No-data/stale/ambiguous | 2 | Text refusal, không có visual part |
| Chat-mode control | 1 | Chỉ text/evidence; zero visual work |

Giá trị live được freeze vào artifact/tape để grade lại không tốn tiền. Test
dùng output thật đã ghi; không fabricate market response để thoả gate.

## Hard Gates

| Dimension | Gate |
|---|---|
| Terminality | 100% Turn settle với typed status và stop reason. |
| Absolute bounds | 0 Turn vượt lane: 10 tool round, 20 external call, 1.800s; cap per-round của executor cũng giữ. |
| Duplicate dispatch | 0 exact call fingerprint thành công bị dispatch upstream hai lần trong một Turn. |
| No progress | 100% fixture trả kết quả giống nhau đi tới ladder `TurnGuardrails` và dừng với reason của nó. |
| Truth contract | Hard dimension fabrication/disclosure/temporal/multi-source giữ đúng giá trị đã lock (fabrication 0%). |
| Visual grounding | 100% số trong visual persisted map về field của một tool call accepted + evidence ID + unit + `as_of`. |
| Flint validity | 100% visual part persisted pass validate/compile của package Flint đã pin, offline. |
| Flint integrity | 0 file Flint source bị sửa/vendor; 0 ECharts option được persist hay post-process. |
| Mode isolation | 100% chat control không có key `visual`, không compile Flint, không nhận market toolset. |
| Internal-only data | 100% case profile không internal đều ẩn/refuse capability Vnstock. |
| Replay | Cùng artifact persisted cho cùng assembly sau refresh/restart, với 0 model/tool call. |

Soft metric — useful call rate, latency, cost, số evidence gap, chất lượng chọn
shape visual — báo ở dạng distribution trước. Chỉ được đặt threshold sau khi có
baseline, và không bao giờ override ceiling ở trên. Đây là chính sách đã có
trong `thresholds.json`, không phải quy tắc mới của phase này.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Modify | `apps/api/golden/release.json` | Thêm family Signal Desk + dimension mới kèm `class`; không bỏ case cũ. |
| Modify | `apps/api/golden/run.py` | Ghi mode, stage history, visual part, lane ceiling thật theo case. |
| Modify | `apps/api/golden/graders.py` | Grader cho visual grounding, mode isolation, replay. |
| Modify | `apps/api/golden/grade.py` | Gắn dimension mới vào `DIMENSIONS`/report. |
| Create | `apps/web/src/lib/flint/grade-artifact.test.ts` | Compile mọi visual part trong artifact bằng package đã pin, rồi bỏ output. |
| Modify | `apps/api/tests/golden/test_release_corpus.py` | Validate source rights marker, mode, expected visual/refusal, bounded symbol/range. |
| Modify | `apps/api/tests/golden/test_grade.py` | Fixture cho dimension mới. |
| Create | `apps/api/tests/test_agent_fault_injection.py` | Cancel, deadline, provider fail, permission denied, mọi ceiling. |
| Create | `plans/260905-0001-signal-desk-visual-harness/reports/graduation-report.md` | Command, version, distribution, verdict, giới hạn đã biết. |
| Modify sau khi pass | `docs/roadmap.md`, `CLAUDE.md` | Ghi capability là current và các gate đã đo. |

Không sửa `gate.py`, `Makefile`, `thresholds.json`.

## Implementation Steps

1. Validate corpus offline trước: mọi case mới có source rights marker, mode,
   expected visual/refusal và bounded symbol/time range.
2. Mở rộng artifact với field mode/stage/visual; giữ parse ngược cho artifact cũ
   ở dạng `N/A`, không bao giờ pass giả.
3. Thêm fixture offline adversarial: exact duplicate thành công, repeated
   failure, malformed draft, permission denied, deadline, restart, visual hỏng.
4. Viết grader grounding + vitest compile; verify chúng **fail** khi cố ý đổi
   một value hoặc một evidence ID.
5. Chạy hết test free, rồi API suite, compileall, web gate. Sửa defect sản
   phẩm; không bao giờ nới gate hay loại case fail.
6. Một canary internal read-only để chắc provider/version/profile Vnstock còn
   dùng được, trong request budget tường minh.
7. Chạy `golden-release` một lần với `CEILING_USD` và trial count do owner đưa.
   Trial đầu ghi tape web/market; trial sau replay.
8. Grade offline tới khi deterministic. Nếu chất lượng fail thì sửa rồi xin
   quyết định paid run mới, không âm thầm tiêu tiếp.
9. Viết graduation report: mọi hard gate, distribution soft, version package/dữ
   liệu, và ranh giới license production còn treo.
10. Chỉ khi mọi hard gate pass mới update roadmap status và đóng plan Signal Desk
    compiler cũ là superseded.

## Test Scenario Matrix

| Scenario | Assertions |
|---|---|
| FPT historical trend | OHLCV bounded, source/time/unit, Flint chart hợp lệ. |
| Giảm ba phiên liên tiếp | Narrative primary + market data; claim phân biệt fact/inference. |
| Intraday vs daily bar | Semantics quan sát tường minh; không có timestamp "live" giả. |
| So sánh hai mã | Cùng unit/interval → multi-series, lệch → refusal; không trộn thang. |
| KBS/VCI conflict | Conflict hiện trong ledger và metadata visual. |
| Symbol sai / cuối tuần | Không retry storm; refusal no-data, không visual part. |
| Web đủ, không cần structured | Không gọi Vnstock chỉ vì capability tồn tại. |
| Cần structured, web không đủ | Gọi Vnstock; agent không bịa và không dừng sớm. |
| Exact repeat thành công | Một dispatch provider, result reuse, Turn hữu hạn. |
| Search đổi query, evidence không đổi | Ladder guardrail dừng với reason của nó. |
| 21 external call đề xuất | Tối đa 20; phần dư refuse/settle; reason ghi lại. |
| Round thứ 11 | Không bao giờ dispatch. |
| Hết 1.800s | Deadline settlement, call còn treo được resolve. |
| Cancel giữa parallel batch | Không orphan; thứ tự ổn định; terminal cancel. |
| Visual không dựng được | Không có key visual; text sống nguyên. |
| Refresh/restart | Cùng message/visual, zero công việc trùng. |
| Chat mode control | Không market bundle, không visual, chất lượng text hiện có. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_guardrails.py tests/test_agent_market_data.py tests/test_agent_visual.py tests/test_agent_fault_injection.py tests/golden
cd apps/api && pytest -q tests/
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test
pnpm --dir apps/web build
git diff --check
rg -n 'src\.(stocks|studies)|Study DSL|Board DSL|widget catalog|global watchlist' apps/api/src apps/web/src
```

Paid gate, chỉ chạy với ceiling owner đưa:

```bash
make -C apps/api golden-release CEILING_USD=<amount> TRIALS=<n>
make -C apps/api golden-release CEILING_USD=1 RELEASE_ARGS="--grade-only golden/artifacts/<file>.json"
```

## Success Criteria

- [ ] Mọi hard gate pass trên một artifact hợp nhất; không case nào bị skip để
      làm đẹp mẫu số.
- [ ] Yêu cầu paid quality của Phase 6 được thoả bằng artifact này, không còn
      một paid run treo thứ hai.
- [ ] Distribution tool count cho thấy call bounded; duplicate và no-progress
      adversarial terminate đúng như đặc tả.
- [ ] Mọi visual part compile được bằng Flint chính thức và mọi số có evidence;
      chat control không có visual work.
- [ ] Toàn bộ API/web/build/security/replay check pass, và graduation report đủ
      để tái lập verdict mà không cần gọi paid lần nữa.
- [ ] Roadmap ghi rõ SaaS/production Vnstock vẫn disabled tới khi có quyền phần
      mềm và quyền dữ liệu upstream bằng văn bản.

## Risks And Rollback

**Corpus live tốn kém hoặc Turn không kết thúc:** runner refuse khi thiếu
ceiling và await/cancel mọi Turn. Dừng sau failure hệ thống đầu tiên; không đốt
phần budget còn lại để thu thập evidence đã biết là xấu.

**Gate lộ ra regression chất lượng:** giữ plan mở và Signal Desk sau flag
internal. Thứ tự rollback là UI panel → visual part → market toolset; engine
text/evidence hiện có deploy được suốt quá trình.

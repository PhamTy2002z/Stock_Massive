---
title: "Evidence-Led Chat Surface"
description: "Biến lane chat từ shell AI tối giản thành bàn nghiên cứu có bằng chứng — trên cả web surface và harness backend."
status: pending
priority: P1
effort: "12 phase"
tags: [ux, harness, web, api, accessibility]
created: 2026-08-27
# Phụ thuộc alembic single-head vào 260826-2158-study-artifact-canvas đã **thoả**
# 2026-08-28: Study 09a done, `alembic heads` trả một head `e6b3d90c41af`.
# Điểm tiếp xúc còn lại chỉ là đọc — xem §Không đụng plan Study.
# 2026-08-28: phase 03 bị chặn — xem §Phase 03 đã bị đảo tiền đề.
relatedTo: [260826-2158-study-artifact-canvas]
# 2026-08-29: phase 02 bị hẹp — `260829-0010-composer-attachments` cho hai row
# AttachMenu handler thật, nên phép xoá toàn phần hết cơ sở. Xem khối đảo
# tiền đề trong phase-02.
# 260828-2126-price-basis-and-signal-field-spine đóng 2026-08-29 (9/9 phase) → nhả chặn.
# 2026-08-29: composer-attachments đóng 10/10 → nhả chặn.
# 2026-08-29: chặn mới hẹp hơn — chỉ phase 09 và 10. Phase 09 phơi
# MAX_TOOL_ROUNDS/MAX_EXTERNAL_TOOL_CALLS ra UI làm tier, và
# 260829-1349-c1-search-and-evidence phase 04 đang đổi đúng hai số đó;
# phase 10 là mặt UI của citation mà C1 phase 05 sinh ra ở backend.
# Phase 01-08 web thuần, KHÔNG bị chặn — chạy song song được.
blockedBy: [260829-1349-c1-search-and-evidence]
---

# Plan: Evidence-Led Chat Surface

Nguồn quyết định: `docs/text.md` — critique dual-agent
(`.impeccable/critique/2026-08-27T16-07-48Z__apps-web-src-components-shell-view-chat-tsx.md`),
**22/40 Design Health**, 5 vấn đề P1, 10 vùng UX chưa hoàn chỉnh, 4/8 checklist
cognitive load fail.

Ba báo cáo nền của plan này (mọi số dưới đây đo từ chúng, không phỏng đoán):

| Báo cáo | Nội dung |
|---|---|
| `plans/reports/scout-260827-2318-web-chat-shell.md` | 14 vùng shell web, mọi claim kèm `path:line` |
| `plans/reports/scout-260827-2318-api-harness.md` | 14 vùng harness backend, router · model · SSE · lifecycle |
| `plans/reports/research-260827-2318-hermes-vs-opencode-harness.md` | So sánh Hermes · opencode · repo cho 6 mục A–F |

## Authority

`docs/Harness/` là SOT cho contract AI (xem `docs/Harness/README.md` §Authority).
Plan này **sở hữu cách triển khai**, không sở hữu contract. Ba chỗ SOT đã chốt
sẵn và plan bám theo:

- `target-architecture.md:264` — model gateway route theo **workload contract**,
  không theo tên model. `investment-intelligence-contract.md:194` ghi non-goal:
  "Hỗ trợ mọi provider/model chỉ để có portability checklist".
- `target-architecture.md:366` — opencode server/session separation = **Adapt**;
  server sở hữu typed durable state, FE là client mỏng.
- `investment-intelligence-contract.md:156` — output contract: as-of và
  freshness **khi thời gian ảnh hưởng kết luận**, evidence + provenance,
  uncertainty, falsifier. Đây là spec của phase 10, không phải phát minh của UI.

Ba chỗ SOT **stale**, plan không viện dẫn: `docs/Harness/README.md` trỏ
`docs/harness-roadmap.md`, `docs/system-roadmap.md`, `src/eval/cli.py` — cả ba
không còn tồn tại (eval đã rip 2026-08-22).

## Ba quyết định đã chốt với user 2026-08-27

1. **Không có model selector theo tên provider.** Cụm "Visgnite Pro" thành
   **tier nghiên cứu** — 3 chế độ map sang (route model, trần vòng tool, trần
   external call). Tier đổi **độ sâu và chi phí**, không bao giờ đổi quyền
   (autonomy contract giữ nguyên A0/A1). Phase 09.
2. **Share = export cục bộ, không public link.** Transcript có bằng chứng qua
   cổng redaction fail-closed. Không bảng `share_token`, không URL công khai,
   không rò rỉ. Public link để lại thành plan riêng có mục threat model —
   `docs/Harness/` hiện **không có một dòng nào** về share. Phase 11.
3. **Chạy song song plan Study, tách làn migration.** Phase web-only đi ngay;
   đúng một phase cần alembic (08) bị chặn tới khi Study phase 09 merge.

## Nguyên tắc xuyên suốt

- **Chỉ render affordance có hành vi hoàn chỉnh.** Mỗi click thất bại dạy user
  rằng UI không đáng tin. Không menu rỗng, không chevron giả, không "sắp ra mắt"
  trong daily workspace.
- **Không badge trang trí.** Session state và độ mới dữ liệu đến từ store thật.
  Không có dữ liệu → **không render gì**, không bao giờ render số giả.
- **FE không giữ state phái sinh** (`target-architecture.md:366`). Nhóm recency,
  tổng hợp evidence, tier resolve — tính ở server, FE hiển thị.
- **Event mới khai tường minh durable hay live-only.** Mọi `*.delta` phải có
  `*.ended` làm biên replay. Đổi nghĩa event → **đổi tên type**, không bump
  envelope. Nhớ vào checkpoint **trước** khi announce, và thêm khoá vào
  `snapshot_from_draft` — quên là reconnect mất event.
- Trước mọi migration: backup DB (`pg_dump` vào `backups/`, không commit).

## Trạng thái & phases

| # | Phase | Lớp | Phụ thuộc | Alembic | Trạng thái |
|---|---|---|---|---|---|
| 01 | [Freeze, contract & a11y baseline](phase-01-freeze-contract-and-accessibility-baseline.md) | web + docs | — | — | pending |
| 02 | [Distill affordance ngõ cụt](phase-02-distill-dead-end-affordances.md) | web | 01 | — | pending |
| 03 | [Market context spine](phase-03-market-context-spine.md) | api | 01 (phụ thuộc ngoài plan đã **thoả** 2026-08-29) | — | **phải viết lại trước khi thi công** |
| 04 | [Research launchpad empty state](phase-04-research-launchpad-empty-state.md) | web | 02, 03 | — | pending |
| 05 | [History information architecture](phase-05-history-information-architecture.md) | web | 02 | — | pending |
| 06 | [Long conversation ergonomics](phase-06-long-conversation-ergonomics.md) | web | 02 | — | pending |
| 07 | [Mobile drawer & responsive](phase-07-mobile-drawer-and-responsive.md) | web | 02 | — | pending |
| 08 | [Thread lifecycle & titles](phase-08-thread-lifecycle-and-titles.md) | api + web | 05 | **1 revision** (S2) | pending |
| 09 | [Research tier selector](phase-09-research-tier-selector.md) | api + web | 08 | — | pending |
| 10 | [Answer evidence header](phase-10-answer-evidence-header.md) | api + web | 03, **08** (cột as_of/health) | — | pending |
| 11 | [Share as evidence export](phase-11-share-as-evidence-export.md) | api + web | 02, 08 (audit), 10 | — | pending |
| 12 | [Verification & re-score](phase-12-verification-and-rescore.md) | cả hai | 04–11 | — | pending |

Đường tới hạn: `01 → 02 → 05 → 08 → {09, 10 → 11} → 12`. Ba nhánh web (04, 06, 07)
chạy song song được sau 02. Phase 03 **không còn** chạy song song ngay sau 01 —
nó chờ `260828-2126-price-basis-and-signal-field-spine/` phase 02 (xem dưới), và
phase 04 phụ thuộc 03 nên chờ theo.

**Phase 08 hết bị chặn** — Study 09a đã done và `alembic heads` trả một head
(`e6b3d90c41af`), xác minh 2026-08-28. Nhưng 08 giờ nằm trên đường tới hạn của cả
09, 10 và 11 vì revision của nó mang cột mà ba phase đó cần (S2). Hệ quả thực tế:
08 là phase phải làm cẩn thận nhất, không phải phase làm nhanh nhất.

~~**Phase 03 không còn read-only.** Nó sửa `trading_day.py` (S1) — lịch mà 25
Signal Field đọc.~~ → **đảo lại 2026-08-28:** việc sửa lịch chuyển sang plan
khác, phase 03 quay về read-only. Chi tiết ngay dưới.

### Phase 03 đã bị đảo tiền đề (2026-08-28) — plan này giờ bị chặn

Red-team 2026-08-27 kết luận "lịch giao dịch của hệ thống đã chết" và giao phase
03 quyền sửa `trading_day.py`. Đo lại 2026-08-28 cho thấy **ba claim nền của kết
luận đó đều sai** vì phép đo chạy trong session Postgres `TimeZone = UTC`:

| Claim | Đo lại |
|---|---|
| `latest_trading_day` báo sớm một ngày | chạy thật → `2026-08-24 Monday`, đúng. `providers/normalize.py:23-36 day_in_vn` đã `astimezone(VN_TZ)` |
| 17/80 dòng rơi vào cuối tuần | đếm theo `AT TIME ZONE 'Asia/Ho_Chi_Minh'`: **0** dòng cuối tuần, mọi source |
| FiinQuant lệch so `bar_daily` | join theo local date: **80/80 khớp tuyệt đối, 0,000%** |

Lỗi thật là khác: `provider_snapshots` **không còn writer nào** trong `src/`, nên
lịch đứng yên ở 2026-08-24 vĩnh viễn. Cách sửa cũng khác — đổi nguồn lịch sang
`bar_daily`, không sửa timezone.

**Kết luận "đổi `trading_day.py` đọc `bar_daily`" (chốt 2026-08-28, ghi ở §Quyết
định bên dưới) vẫn đúng — nhưng đổi chủ sở hữu.** Nó chuyển sang
`plans/260828-2126-price-basis-and-signal-field-spine/` **phase 02**, vì ở đó nó
đi liền với việc `signals/sessions.py` cũng phải chuyển nguồn trong cùng một
nhánh: lịch và row khớp nhau theo `effective_at` **bằng đúng** (`sessions.py:117`),
nên tách hai bên ra hai plan là mở một cửa sổ mà mọi Signal Field trượt sạch.

Sau khi phase 02 bên đó xong, phase 03 ở đây trở lại **read-only**: chỉ đọc lịch,
không sửa `trading_day.py`, blast radius về gần 0. **Phải viết lại phase 03 trước
khi thi công nó** — bản hiện tại vừa dựa trên ba claim đã bị đảo, vừa nhận một
việc không còn là của nó.

**Cập nhật 2026-08-29 — phụ thuộc đã thoả, việc viết lại thì chưa.** Plan
`260828-2126-price-basis-and-signal-field-spine/` đã đóng 9/9 phase:
`trading_day.py` đọc `bar_daily` (phase 02), `signals/sessions.py` cùng nhánh
(phase 03), và dòng FiinQuant đã xoá khỏi DB (phase 08, revision `a3f7e21b8d54`).
Nên phase 03 ở đây **không còn bị chặn** — nó chỉ còn nợ một bản viết lại.

## Không đụng plan Study — làn tách thế nào

Plan Study `260826-2158-study-artifact-canvas` còn phase 08b, 09a, 09b, 10.
Footprint của nó: `src/stocks/financial/*`, `src/stocks/signals/*`,
`src/studies/earnings_dislocation.py`. Phase 10 của nó ghi thẳng "không file web
mới". Ba luật giữ hai plan không cắn nhau:

1. **Alembic một head.** Head hiện tại `e6b3d90c41af`. Study 09a thêm 2 bảng.
   Phase 08 của plan này thêm **đúng một revision** (3 cột additive trên
   `agent_thread`) và **chỉ được tạo revision sau khi Study 09a đã merge** —
   `alembic heads` phải trả một dòng trước khi chạy `revision`.
2. **Không đụng `src/stocks/*`.** Plan này chỉ đọc: `trading_day.py`,
   `session_window.py`, `universe.py`, `listing_roster.py`, `bar_daily`,
   `bar_intraday_15m`. Phase 03 tạo module mới, không sửa reader của signals.
3. **Không bump `PROMPT_VERSION`, không sửa vòng tool của `loop.py`.** Study
   acceptance #5 dựa vào việc thêm Study không cần sửa prompt contract. Phase 09
   đổi **trần** vòng tool qua tham số, không đổi cấu trúc vòng.

## Freeze amendment cần thiết (phase 01 làm)

CLAUDE.md ghi "Hard freeze ngoài `src/agent/*` — PR duy nhất được nhận là
harness, auth tenant, budget schema". Plan này **là** PR harness, nhưng phải ghi
tên file ra như phase 01 của plan Study đã làm.

**Danh sách này đã sửa sau red-team** — bản đầu nêu bốn file không tồn tại và bỏ
sót năm file thật. Mở đúng:

| File | Vì sao | Phase |
|---|---|---|
| `src/alpha/models.py` | `agent_thread` ở đây (`:26`), **không** ở `src/agent/models.py` — file đó không tồn tại | 08 |
| `src/agent/persistence.py` | mọi query thread thật ở đây (`:378,429-439,452,485,516,569,620,695-716`), **không** ở `service.py` | 08 |
| `src/agent/ops.py` | đường đọc thread thứ hai (`:320-341`) | 08 |
| `src/agent/tools/memory.py` | raw SQL `JOIN agent_thread` (`:213-222`) — không bao được bằng helper Python | 08 |
| `src/core/llm/admission.py` | đường đọc thread thứ ba (`:900-902`) | 08 |
| `src/agent/{router,schemas}.py` | thread lifecycle, tier, export | 08, 09, 11 |
| `src/agent/{loop,messages,turns}.py` | evidence summary, ghi as-of/health lúc tool trả | 09, 10 |
| `src/agent/guardrails.py`, `src/agent/executor.py` | hiệu chỉnh theo hai trần mà phase 09 tham số hoá | 09 |
| `src/stocks/trading_day.py` | lịch giao dịch đọc bảng đã chết — sửa tận gốc | 03 |
| `src/market_context/*` (mới) | session state + freshness read | 03 |
| `src/agent/export/*` (mới) | transcript export + redaction | 11 |
| `apps/web/src/components/shell/*` + `lib/*` | surface chat | mọi phase web |
| `apps/web/src/components/alpha/message/*` | `message-shell`, `message-actions`, `assistant-message` ở đây, **không** ở `components/shell/` | 01, 06, 10 |
| `apps/web/src/components/settings/account-section.tsx` | caller `navigator.clipboard` thứ tư (`:28`) | 06 |

CLAUDE.md đang **lệch thực tế ba chỗ**, phase 01 sửa cùng lúc:

| CLAUDE.md ghi | Thực tế đo | Nguồn |
|---|---|---|
| `PROMPT_VERSION` 2.6.0 | **2.7.0** | scout api §9 |
| 8 tool / 3 bundle | **12 tool / 4 bundle** | scout api §10 |
| 406 test web | **446 case / 37 file** | scout web §13 |

## Sửa sau red-team (2026-08-28) — đọc trước khi thi công

Hai reviewer đối kháng tìm **10 BLOCKER + 19 MAJOR**. Báo cáo:
`plans/reports/redteam-260827-2340-evidence-led-chat-surface.md` (khả thi) và
`plans/reports/redteam-260827-2340-security-and-ux-truth.md` (bảo mật + trung
thực UX). Mười một quyết định dưới đây **đảo** nội dung bản đầu và đã vá vào từng
phase. Nếu một phase file nói khác mục này, mục này thắng.

### S1 — Lịch giao dịch của hệ thống đang chết. Phase 03 sửa tận gốc.

Đo trên DB thật 2026-08-28:

| Nguồn | Mới nhất |
|---|---|
| `provider_snapshots` capability `market` — cái `trading_day.latest_trading_day()` đọc (`stocks/trading_day.py:43-54`) | **2026-08-23** |
| `bar_daily` (`series` = equity 809.085 dòng · index 3.991) | **2026-08-27** |

Collector ghi `provider_snapshots` đã rip 2026-08-25; bảng đóng băng. Nên **toàn
bộ** `trading_day.py` — `latest_trading_day`, `trading_days_before/between` — trả
lịch trễ 4 phiên và đang trôi xa thêm mỗi ngày. `signals/` và `studies/` đều đọc
nó.

Quyết định (user chốt 2026-08-28): **`trading_day.py` đọc `bar_daily`**, không tạo
lịch thứ hai trong `src/market_context/`. ~~Phase 03 làm việc đó.~~ → **Chuyển
chủ sở hữu 2026-08-28 sang `260828-2126-price-basis-and-signal-field-spine/`
phase 02** (lý do ở §Phase 03 đã bị đảo tiền đề). Con số đúng là **30** Signal
Field đọc lịch này, không phải 25. Phase 03 ở đây quay lại read-only.

Kèm hai lỗi cột của bản đầu: bảng dùng `trading_day`, **không** `session_date`;
và `bar_daily` chứa cả `equity` lẫn `index` trong một bảng nên mọi truy vấn phải
lọc `series`, không thì nhánh daily trộn VN-Index vào cổ phiếu.

### S2 — Phase 08 mang **một** revision nhưng bốn nhóm thay đổi.

Bản đầu nói 3 cột trên `agent_thread`. Thực tế cần:

| Đối tượng | Thay đổi | Vì sao |
|---|---|---|
| `agent_thread` | `archived_at`, `title_source`, `research_tier` | như bản đầu |
| `agent_turn` | tier đã dùng thật | phá vòng phụ thuộc 08↔09 (bản đầu để phase 09 tự quyết → vòng) |
| `agent_tool_call` | `as_of`, `health` | **không có** hai cột này (`alpha/models.py:157-205`); phase 10 không thể tổng hợp mà không có chúng. User chốt thêm cột. |
| `agent_export_audit` (bảng mới) | ai export thread nào, lúc nào | SOT `quality-safety-and-operations.md:227` đòi audit đường export |

Vẫn **một** revision — quy tắc single-head giữ nguyên. `alembic heads` xác minh
2026-08-28: một head `e6b3d90c41af` (chính là revision Study 09a, **đã done**),
nên phase 08 **hết bị chặn**.

### S3 — Lọc thread archive phải là **view Postgres**, không phải helper Python.

`agent/tools/memory.py:213-222` là **raw SQL** join `agent_thread` để full-text
search nội dung message. Một helper trả `select()` không dùng được ở đó. Nếu bỏ
sót: user xoá thread → ba ngày sau model trích lại nội dung của nó.

Nên: view `agent_thread_active` trong cùng revision. ORM và raw SQL đều đọc view.
Test grep đổi thành "zero query đọc `agent_thread` trực tiếp trừ chính view và
đường undo".

### S4 — Phase 11: whitelist theo **cột** là fail-open. Phải theo khoá JSON.

`agent_message.content` là JSONB, shape thật ở `agent/turns.py:248-259`:
`{text, answer, thoughts, tool_calls, canvases, status, elapsed_ms}`. Whitelist
`{"role","content","created_at"}` cho `content` đi qua **nguyên vẹn** — gồm
`thoughts` (reasoning, đúng cái phase hứa loại) và `tool_calls[].results[]` (có
`url` ≤2048 ký tự và `snippet` từ trang ngoài, `messages.py:421-428`).

Và `kind = answer|thought` **chỉ tồn tại trên SSE**, không tồn tại trong store
(store tách bằng khoá `answer` vs `thoughts`). Nên success criterion cũ
"`kind = thought` không có trong export" là **test rỗng** — pass dù xuất trọn
reasoning.

Sửa: whitelist đệ quy theo **đường khoá JSON**, không theo cột. Cộng ba thứ SOT
đòi mà bản đầu bỏ: audit row (S2), retention/deletion path tường minh, và escape
nội dung untrusted trước khi ghi Markdown.

### S5 — Phase 09 bỏ hai module hiệu chỉnh theo chính hai trần nó tham số hoá.

`guardrails.py:82-95` đặt `same_tool_failure_halt_after=6` **bằng** trần external
("a rung set above either of those is a rung nothing can ring");
`executor.py:88-92` biện minh `MAX_EXTERNAL_CALLS_PER_ROUND=8` bằng con số 6. Nên
`quick` (trần 2) làm rung chết, `deep` (trần 8) có thể halt giữa turn. "Chỉ đổi
trần" là sai — phase 09 phải đổi cả hai module cùng lượt.

Thêm: route `llm_model_batch` (`deep` định dùng) **chưa từng probe lúc runtime** —
probe chỉ chạy SESSION (`main.py:52-56`); `Workload.BATCH` chỉ xuất hiện ở config
và pricing, không có call site. Bước 2 của phase 09 phải probe nó trước, không
giả định nó tương đương.

### S6 — Trần per-user là **số lượt**, không phải tiền.

`llm_user_turn_starts_per_day=20` (`core/config.py:161`, enforce
`admission.py:567`); envelope là toàn hệ thống. Hai mươi lượt `deep` của một user
rút cạn lane Turn của mọi user, và phản ứng duy nhất là kill switch toàn cục.
Phase 09 phải nêu điều này thẳng; nếu không có trần theo chi phí thì `deep` mặc
định **tắt** (`enabled=false`) và bật theo chủ ý.

Cùng họ: `OwnerType` chỉ có ba giá trị (`admission.py:71-74`), nên chi phí title
generator của phase 08 dùng lại owner_id của turn thì **không tách được** trong
ledger — đúng cái phase 08 muốn tránh. Cần owner type thứ tư, hoặc chấp nhận
không tách và nói rõ.

### S7 — Phase 02: TopBar có **4** item và một cái không có bản sao ở đâu.

Bốn item thật: Ghim · Đổi tên · **Xuất PDF** · Xoá (`top-bar.tsx:73,76,79,83`).
`ThreadMenu` của sidebar chỉ có **3** (`sidebar.tsx:382-394`); export không tồn
tại ở đâu, và phase 11 làm **Markdown**, không PDF. Nên phase 02 nối 3 và **xoá**
item export; phase 11 mang nó về với nhãn "Xuất Markdown".

Và pin/unpin **đã hoạt động** (`sidebar.tsx:340-343,382-393`) — phase 02 và 05
đều nói sai là chưa. Contract là `pinned: bool` (`schemas.py:57`), server tự
`coalesce(pinned_at, now())`. Nên criteria cũ "unpin = `null`" đòi đổi public
contract mà không có lý do; bỏ.

### S8 — Ticker chip của phase 05 sẽ trống 100% mọi thread.

Cơ chế union `symbols` **đã chạy** (`persistence.py:391-395`, từ
`CreateTurnRequest.symbols`) nhưng lane chat **cố ý gửi rỗng**:
`desk-state.tsx:169-170` — *"guessing which symbols a sentence is about would put
a parser in the browser and a wrong answer in the idempotency payload"*. Lý do đó
đúng và không đảo.

Nên: phase 05 ghi thẳng chip trống tới khi 08 xong; phase 08 điền `symbols`
**từ argument của tool call ở server** (mã đã thật sự được đọc — chính xác, không
phải regex) và đi qua **đúng đường union đã có**, không mở đường thứ hai trong
`loop.py`.

### S9 — Trust line của phase 04 hứa hộ model điều prompt cấm.

`prompt/sections.py:239`: *"Tra rồi thì nêu thời điểm, **đừng nêu nguồn**"*;
`:363`: *"**Không viết phần dẫn nguồn**… Việc đó là của giao diện"*. Uncertainty
là có điều kiện (`:367`). Nên câu "Câu trả lời nêu nguồn…" là lời hứa sai chủ
thể.

Sửa: trust line nói cái **hệ thống** làm, không cái model viết — "Nguồn và thời
điểm dữ liệu hiện ở tab Nguồn cạnh mỗi câu trả lời." Và phase 12 thêm một test
đối chiếu trust line với prompt contract, để hai chỗ không lệch nữa.

### S10 — Evidence line phải có materiality gate.

Contract:156 nói as-of/freshness **"khi thời gian ảnh hưởng kết luận"**, và
non-goal:198 cấm "cảnh báo… không có materiality gate". `min(as_of)` + `health`
xấu nhất không điều kiện sẽ gắn cảnh báo lên 100% câu trả lời → user học cách bỏ
qua nó.

Sửa: dòng luôn hiện ở tone **trung tính**; chỉ lên tone cảnh báo khi có
materiality thật — `sessionsBehind > 0`, hoặc `health != normal`, hoặc
`noValueCount > 0`. Và tóm tắt **tách** nguồn store với nguồn web
(`messages.py:218-220` gọi phân biệt này là *"the distinction the whole evidence
boundary rests on"*) — gộp chúng là phá luật "tách hai khối bằng chứng" đã ghim
trong prompt.

### S11 — Bốn acceptance của bản đầu là test luôn xanh hoặc không phải test.

| Acceptance cũ | Vì sao vô nghĩa | Thay bằng |
|---|---|---|
| "cụm nằm trên optical center", test `rect.top < h/2` | jsdom trả rect **0** → luôn xanh | e2e Playwright, đo rect thật |
| "hit area ≥44px" trong vitest | cùng lý do | e2e, hoặc test class + một e2e xác nhận |
| "kiểm thật trên Safari iOS" | không phải test tự động | checklist tay có ghi kết quả, đánh dấu rõ là kiểm tay |
| "một request = một truy vấn/nguồn" + "cache 30s hoạt động" | hai cái đối đầu nhau; và cache in-process sai trong multi-worker (`Dockerfile:37`) | bỏ cache in-process; đo query count không có cache |

Cộng: acceptance #10 (cognitive load ≤1 fail) đo **toàn sidebar** theo
`docs/text.md:177,185` (~18 item). Sau phase 05 có thể >20 item → không đạt được
như viết. Phase 12 phải đếm lại theo đúng định nghĩa của critique, hoặc nêu rõ
tiêu chí nào không đạt và vì sao.

### Gap scope duy nhất còn lại

Persona Alex "path nhanh theo mã" (`docs/text.md` §Persona Red Flags) — phase 05
tường minh từ chối, không phase nào nhận. Đây là thu hẹp scope so với yêu cầu
"toàn bộ đề xuất"; nêu ra thay vì che.

## Baseline đo được (mốc so sánh của mọi phase)

| Chỉ số | Giá trị |
|---|---|
| `make test` apps/api | 1060 pass |
| `pnpm test` apps/web | 446 case / 37 file |
| Alembic head | `e6b3d90c41af` (một head) |
| Route `/` bundle | 82,2 kB · First Load 214 kB |
| Design Health | **22/40** — thấp nhất là Help & Documentation 1/10 |
| Cognitive load | 4/8 checklist fail |
| Touch target icon button | `size-7` 28px / `size-[30px]` 30px — dưới WCAG 2.5.5 |
| Nhãn ARIA tiếng Anh còn sót | 5 (`message-shell.tsx:29`, `inspector.tsx:68,79,100,120`) |
| Control thiếu focus ring | ~9 |

## Acceptance criteria toàn plan (đo, không cảm)

1. **Không còn affordance ngõ cụt.** Test contract: mọi control render ra đều
   có handler thật; không control nào `disabled` mà không kèm lý do đọc được;
   menu không mở khi không có item khả dụng. Đếm được, không review bằng mắt.
2. **Không badge giả — và không badge *đúng về một số sai*.** Hai nửa:
   (a) tắt `GET /market/context` (5xx hoặc payload null) → chip **biến mất**,
   không placeholder, không crash; (b) lịch giao dịch mà chip dựa vào đọc nguồn
   **có writer sống** — test khẳng định `latest_trading_day()` khớp
   `max(bar_daily.trading_day)` cho `series='equity'`, không khớp
   `provider_snapshots`. Nửa (b) là cái bản đầu bỏ sót và nó là nửa quan trọng
   hơn: một chip hiện số đóng băng còn tệ hơn một chip biến mất.
3. **Empty state trả lời được câu "nên hỏi gì" trong 5 giây**: ≥3 starter theo
   tác vụ, mỗi cái có mô tả output, cộng một trust line nêu nguồn · thời điểm ·
   giới hạn. Collapse khi conversation bắt đầu.
4. **Mobile không bóp main.** Ở 390px, 430px và tablet: mở sidebar → `main`
   giữ nguyên width, drawer phủ lên, có scrim, Escape đóng, focus trap giữ
   focus, và khi đóng thì button trong drawer **không focusable** được.
5. **Xoá thread hoàn tác được** trong cửa sổ undo; rename của user không bao giờ
   bị title tự sinh ghi đè (precedence `derived < llm < user` enforce trong
   transaction, không ở call site).
6. **Tier đổi hành vi đo được** — trần vòng tool khác nhau quan sát được trên
   `agent_tool_call`; tier lạ → fallback mặc định, không crash. Tier **không**
   đổi tool allowlist hay quyền.
7. **Evidence header khớp trace, và tách hai khối bằng chứng.** as-of/health trên
   answer bằng đúng giá trị ở **cột** `agent_tool_call.as_of`/`.health` (cột mới
   từ S2 — trước đó không có chỗ nào lưu, nên acceptance này bản đầu không thực
   hiện được). Tóm tắt **tách** nguồn store với nguồn web, không gộp. Dòng chỉ
   lên tone cảnh báo khi có materiality (S10). `frames` vẫn không xuất hiện trong
   bất kỳ message gửi model — test transcript của plan Study phải còn xanh.
8. **Export fail-closed theo khoá JSON, không theo cột.** Khoá JSON không nằm
   trong whitelist đệ quy **không bao giờ** ra output — đặc biệt `content.thoughts`
   và `content.tool_calls[].results[].{url,snippet}`. Test: thêm một khoá giả
   **bên trong** `content` và khẳng định nó bị loại; và một test khẳng định
   reasoning (`content.thoughts`) không có trong output — không phải test trên
   `kind`, vì `kind` không tồn tại trong store (S4). Cộng: mỗi lần export ghi một
   dòng audit; nội dung untrusted được escape trước khi vào Markdown.
9. **A11y:** mọi control tương tác có accessible name **tiếng Việt** và focus
   ring hiển thị; menu custom đi được bằng arrow key + Home/End + Escape; contrast
   đạt AA trên cả `.light` và dark. Hit area ≥44px và vị trí cụm mở đầu đo bằng
   **e2e**, không bằng vitest — jsdom trả rect 0 nên assertion đó luôn xanh giả
   (S11).
10. **Thread đã archive không rò qua bất kỳ đường nào** — gồm cả full-text search
    của memory tool (`agent/tools/memory.py:213-222`, raw SQL). Test: archive một
    thread rồi gọi memory tool, khẳng định nội dung của nó không được trích (S3).
11. **Tier không nới quyền và không phá guardrail.** Cùng tập tên tool ở ba tier;
    và `guardrails.py` + `executor.py` được hiệu chỉnh lại cùng lượt (S5) — test
    khẳng định `quick` không làm rung guardrail chết và `deep` không halt giữa
    turn.
12. **Design Health ≥32/40** với **mọi** heuristic ≥3. Cognitive load: đếm lại
    theo đúng định nghĩa của critique (toàn sidebar, `docs/text.md:177,185`) và
    nêu rõ tiêu chí nào không đạt kèm lý do — **không** cam kết ≤1 fail như bản
    đầu, vì con số đó chưa được kiểm là đạt được (S11).
13. Mỗi phase xanh: `make test` (apps/api, host) + `pnpm type-check && pnpm lint
    && pnpm test && pnpm build` (apps/web). Không phase nào để test đỏ sang
    phase sau.
14. Route `/` First Load **không tăng quá 10%** so với 214 kB.

## Rủi ro cấp plan

| # | Rủi ro | Tín hiệu nó xảy ra | Phản ứng đã định |
|---|---|---|---|
| R1 | **Tier nghiên cứu là nhu cầu giả.** Repo chỉ có 2 route (`llm_model_batch`, `llm_model_session`); nếu động lực thật chỉ là hiển thị chi phí thì selector là scope thừa. | Phase 09 dựng xong nhưng 3 tier chỉ khác nhau ở trần vòng tool, không khác route | Thu về **hai** tier có route thật khác nhau, hoặc hạ xuống label tĩnh honest (option B của quyết định 1). Không giữ 3 tier chỉ để có 3. |
| R2 | **Undo delete va cascade.** `agent_thread` xoá là hard cascade; đổi sang `archived_at` mà bỏ sót một reader sẽ làm thread đã archive vẫn hiện. | Test undo xanh nhưng list thread trả cả thread archived | Phase 08 grep **mọi** query đọc `agent_thread` trước khi đổi, không sau. |
| R3 | ~~Làn migration bị chặn dài~~ → **đảo sau red-team: 08 giờ chặn ba phase.** Study 09a đã done, một head, nên 08 chạy được ngay — nhưng revision của nó mang cột mà 09, 10, 11 đều cần (S2). Một lỗi trong 08 chặn nửa sau của plan. | Revision 08 phải sửa sau khi merge | 08 làm **một** revision với đủ bốn nhóm thay đổi, không chia nhỏ. Trước khi viết revision, đọc lại S2 và xác nhận danh sách cột với phase 09/10/11 — sai sót ở đây tốn một revision thứ hai và phá luật single-head với plan Study. |
| R6 | ~~Sửa `trading_day.py` phá 25 Signal Field~~ → **chuyển khỏi plan này 2026-08-28.** Việc sửa lịch (và rủi ro 30 Signal Field kèm theo) giờ thuộc `260828-2126-price-basis-and-signal-field-spine/` phase 02-03. | — | Phase 03 ở đây chỉ **đọc** lịch. Rủi ro còn lại là đọc một lịch chưa được sửa: phase 03 không merge trước khi phase 02 bên đó xong. |
| R7 | **Export là egress không có chủ.** Bearer token + `GET /threads` cho phép duyệt và xuất mọi thread; SOT đòi audit + retention + phân loại capability (S4). | — | Phase 11 không merge trước khi có audit row và một câu tường minh về retention. Nếu không ai sở hữu retention path thì phase 11 **hoãn**, không phát hành nửa vời. |
| R4 | **Xoá affordance làm mất chức năng user đang dùng.** TopBar menu 4 item disabled nhưng sidebar làm thật cùng 4 việc đó. | — | Phase 02 **nối** TopBar menu vào handler thật của sidebar thay vì xoá menu. Chỉ xoá cái không có handler ở đâu cả. |
| R5 | **Critique re-score là judgment của LLM, không phải metric.** Acceptance #10 có thể pass/fail vì lý do ngoài code. | Điểm đổi mà diff không đổi | #10 là cổng mềm. Chín acceptance còn lại đều là test chạy được và là cổng cứng. |

## Câu hỏi chưa giải quyết

- Public share link: cần threat model được chấp nhận ghi vào `docs/Harness/`
  trước khi thành plan. Chưa có ai sở hữu quyết định này.
- Licence vnstock (R1 của plan Study) chặn ngày launch, không chặn plan này.
  Nhưng nếu launch không xảy ra thì phase 11 export là surface duy nhất đưa dữ
  liệu ra ngoài — đáng soát lại lúc đó.

<!-- slug: evidence-led-chat-surface -->

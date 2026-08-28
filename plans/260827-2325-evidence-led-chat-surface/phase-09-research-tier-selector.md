---
phase: 9
title: "Research tier selector"
status: todo
priority: P2
effort: ""
dependencies: [8]
---

# Phase 09: Research tier selector

## Overview

Biến cụm "Visgnite Pro" — hiện là một `<span>` tĩnh mang chevron giả
(`composer.tsx:182-185`) — thành một control có hành vi thật. Nhưng **không** thành
một danh sách provider: `docs/Harness/investment-intelligence-contract.md:194` ghi
non-goal "Hỗ trợ mọi provider/model chỉ để có portability checklist", và
`target-architecture.md:264` chốt routing theo **workload contract**, không theo
tên model.

Nên control này chọn **độ sâu nghiên cứu**, và độ sâu map sang một tuple hạ tầng.
Tier đổi chi phí và thời gian; nó **không bao giờ** đổi quyền hay tool allowlist.

**Đọc R1 cấp plan trước khi làm phase này.** Repo chỉ có hai route cấu hình
(`llm_model_batch=gpt-5.6-luna`, `llm_model_session=gpt-5.6-terra` — scout api §5).
Nếu ba tier hoá ra chỉ khác nhau ở trần vòng tool mà cùng một model, thì phase này
nên thu về hai tier hoặc hạ xuống label tĩnh. Quyết định đó lấy ở bước 2, **trước**
khi viết UI.

## Sửa sau red-team (2026-08-28)

Bốn điều chỉnh, hai trong đó là lỗi thiết kế của bản đầu:

**1. "Chỉ đổi trần" là sai — hai module khác được hiệu chỉnh *theo* hai trần đó.**

| Module | Ràng buộc | Hệ quả nếu bỏ qua |
|---|---|---|
| `src/agent/guardrails.py:82-95` | `same_tool_failure_halt_after = 6` đặt **bằng** trần external, kèm bình luận *"a rung set above either of those is a rung nothing can ring"* | `quick` (trần 2) làm rung guardrail **chết** — nó không bao giờ rung được |
| `src/agent/executor.py:88-92` | `MAX_EXTERNAL_CALLS_PER_ROUND = 8` biện minh bằng con số 6 | `deep` (trần 8) có thể **halt giữa turn** |

Nên phase này đổi **cả ba** chỗ cùng lượt, và guardrail rung phải dẫn xuất từ trần
của tier đang chạy, không phải hằng số.

**2. Route `llm_model_batch` chưa từng probe lúc runtime.** Probe chỉ chạy SESSION
(`main.py:52-56`); `Workload.BATCH` chỉ xuất hiện ở config và pricing, **không có
call site runtime**. Bốn check loop phụ thuộc (`closed_tool_loop`…) chưa xác minh
cho route đó. Bước 2 phải probe nó trước, không giả định tương đương.

**3. Trần per-user là số lượt, không phải tiền.** `llm_user_turn_starts_per_day = 20`
(`core/config.py:161`, enforce `admission.py:567`); envelope là **toàn hệ thống**.
Hai mươi lượt `deep` của một user rút cạn lane Turn của mọi user, và phản ứng duy
nhất là kill switch toàn cục. Nên: **`deep` mặc định `enabled = false`**, bật theo
chủ ý sau khi có trần theo chi phí. Cơ chế `enabled` ở catalog tồn tại chính vì lý
do này.

**4. Cột "tier đã dùng" thuộc revision của phase 08, không phải quyết định của phase
này.** Bản đầu để phase 09 tự quyết chỗ ghi "nếu cần cột thì đưa vào revision phase
08 trước khi 08 merge" — nhưng 09 phụ thuộc 08, nên đó là **vòng phụ thuộc**. Đã
giải: cột nằm trên `agent_turn` trong revision của 08 (`plan.md` §S2). Và fallback
cũ ("dùng cột JSON có sẵn") trỏ `agent_turn.draft_content` — cột checkpoint reconnect
mà phase 10 dựa vào; **không** dùng nó.

## Requirements

Functional:

- Catalog tier do repo sở hữu, khai tường minh, không lấy từ service ngoài.
- Guardrail rung và trần external per-round dẫn xuất từ tier đang chạy.
- Mỗi tier map sang (route model, trần vòng tool, trần external call).
- Tier chọn được ở composer; lưu trên thread (`research_tier`, cột đã có từ
  phase 08).
- Tier thực tế dùng cho một turn được ghi lại, không chỉ tier mong muốn.
- Tier lạ / `null` → fallback mặc định, không lỗi.

Non-functional:

- **Không đổi tool allowlist theo tier.** 12 tool giữ nguyên ở mọi tier.
- **Không bump `PROMPT_VERSION`, không đổi cấu trúc vòng tool của `loop.py`** —
  chỉ đổi **trần** qua tham số (`plan.md` §Không đụng plan Study luật 3).
- Không dựng provider catalog, không gọi models.dev.

## Architecture

**Ba tier, mỗi cái là một tuple tường minh.** Giá trị dưới đây là **đề xuất khởi
điểm**; bước 2 đo lại và chốt.

| Tier | Route | `max_tool_rounds` | `max_external_calls` | Khi nào |
|---|---|---|---|---|
| `quick` | `llm_model_session` | 1 | 2 | câu hỏi một dữ kiện |
| `balanced` (mặc định) | `llm_model_session` | 4 | 6 | hôm nay là hành vi duy nhất |
| `deep` | `llm_model_batch` | 6 | 8 | nhiều mã, nhiều nguồn — **`enabled = false` mặc định** (§Sửa sau red-team mục 3) |

Guardrail rung (`same_tool_failure_halt_after`) và trần external per-round không
phải hằng số nữa: chúng dẫn xuất từ `max_external_calls` của tier đang chạy, giữ
đúng quan hệ mà `guardrails.py:82-95` mô tả.

`balanced` **phải** khớp chính xác hành vi hiện tại (`MAX_TOOL_ROUNDS = 4`,
`MAX_EXTERNAL_TOOL_CALLS = 6` — scout api §4). Nghĩa là user không chọn gì thì
không có gì đổi. Đây là điều kiện để phase này không thành một hồi quy.

**Shape catalog lấy từ opencode, phạm vi lấy từ Hermes** (research §C). Từ
`ModelV2.Info` lấy ba bài học có giá trị thật:

- `cost` là **array có tier**, không phải một số — chuẩn bị cho pricing bậc thang.
- `limit.context` và `limit.output` **tách nhau** — hai ràng buộc khác nhau.
- `status` ≠ `enabled` — một tier có thể tồn tại mà không mở cho user.

Không lấy: danh sách provider, cơ chế fetch catalog từ ngoài (models.dev còn sai
context length, phải override — research ghi issue #84482).

Catalog nằm ở `src/agent/tiers.py` — Python thuần, không DB, không env. Nó là
capability catalog theo `target-architecture.md:215` (layer "Capability catalog",
trust = "repository/provider metadata").

**Endpoint.** `GET /api/v1/tiers` trả tier đang mở (`enabled`), kèm nhãn tiếng
Việt và một dòng mô tả. FE **không** hard-code ba tier — nếu tier bị tắt ở server
thì nó biến khỏi UI, không cần deploy web.

**Tier mong muốn vs tier thật.** Research §C ghi bài học từ opencode issue #51607:
bỏ tầng "model thật per-turn" là dồn hết chi phí cho model đầu tiên. Áp vào đây:

- `agent_thread.research_tier` = **mong muốn** của user (có thể `null` = mặc định).
- Turn ghi lại tier **đã dùng thật**. Nơi ghi: nếu `agent_turn` có cột phù hợp thì
  dùng; nếu không, thêm vào cùng revision của phase 08 — **quyết định ở bước 1
  của phase này, và nếu cần cột thì nó phải vào revision phase 08**, không tạo
  revision thứ hai.

Điều này quan trọng vì tier có thể bị hạ: hết ngân sách lane → `deep` chạy như
`balanced`. Khi đó trace phải nói cái đã chạy, không nói cái đã xin.

**UI.** Control ở footer composer, thay `<span>` tĩnh. Chevron **thật**. Menu đi
qua primitive menu của phase 02 (có luật không mở khi rỗng) và semantics bàn phím
của phase 10 nếu đã có; nếu chưa, phase này tự cài arrow-key + Home/End + Escape
cho menu này và phase 12 kiểm lại toàn bộ.

Mỗi item hiện: nhãn + một dòng hệ quả ("6 vòng · tốn ngân sách hơn"). Không hiện
tên model — tên model là chi tiết hạ tầng, và hiện nó ra là đi ngược non-goal đã
dẫn ở trên.

**Tier không đổi quyền.** Ghi thành test, không chỉ ghi thành lời: cùng một câu
hỏi ở ba tier → `agent_tool_call` có thể khác **số lượng**, không được khác **tập
tên tool được phép**. Autonomy contract giữ nguyên A0/A1
(`investment-intelligence-contract.md:177`).

## Related Code Files

Create:

- `apps/api/src/agent/tiers.py` — catalog + resolve
- `apps/api/tests/agent/test_tiers.py`
- `apps/api/tests/agent/test_tier_does_not_widen_authorization.py`
- `apps/web/src/components/shell/tier-selector.tsx`
- `apps/web/src/hooks/use-tiers.ts`
- `apps/web/src/components/shell/tier-selector.test.tsx`

Modify:

- `apps/api/src/agent/loop.py` — nhận trần qua tham số thay vì hằng số module
- `apps/api/src/agent/router.py` — `GET /tiers`; `PATCH /threads` nhận
  `research_tier`; ghi tier đã dùng khi tạo turn
- `apps/api/src/agent/schemas.py`
- `apps/web/src/components/shell/composer.tsx:182-185` — `<span>` → control

## Implementation Steps

1. Xác nhận cột "tier đã dùng" trên `agent_turn` đã có (revision phase 08). Nếu
   chưa → dừng; **không** tạo revision thứ hai và **không** dùng
   `agent_turn.draft_content` (cột checkpoint mà phase 10 dựa vào).
2. **Probe `llm_model_batch` lúc runtime** — nó chưa từng được probe
   (§Sửa sau red-team mục 2). Kiểm bốn check loop phụ thuộc trên route đó trước khi
   `deep` trỏ vào nó.
3. **Đo R1.** Chạy cùng một câu hỏi qua `llm_model_session` và `llm_model_batch`,
   so chất lượng và latency. Nếu hai route không khác nhau đáng kể thì **thu về hai
   tier** hoặc báo lại để hạ xuống label tĩnh. Ghi kết quả đo vào phase này.
4. **Hiệu chỉnh `guardrails.py` + `executor.py`** theo trần của tier. Test: `quick`
   → rung guardrail vẫn rung được; `deep` → không halt giữa turn.
3. `tiers.py`: catalog + `resolve(requested) -> TierConfig`, fallback mặc định cho
   giá trị lạ/`null`. Test bảng: `None`, `"quick"`, `"balanced"`, `"deep"`,
   `"nonsense"`, `""`.
4. `loop.py`: hai hằng số thành tham số có default **bằng đúng giá trị hiện tại**.
   Test hồi quy: gọi không truyền tham số → hành vi y hệt trước.
5. `GET /tiers` + `PATCH research_tier` + ghi tier đã dùng.
6. Test "tier không nới quyền": ba tier, cùng câu hỏi, so tập tên tool.
7. FE: `use-tiers.ts` + `tier-selector.tsx`. Menu có arrow-key/Home/End/Escape.
8. Cổng: `make test` + đầy đủ cổng web.

## Success Criteria

- [ ] `llm_model_batch` được probe lúc runtime trước khi `deep` trỏ vào nó; bốn
      check loop phụ thuộc xác minh trên route đó
- [ ] `quick` (trần 2) → rung guardrail **vẫn rung được** (test); `deep` (trần 8)
      → **không** halt giữa turn (test). `guardrails.py` + `executor.py` dẫn xuất
      từ tier, không còn hằng số — grep khẳng định
- [ ] `deep` mặc định `enabled = false`; bật được bằng một dòng ở server
- [ ] Cột "tier đã dùng" đọc từ `agent_turn` (revision phase 08); **không** dùng
      `draft_content`
- [ ] Bước 3 có **số đo ghi lại**, và quyết định số tier dựa trên số đó
- [ ] `balanced` cho hành vi **y hệt** hiện tại (test hồi quy: không truyền tier
      → 4 vòng / 6 external call)
- [ ] `resolve` test bảng 6 giá trị xanh; giá trị lạ → mặc định, không raise
- [ ] `GET /tiers` chỉ trả tier `enabled`; tắt một tier ở server → nó mất khỏi UI
      **không cần** deploy web
- [ ] Ba tier cho **cùng tập tên tool** trong `agent_tool_call`; chỉ số lượng khác
- [ ] Tier đã dùng ghi lại được và khác tier mong muốn khi bị hạ (test có ca hạ)
- [ ] `PROMPT_VERSION` **không đổi**; grep khẳng định
- [ ] Cấu trúc vòng tool `loop.py` không đổi — chỉ hằng số thành tham số
      (diff review khẳng định)
- [ ] Menu tier đi được bằng arrow-key + Home/End + Escape
- [ ] Item không hiện tên model
- [ ] `make test` ≥1060 · `pnpm test` xanh

## Risk Assessment

**R1 cấp plan: tier là nhu cầu giả.** Đã đặt cổng đo ở bước 2, trước khi viết
UI — nên chi phí của việc R1 đúng là hai lần chạy thử, không phải một phase bỏ đi.
Phản ứng đã định và có thứ tự: (a) thu về hai tier; (b) nếu vẫn không khác biệt
thật thì hạ xuống label tĩnh honest (option B của quyết định 1 ở `plan.md`) và
báo lại — **không** giữ ba tier chỉ để control có chevron.

**Đổi hằng số thành tham số làm rò default.** Nếu một call site quên truyền thì
nó nhận default; nếu default viết sai thì mọi turn đổi hành vi im lặng. Tín hiệu:
test hồi quy bước 4 đỏ. Phản ứng: default **là** giá trị hiện tại, và test khẳng
định điều đó bằng con số cứng (4 và 6), không bằng cách đọc lại hằng số.

**Tier `deep` phá perf budget của plan Study.** Study đặt mốc "câu hỏi →
`canvas.ready` ≤8s store ấm". Sáu vòng tool sẽ vượt. Tín hiệu: smoke canvas ở
tier `deep` vượt mốc. Phản ứng đã định: mốc 8s là **của `balanced`**, không phải
của mọi tier. Ghi rõ điều này vào phase này và vào perf budget — một tier "sâu"
chậm hơn là đúng thiết kế, không phải hồi quy. Nhưng `balanced` vượt 8s thì là
hồi quy thật.

**Ngân sách: `deep` cho phép user tự tiêu envelope.** Ba tier × 30 turn/tháng của
lane Turn. `deep` tốn nhiều hơn nên envelope cạn sớm hơn. Tín hiệu: ledger. Phản
ứng: `deep` khai `status` riêng và tắt được ở server bằng một dòng — cơ chế
`enabled` đã có ở catalog chính vì lý do này.

Rollback: `resolve` luôn trả `balanced` là kill switch một dòng, đưa hành vi về
trước phase. Cột `research_tier` để nguyên (nullable, vô hại). FE revert độc lập.

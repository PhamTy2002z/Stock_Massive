---
title: "Deviation: Signal Desk visual mode, một Vnstock read tool, Flint chart core"
date: 2026-09-05
status: "ACCEPTED"
accepted_by: "product owner"
accepted_on: 2026-09-05
plan: "plans/260905-0001-signal-desk-visual-harness/"
authority_touched: ["CLAUDE.md", "docs/roadmap.md"]
---

# Deviation: Signal Desk visual mode, một Vnstock read tool, Flint chart core

`CLAUDE.md` §"Decision and Deviation Rules" xếp capability ngoài catalog vào
one-way door. Plan `260905-0001-signal-desk-visual-harness` mở ba capability
nằm ngoài catalog hiện tại, nên report này phải được owner chấp nhận trước khi
có dòng code nào.

## Quyết định cũ → evidence mới → amendment hẹp

| Quyết định cũ | Evidence mới | Amendment hẹp |
|---|---|---|
| Signal Desk output retired (`CLAUDE.md` §Retired Paths, roadmap Phase 0 §"Đã xóa") | Owner đã restore mode + pane ngày 2026-09-04 (`components/shell/composer.tsx`, `inspector.tsx`, `signal-desk/`). `flint-chart@0.5.1` có typed assembly input + compiler boundary, nên chart là dữ liệu đã validate chứ không phải code model sinh ra. | Mở **một** optional versioned visual part, render **chỉ** ở pane phải. Board renderer, Study/Board DSL, widget catalog, artifact rows, `signal_desk.ready`, board tab/pin/export vẫn retired. |
| Market-data SDK bị cấm (catalog runtime đúng năm tool) | Probe live 2026-09-04 (`plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`): KBS `Quote.history` FPT 5 rows ~1,0s; VCI trả cùng khoảng nhưng bỏ qua `start`; alias `va`; giá theo nghìn VND. Bounded read dùng được cho internal research. | Mở **một** provider-neutral read tool `get_market_data`, dataset **chỉ `ohlcv`**, một symbol/call, bounded rows. Availability chỉ khi profile `personal_internal` + flag + import check. Production/staging fail-closed dù có credential. Không indicator, store, scheduler, watchlist, order. |
| Phase 6 evidence là web-only | `_numbers_supported` đòi số phải xuất hiện đúng unit trong excerpt; `_temporal_valid` đòi `published_at`. Web search snippet không bảo đảm unit/time/provenance cho chuỗi giá — bằng chứng là chính probe: `72.5` là nghìn VND, timestamp naive 07:00. | Dùng `EvidenceKind.STORE_FIGURE` + `SourceClass.STORE` (đã có trong enum, chưa ai dùng). Web vẫn là narrative/primary source. |
| MCP chờ Phase 12 | Phase 2 import npm package `flint-chart` trực tiếp vào web app. | **Không amend.** Lệnh cấm generic MCP gateway giữ nguyên. |

## Trade-off phải nêu

**Chọn Flint thay `lieflat-charts` cho core.** Flint có ranh giới
assembly-input → compiler, tức host assemble input đã typed và validate, model
không gửi số nào. `lieflat-charts` chỉ là visual benchmark, không vào runtime.
Giá phải trả: phụ thuộc một package Microsoft ở `0.x`, API có thể drift. Chặn
bằng pin exact version + compile fixture trong CI + canary khi nâng.

**Từ chối agent loop thứ hai.** Đọc code cho thấy readiness gate
(`validate_claim_ledger`), state machine (`PipelineStage`), typed need
(`ResearchDraft.gaps`), refusal (`failed_ledger`), bound (`lanes.DEEP`) và
duplicate ladder (`TurnGuardrails`) **đã tồn tại**. Viết `readiness.py` thứ hai
là hai nơi định nghĩa "ready" và hai nơi để lệch nhau. Giá phải trả: không có
coverage digest bắt case "query khác, kiến thức như cũ" — chấp nhận được vì case
đó đã bounded bởi 10 round / 20 external call / 1.800s và terminate có reason
(roadmap §4: bound để dừng có lý do, không để tiết kiệm tiền).

**`SINGLE_SOURCE` là nhãn đúng, không nới `_PRIMARY_CLASSES`.** Số đến từ feed
KB Securities/Vietcap, không phải HOSE/HNX. Gọi nó `EXCHANGE` là dán nhãn sai
đường đi dữ liệu — đúng thứ `_PRIMARY_CLASSES` tồn tại để chặn. Đường lên
`VERIFIED` khi cần là cross-check hai publisher độc lập, `_accepted_verdict` đã
hỗ trợ sẵn.

## Giữ nguyên, không đụng tới

Truth contract (roadmap §2), one-call-one-result, typed Turn settlement,
permission/budget plane, thứ tự phase tuần tự, `mode=chat` là default
backward-compatible. Ngoài scope: Study/Board DSL, widgets, stock store,
scheduler, watchlist, broker/order, generic MCP, multi-agent, host shell,
file-write tool.

Paid quality gate còn lại của Phase 6 evidence engine chuyển vào Phase 7 của
plan này — không chạy hai corpus cạnh tranh.

## License boundary

Community `vnstock` là personal/research/non-commercial. Không suy ra quyền
Diamond từ LICENSE.md của bản community. Production chỉ GO sau khi có văn bản
bao phủ software license, quyền từng upstream source, SaaS/container/CI
identity, quota/SLA. Đến lúc đó, runtime gate là internal-only và production
hard-disabled.

## Rollback

Revert amendment trong `CLAUDE.md` + `docs/roadmap.md`; gỡ bundle `market_data`
và dependency; gỡ optional visual part. Signal Desk trở lại pane rỗng. Text và
web-evidence path không bị chạm ở bất kỳ bước rollback nào.

## Owner decision

- [x] **Chấp nhận** — ba amendment ở trên, đúng phạm vi đã ghi.
- [ ] Từ chối.

Product owner chấp nhận cả ba ngày 2026-09-05. `CLAUDE.md` và `docs/roadmap.md`
được sửa trong cùng commit với quyết định này.

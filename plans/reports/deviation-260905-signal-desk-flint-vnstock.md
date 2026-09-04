# Deviation: Signal Desk visual mode, một Vnstock read tool, Flint

**Ngày:** 2026-09-05
**Plan:** `plans/260905-0001-signal-desk-visual-harness/`
**Trạng thái:** chờ quyết định của product owner — **không có dòng code nào được
viết trước khi report này được chấp nhận**
**Vì sao cần:** `CLAUDE.md` xếp "capabilities outside the catalog" vào one-way
door. Ba capability dưới đây nằm ngoài catalog hiện tại, và `docs/roadmap.md`
cùng `CLAUDE.md` hiện **không nhắc** `signal_desk`, `get_market_data` hay
`Flint` ở bất kỳ đâu ngoài một dòng board announcement đã retired.

## Amendment đề nghị

| Quyết định cũ | Evidence mới | Amendment hẹp |
|---|---|---|
| Signal Desk output retired | Owner đã restore mode + pane ngày 2026-09-04; Flint có typed assembly/compiler boundary, npm `flint-chart@0.5.1` verified 2026-09-05. | Mở **một** visual part optional ở pane phải. Board, Study DSL, widget, artifact table, `signal_desk.ready` announcement vẫn retired. |
| Market SDK prohibited | Live probe Vnstock Community: OHLCV bounded dùng được cho internal research (`plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`). | Mở **một** read-only `get_market_data`, dataset `ohlcv`, internal profile only, production fail-closed. |
| Phase 6 evidence là web-only | Số thị trường cần unit/time/provenance mà web search không bảo đảm. `EvidenceKind.STORE_FIGURE` và `SourceClass.STORE` đã có trong enum, chưa consumer nào dùng. | Thêm `STORE_FIGURE` evidence. Web vẫn là nguồn narrative/primary. |
| MCP chờ Phase 12 | Phase 2 import npm package trực tiếp trong vitest. | **Không amend** — lệnh cấm generic MCP giữ nguyên. |

## Trade-off phải nêu

1. **Chọn Flint làm visual core**, không phải `lieflat-charts` (chỉ dùng làm
   benchmark thị giác). Đổi lại: phụ thuộc một package Microsoft phải pin và
   canary khi upgrade; bù lại là typed assembly input có validator, thứ một DSL
   tự viết sẽ phải làm lại từ đầu.
2. **Từ chối agent loop thứ hai.** Readiness dùng lại `validate_claim_ledger`,
   `PipelineStage`, `TurnGuardrails`, `lanes.DEEP` — không viết module
   readiness, coverage digest hay state machine mới. Đổi lại: không tối ưu được
   round lãng phí kiểu "query khác, kiến thức như cũ" cho tới khi corpus Phase 7
   đo được nó.
3. **Host tự assemble chart, model không đề xuất.** Với một dataset và hai hình
   dạng chart deterministic, model draft không quyết định gì. Đổi lại: chart
   không linh hoạt theo ý người đọc; nâng cấp là cho model chọn *kind* (không
   bao giờ chọn *data*).
4. **Số market ra `SINGLE_SOURCE`, không phải `VERIFIED`.** `SourceClass.STORE`
   không thuộc `_PRIMARY_CLASSES`, và đó là nhãn đúng: số đến từ feed KB
   Securities/Vietcap, không phải HOSE/HNX. Report nghiên cứu của chính dự án
   ghi "Không được trả lời 'nguồn chính thức' chỉ vì Vnstock đã normalize row".
   **Không nới `_PRIMARY_CLASSES`** — đó là thay đổi truth contract, một
   one-way door riêng. Đường lên `VERIFIED` khi cần là cross-check hai provider
   độc lập, cơ chế `_accepted_verdict` đã hỗ trợ sẵn.

## Giữ nguyên, không nằm trong amendment

Truth contract (roadmap §2), one-call-one-result, typed Turn settlement,
permission/budget plane, thứ tự phase tuần tự, `mode=chat` là default
backward-compatible.

Ngoài scope: Study/Board DSL, widget catalog, stock store, scheduler, global
watchlist, broker/order execution, generic MCP, multi-agent, side-effect tool,
host shell, file-write tool.

Paid quality gate còn lại của Phase 6 evidence engine chuyển vào Phase 7 của
plan này — không chạy hai corpus cạnh tranh.

## Deployment và license

Vnstock Community chỉ bật ở profile `personal_internal`. Production/staging/
shared SaaS **fail-closed dù có credential**. Mở chúng cần một deviation riêng
kèm quyền phần mềm và quyền dữ liệu upstream (KBS, VCI, MAS…) bằng văn bản.
Vnstock là technical connector, không trao quyền dữ liệu nguồn.

## Rollback

Revert amendment: pane Signal Desk trở lại empty state, `get_market_data` gỡ
khỏi toolset, visual part optional gỡ khỏi message content. Không mất
capability nào đang chạy; engine text/evidence deploy được suốt quá trình.

Trace và ledger đã ghi vẫn là evidence lịch sử theo retention policy — xoá dữ
liệu là một quyết định migration riêng, không phải phần của rollback này.

## Nếu được chấp nhận

Sửa `CLAUDE.md` và `docs/roadmap.md` trong **cùng một commit** để hai file khớp
nhau về capability, thứ tự phase và stop condition. Kiểm bằng:

```bash
rg -n 'signal_desk|get_market_data|Flint' CLAUDE.md docs/roadmap.md
```

Roadmap hiện vẫn ghi cả Signal Desk bị tear down (Phase 0, §"Đã xóa") và chưa
được amend; amendment này là chỗ sửa nó.

## Nếu bị từ chối

Đóng plan `260905-0001-signal-desk-visual-harness`. Không viết code. Pane Signal
Desk giữ empty state như hiện tại.

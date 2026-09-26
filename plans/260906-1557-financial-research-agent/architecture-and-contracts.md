# Kiến trúc và hợp đồng đề xuất

Tài liệu thiết kế cho plan, không phải contract production hiện hành. Paths bên dưới tương đối với `/Users/typham/Dev/Stock_Massive`.

## Một runtime, nhiều loại bằng chứng

```text
User question + attachments + optional visual mode
  → existing durable Turn + resolved capabilities + permission/budget
  → requirement frame (entity, cutoff, job, material questions)
  → existing research loop
       → web search: discover
       → fetch_url: HTML/PDF/document retrieval
       → structured read: entitled market/filing datasets
       → session/memory: owner-scoped context, never market truth
  → evidence + typed financial observations
  → counterevidence → clean-context verifier + deterministic validation
  → bounded gap-directed retrieval if justified and budget remains
  → durable claim ledger + coverage outcome
       → memo + evidence cards + optional host-bound Flint visual
       → thread dossier, explicit memory consent
```

Các mũi tên mới được ghép vào `AgentLoop`, `PipelineStage`, `ToolExecutor`, `TurnBudget` và persistence hiện có. Không thêm orchestration service/state machine song song. Light lane vẫn dùng cho câu hỏi đơn giản; mọi external material claim phải qua cùng grounding policy hoặc được route vào deep lane.

## Những seam hiện có cần bảo vệ

| Owner | Hợp đồng hiện có / consumer phải rà |
|---|---|
| `agent/router.py`, `schemas.py`, `turns.py` | CreateTurnRequest extra-forbid, attachment resolution, mode/lane, cancel, SSE; client `lib/alpha-desk/api.ts`, `types.ts` |
| `agent/registry.py`, `toolsets.py`, `executor.py` | Một đăng ký/dispatch, availability khác permission, schema/resource validation trước I/O |
| `agent/evidence/contracts.py` | EvidenceRef, EvidenceLocation, DraftClaim, VerifiedClaim, ClaimLedger; consumer pipeline/ledger/documents/persistence/visual/golden |
| `agent/evidence/pipeline.py` | research draft, evidence_from_calls, candidate_ledger, verifier_messages; consumer loop và tests |
| `agent/persistence.py`, `alpha/models.py` | Thread/Turn/tool call/evidence cache/claim ledger; không thêm market store hoặc artifact DB |
| `agent/visual.py`, web `lib/flint/compile-visual.ts` | Host input→Flint official compiler; web read-content/desk state/panel và golden graders |

Trước mỗi thay signature: tìm toàn bộ caller ở commit thực hiện, ghi inventory vào phase report và sửa atomically; các seam ở đây là owner đã tìm thấy, không phải danh sách caller hoàn chỉnh của code tương lai.

## Observation tài chính

Mở rộng evidence contract hiện có bằng observation payload typed, không sao chép cả evidence thành hệ thống mới. Trường đề xuất:

| Nhóm | Trường / quy tắc |
|---|---|
| Identity | observation ID, evidence ID, entity ID/ticker và tên pháp nhân; ticker chỉ là alias có hiệu lực theo thời gian |
| Metric | original label, normalized metric, value dạng decimal string; null khác 0 và dấu gạch thiếu số |
| Unit | currency, unit, scale; source value và normalized value; đổi đơn vị host-side một lần |
| Period | period start/end hoặc instant date, fiscal year, quarterly/YTD/annual, consolidated/separate |
| Provenance | source document/version/hash; page/bounding box hoặc sheet/cell range; extractor version; OCR confidence nếu có |
| Validity | published/available time, retrieved time, audit/review status, reported/restated, supersedes ref khi có |

Không đoán period/basis từ việc hai số đứng gần nhau. Unknown là giá trị hợp lệ nhưng làm mất khả năng so sánh/khẳng định tương ứng. Banks/insurance dùng metric phù hợp; không áp mẫu công nghiệp lên mọi ngành. Cell locator không có trong PDF thì dùng page + span/bounding box thật, không bịa tọa độ.

## Financial derivation — D4 phải được duyệt

Reuse `EvidenceKind.CALCULATION`. Record gồm operation allowlisted, ordered operand observation IDs, evaluator version, output unit/currency, rounding, result decimal, source lineage. Model có thể đề xuất operands/operation; host resolve, kiểm tương thích và tự tính. Không nhận Python/JS/SQL/expression tùy ý và không dò mọi phép tính để hợp thức hóa một số.

Operations ban đầu phục vụ corpus: chênh lệch, tổng hữu hạn, tỷ trọng, YoY/QoQ tương thích, Q4=FY−9M cùng basis, normalized price return/index-base và benchmark difference. Zero/negative denominator, lỗ→lãi, missing periods phải có kết quả không áp dụng hoặc wording riêng. Balance-sheet instant không cộng như flow. Derived result không có mức tin cậy cao hơn input; hai phép tính cùng input không thành hai nguồn độc lập.

## Verification và completeness là hai trục

- Semantic support của claim đối với source là điều kiện cần. Mechanical checks kiểm ID/location/time/unit/lineage và chỉ giữ hoặc hạ trạng thái; nguồn primary không chữa được claim verifier bác bỏ.
- Mỗi material requirement và draft claim đều được accounted: supported, conflicting, unverified, unavailable hoặc excluded có lý do. Omitted verifier claim không được biến mất khỏi denominator.
- Claim `fact/inference/scenario`, materiality và source confidence không do model tự quyết để vượt policy; host dùng quy tắc conservative với số/tác động trọng yếu.
- Observation time không phải retrieval time. Một tài liệu truy xuất hôm nay có thể dùng cho câu hỏi lịch sử chỉ khi phiên bản chứng minh được đã có ở cutoff. Restatement mới không được backdate.
- Nguồn primary và independence có provenance: một báo dẫn IR không tự nâng cả trang thành primary; nhiều báo dẫn cùng IR chỉ có một origin.
- Assumptions, gaps, invalidations, titles và annotations cũng không là cửa đưa số/URL không nguồn ra UI.
- Turn COMPLETE là settlement kỹ thuật. Task complete/partial/insufficient là outcome riêng, không đổi ngầm terminal enum hay SSE semantics.

## Retrieval, context và storage

URL discovery trả locator và publication hints; fetch nhận bytes qua WebLane/SSRF/redirect/size/time/quota hiện có. MIME + magic bytes chọn HTML hoặc document parser. Parser chạy bounded worker/process để CPU/memory/time được giới hạn thực; timeout async không được để CPU worker tiếp tục vô hạn.

Parser text có trước; tài liệu scan/mixed pages dùng OCR fallback có gate chất lượng và quyền gửi dữ liệu. Bảng được giữ headers và coordinates; chunks theo page/section/table, không cắt mất label/unit. Full content ở evidence store hoặc private attachment store; prompt chỉ nhận phần liên quan và refs. Cache key gồm content/version/parser + time window + rights scope, không trộn private/public. Chỉ URL public có quyền cache mới share; user file không tự trở thành public vì nội dung giống tài liệu web.

Snapshot evidence/visual phục vụ replay khác cache tăng tốc. TTL cache không được âm thầm phá citation của memo đang giữ. Chốt retention và hành vi expired/unavailable; rights revocation phải chặn serve lại, gồm replay. Không hứa lưu raw vĩnh viễn. Mọi migration cần backup và restore drill; prefer additive payload versions, dual-read/one-write, feature flag rollback.

## Tool surface đề xuất

Giữ web_search/fetch_url/session_search/remember_fact/recall_facts. Mở rộng `get_market_data` theo manifest dataset đã được duyệt, hoặc thêm tool hẹp chỉ khi schema khác bản chất (ví dụ filings lookup) và D3 đã mở catalog. Không expose toàn SDK; tool descriptions nói rõ coverage/time/unit/quyền, trả lỗi typed no_data/unavailable/rate_limited/schema_drift/access_denied. Provider fallback chỉ dùng nguồn có cùng semantics và entitlement; luôn ghi nguồn thật.

## User flow

1. User hỏi hoặc gửi báo cáo; thấy nguồn đang đọc và các mục cần kiểm, không thấy thông tin implementation.
2. Hỏi lại tối đa theo elicitation budget hiện có, chỉ câu trả lời làm đổi kết luận; skip vẫn chạy với giả định rõ.
3. Memo mở bằng kết luận/cutoff, các premise verdict, facts/inference/scenario, phản chứng và mục theo dõi.
4. Click claim mở evidence đúng page/cell/span; conflict giữ cả hai, số tính mở operands/formula.
5. Signal Desk hiển thị visual liên quan tới câu hỏi, nguồn/thời gian/basis, bảng thay thế accessible. Không có dữ liệu thì giải thích thiếu gì; không thay bằng chart không liên quan.
6. F5/reconnect/thread switch không rerun research hoặc show chart cũ như chart Turn mới. Dossier rerun là Turn mới; bản cũ bất biến.

## Không khóa trước khi có probe

Vendor dữ liệu, OCR engine, raw document storage backend và sandbox runtime chưa được lựa chọn. Phase sở hữu phải ghi lựa chọn dựa trên corpus/rights/performance; không thêm dependency chỉ vì tên công nghệ phổ biến.

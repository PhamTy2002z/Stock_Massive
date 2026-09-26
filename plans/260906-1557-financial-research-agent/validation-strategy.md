# Validation strategy và acceptance matrix

Kế hoạch kiểm thử cho implementation, chưa phải kết quả test. Reuse `apps/api/golden`; không có harness eval thứ hai. Phase W1 khóa mọi soft threshold trước candidate run. W1–W10 là work package của plan, khác số phase trong roadmap.

## Corpus và ground truth

Giữ toàn bộ release corpus hiện có; thêm tối thiểu 20 câu đại diện theo bảng. Số 20 là đề xuất tối thiểu cho coverage, không đủ để tuyên bố accuracy cho mọi doanh nghiệp. Mỗi case có requirement IDs do reviewer xác định, answerable status, material facts/locators, cutoff/source version, valid interpretations, expected missing/conflict behavior. Không hardcode một văn mẫu làm golden answer.

| Family | 4 case khởi đầu | Bằng chứng bắt buộc |
|---|---|---|
| BCTC/chất lượng lợi nhuận | YoY; khoản một lần; CFO vs LNST; hợp nhất/restatement | Báo cáo + notes, kỳ/basis/unit, exact cells/pages |
| Tin/sự kiện | KQKD; thay đổi quản trị; dự án/pháp lý; tin sau giờ đóng cửa | Primary CBTT/IR hoặc nguồn độc lập, publication time |
| Thông tin ngách | Backlog/sản lượng; công ty con; nguyên liệu/khách hàng; related-party | Entity linkage, ngành/period, provenance, explicit unavailable |
| Phản ứng thị trường | Sau công bố; so benchmark; corporate action; đình chỉ/gap | Series đúng basis/cửa sổ/cutoff, event timestamp; causal uncertainty |
| Stress-test/mâu thuẫn | Hai số lệch; rumor; thiếu nguồn; nhiều tiền đề | Evidence cho từng premise, counterevidence, origin và gaps |

Thêm adversarial transformations cho cùng evidence: đổi entity/kỳ/metric/unit, ngày tương lai, restatement mới, 2 bài copy 1 origin, verifier omitted/timeout/semantic rejection, chart sửa 1 số/ref, wrong-owner file, revoked entitlement. Mutation là negative test, không dùng làm fake runtime data. Fixture của source phải là snapshot được phép giữ hoặc mẫu test rõ provenance; không commit secrets/private documents.

## Metric không trộn lẫn

| Metric | Denominator | Gate |
|---|---|---|
| Mechanical provenance integrity | Toàn bộ numeric/URL/ref được hiển thị trong memo/chart/annotations | 100% trên fixture/golden được khai applicable; unknown ID/lineage = fail |
| False verified states | Negative verifier/time/unit/source fixtures | 0 trên suite; không suy rộng thành semantic accuracy tuyệt đối |
| Material fact accuracy | Human-labeled material facts trong corpus | Ngưỡng theo baseline W1 + human review, báo CI và số mẫu |
| Requirement fulfillment | User-requested requirements của answerable cases | Ngưỡng W1 từng family; không cho model tự giảm denominator |
| Correct refusal/disclosure | Cases được ground truth xác định insufficient/conflicting | 100% disclosure hard policy; refusal đúng không tăng fulfillment cho answerable case |
| Extraction accuracy | Labeled material cells và document types | Ngưỡng W1; exact value/unit/period/locator, không chỉ text similarity |
| Temporal/source rights | Applicable cutoff/entitlement test cases | 0 leakage/forbidden serve trên suite |
| Replay/settlement | Turn/event/visual scenarios | 100% invariant suite; 0 orphan/double terminal |
| Cost/latency | Successful tasks, thêm breakdown partial/failed | Report p50/p95/model/data/OCR cost; existing envelopes remain enforced |

Thresholds chưa khóa là **blocking requirement của W1**, không thể bắt đầu thay behavior lớn và chọn ngưỡng sau. Hard policy không được nới để pass. Dòng BLIND/skipped không pass. Incomplete artifact fail release dù phần đã chạy xanh.

## Commands hiện có

Chạy từ repo root, project environment theo Makefile. Narrow suite dùng tên file thực tế; test mới chỉ chạy sau khi phase tạo nó.

```bash
make -C apps/api test-one T=tests/test_agent_evidence_contract.py
make -C apps/api test-one T=tests/test_agent_document_evidence.py
make -C apps/api test-one T=tests/test_agent_market_data.py
make -C apps/api test-one T=tests/test_agent_evidence_pipeline.py
make -C apps/api test-one T=tests/test_agent_memory_tools.py
make -C apps/api test
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test
pnpm --dir apps/web build
git diff --check
```

Full commands áp dụng khi shared/public contracts thay đổi và trước release, không chạy toàn bộ sau mỗi dòng sửa. Python phải là project environment; nếu shell chưa activate thì dùng `apps/api/.venv/bin/python` khi có. Frontend E2E command phải đọc package scripts ở commit thực hiện; không giả định Playwright script hiện có.

Paid release chỉ sau user cấp amount và trials; placeholder dưới đây **không phải giá trị mặc định**:

```bash
make -C apps/api golden-release CEILING_USD=<approved-amount> TRIALS=3
make -C apps/api golden-grade ARTIFACT=<existing-artifact-path>
```

`golden-grade` đọc artifact không dùng model/network/database theo Makefile. Release grade-only dùng existing CLI nếu cần full release dimensions; xác minh help/schema artifact trước khi chạy. 3 trial là đề xuất cần owner chấp thuận, không permission chi tiền.

## Gating theo phase

| Work package | Offline gate | Live/human gate | Exit artifact |
|---|---|---|---|
| W1 | Corpus/graders + baseline fault fixtures | Paid baseline + ground truth + Signal handoff | Decisions + baseline manifest |
| W2 | Contract mutations + old/new replay | Semantic/cutoff human spot-check | Policy/contract report |
| W3 | URL/upload/parser/OCR/security integration | Official filing sample, labeled cells | Extraction coverage matrix |
| W4 | Dataset normalizer/rights/cache/mode | Entitled provider canary, rights evidence | Source manifest |
| W5 | Decimal/units/basis/derivation lineage | Finance truth set, paired eval | Calculation evidence + metrics |
| W6 | Planner/recovery/context/cancel | Per-family fulfillment improvement | Paired research evaluation |
| W7 | Typed UI/chart/compiler/replay/a11y | Real Turn, mid-flight refresh/thread switch | Visual artifact + screenshots |
| W8 | Consent/owner/delete/stale/injection | Recall uplift, consent flow | Memory privacy report |
| W9 | Full regression/fault/backup restore | Release trials + human holdout + beta window | Release manifest, rollback drill |
| W10 | Branch-specific invariants | Trigger/uplift/load benchmark | Opened/rejected decision |

## End-to-end acceptance examples

1. Hỏi chất lượng lợi nhuận quý gần nhất → đọc BCTC và notes → số báo cáo/derived tách riêng → kết luận với phản chứng → chart relevant nếu có → click source đúng trang → F5 cùng memo/chart.
2. Hỏi vì sao cổ phiếu giảm → nguồn tin + price/benchmark đúng cửa sổ → không lấy split như loss; không khẳng định nhân quả nếu chỉ có đồng thời.
3. Gửi PDF scan riêng → được cảnh báo phần đọc thiếu khi OCR kém → evidence chỉ owner thấy → user xóa/withdraw → cached recall và replay không lộ dữ liệu đã bị thu hồi.
4. Hai nguồn lệch doanh thu vì consolidated/separate → trình bày cả hai basis, không lấy trung bình; chart chỉ compare compatible basis.
5. Hỏi ngách không có nguồn → ghi đã tra gì, thiếu gì và cách bổ sung; không bịa câu trả lời để nâng coverage score.

## Process/resource discipline

Trước chạy server/worker: kiểm tra owner của port/process, reuse nếu đúng task. Ghi command/PID/port/worktree và stop process mình tạo khi kiểm thử xong. Parser/OCR/sandbox cancel phải chấm cả process termination, không chỉ HTTP response. Không kill process của người dùng để đạt gate.

## Review và measurement limits

Planner review chỉ xác minh thiết kế/caller/source; không thay thế unit/E2E/live eval. Mọi source findings chưa có failing fixture ghi hypothesis cần kiểm. Statistical accuracy cần human-labeled cases và đủ samples; 100% mechanical gate không phải cam kết dự báo hay tin cậy tuyệt đối của publisher.

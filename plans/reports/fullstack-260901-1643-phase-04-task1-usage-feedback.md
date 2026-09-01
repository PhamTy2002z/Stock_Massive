# Việc 1 — usage token thật quay lại quyết định context

Ngày 2026-09-01, nhánh `feat/phase-04-context-engine`.

## Đã sửa

- `apps/api/src/agent/messages.py`
  - `UsageFeedback(real_input_tokens, estimate_at_real)` — hai trường, mặc định
    `0/0`. `project(est) = max(0, real + est - estimate_at_real)`; mặc định zero
    làm projection **bằng** ước lượng nên không có nhánh "chưa đo".
    `bias = real / estimate_at_real` hoặc `None`.
  - `ContextComposition` thêm `projected_tokens` + `estimate_bias`. `total` vẫn
    chỉ cộng 7 layer; `as_dict()` không đổi (replay/artifact không vỡ).
    `plus()` dịch `projected_tokens` đúng bằng số token append vào — khoảng cách
    giữa hai phép đo là tính chất của *call đã đo*, không phải của note vừa thêm.
  - `ConstructedContext` thêm `rung` (chỉ số nấc của `_reductions`, 0 = nguyên).
  - `build_messages(transcript, budget, feedback=None)` — ceiling so với
    **projection**; `feedback=None` cho đúng context như trước (replay, test
    thuần, `golden/context_replay.py` không đổi).
  - `ConstructedContextTooLarge` mang số đã quyết định (projection), = ước lượng
    khi chưa đo.
- `apps/api/src/agent/loop.py`
  - `_TurnState.last_real_input_tokens` + `estimate_at_last_real`,
    `observe_input(usage, estimated)`, `feedback()`.
    `real = input_tokens + cached_input_tokens` (cached vẫn là token model đọc);
    `usage is None` → giữ số đo cũ, không coi là 0 (cùng lý lẽ `add_usage`).
  - Ghi ngay sau `_complete` thành công, với `composition.total` = ước lượng của
    **chính** messages vừa gửi (gồm note append). Ghi trước nudge: call rỗng vẫn
    là call route đã đọc.
  - `_construct` truyền `state.feedback()` xuống `build_messages`.
  - `_pruned(...)` phát `context_pruned` một lần mỗi construct **thật sự nhường
    đất**, tại đúng chỗ context được dựng cho call sắp gửi. Không phát từ
    rebuild thử trong `_compress` (đó là câu hỏi, không phải context ai gửi),
    không phát khi context vừa khít (vừa khít không phải sự kiện).
- `apps/api/src/agent/parts.py`
  - `ProgressKind.CONTEXT_PRUNED`; allowlist
    `(rung, turns_dropped, results_collapsed, estimated, projected, layers)`.
  - `NUMERIC_MAP_FIELDS = {"layers"}`: mapping chỉ đi lọt trên key đã khai báo
    **và** mọi value phải là số (bool loại trừ). Mapping ở key khác vẫn bị chặn
    y như cũ. Payload copy `dict(value)` thay vì giữ tham chiếu.
- `apps/web/src/lib/alpha-desk/types.ts` + `read-content.ts`: thêm
  `"context_pruned"` vào union và vào `PROGRESS_KINDS`. Chỉ hai dòng — reader
  drop kind lạ, nên chỉ sửa union thì part bị vứt im lặng. Không có UI mới:
  chưa component nào vẽ progress theo kind.

## Test

- Backend: **1283 → 1295 passed** (`cd apps/api && pytest -q`), 3 deselected,
  không test nào bị nới.
- Mới trong `tests/test_agent_loop.py` (8): projection = ước lượng khi chưa đo;
  projection = số thật + delta ước lượng; ước lượng **thấp** vẫn phải nhường đất
  khi route đã lên tiếng; ước lượng **cao** thôi cắt khi route nói ngược lại;
  `plus()` dịch cả hai phép đo; số route trả quyết định call kế tiếp trong loop
  thật (A/B cùng script, cùng ceiling, khác mỗi `usage`); payload
  `context_pruned` toàn số, `sum(layers) == estimated`, không chứa câu nào của
  transcript; context vừa khít không phát part.
- Mới trong `tests/test_agent_parts.py` (4): payload đủ 6 key; breakdown chứa
  text bị drop, part vẫn publish; chỉ `layers` được mang mapping; mapping được
  copy.
- Sửa 1 test có sẵn: `test_a_compression_that_ran_is_reported_once_with_its_bound`
  giờ ghim trail đúng 6 phần tử (thêm 2 `context_pruned` — hai construct thật đã
  xảy ra). Vẫn là so sánh bằng, không nới.
- `python -m compileall -q apps/api/src apps/api/golden apps/api/tests` sạch.
- Web: `lint`, `type-check`, `test` (458), `build` xanh
  (`E2E_NEXT_DIST_DIR=.next-verify` để không đụng `.next` của dev; đã revert
  `next-env.d.ts` mà Next tự ghi và xoá `.next-verify`).
- `git diff --check` sạch. Không tham chiếu Signal Desk/Study mới.

## Quyết định đáng ghi

1. **Không nhánh "chưa đo"** — mặc định `0/0` khiến `project()` là hàm đồng nhất.
   Đường code một nhánh đúng như thiết kế §1 yêu cầu.
2. **Admission vẫn reserve trên ước lượng** (`SpendRequest.input_tokens =
   estimated + reserved`), không đổi. Ước lượng giữ vai backstop preflight;
   projection chỉ quyết định *dựng context*.
3. **`rung` thêm vào `ConstructedContext`** vì payload cần chỉ số nấc và
   `_reductions` trước đó không lộ ra. `enumerate` trên ladder, không đổi ladder.
4. **Mapping vào allowlist theo key + theo value.** Cho phép mapping số chung
   chung là mở cửa cho payload sau này mang text dưới key thứ hai; khoá theo tên
   key giữ tính "structural, not remembered" mà module tự tuyên bố.
5. **`estimate_bias` để ở composition** (không log) vì P9 cần đọc sai số bằng số
   đo thật; `as_dict()` giữ nguyên chỉ-layer nên artifact cũ không đổi shape.

## Câu hỏi mở / rủi ro

- **`ConstructedContextTooLarge` vẫn thoát khỏi `_call` không được bắt** (chỉ
  `_compress` bắt). Với feedback, một route báo số thật lớn hơn nhiều ước lượng
  có thể làm construct giữa Turn chạm nấc cuối và ném lỗi này ra
  `TurnService` → settle `incomplete/turn_failed`, **mất phần trả lời dở**.
  Điều kiện xảy ra: bias × (prompt + câu hỏi cuối, đã collapse hết) > ceiling —
  đo trên corpus hiện tại thì prompt ≈ 53% ceiling nên cần bias ≳ 1,8. Đây là lỗ
  có sẵn (transcript quá lớn ngay call đầu cũng ném thế), nay dễ chạm hơn. Sửa
  đúng là biến nó thành terminal `context_overflow` — **ngoài phạm vi việc 1**,
  đề nghị gộp vào việc 5 (gate "overflow hội tụ bounded").
- `observe_input` bỏ qua `usage` rỗng. Nếu một route nào đó **luôn** trả usage
  rỗng, Turn chạy hoàn toàn trên ước lượng như hôm nay — an toàn, nhưng lặng.
  Chưa thêm cảnh báo vì chưa có ngưỡng nào để báo động cho đúng.
- Phần web chỉ mới nhận `context_pruned` vào state; chưa surface nào vẽ nó (P7).

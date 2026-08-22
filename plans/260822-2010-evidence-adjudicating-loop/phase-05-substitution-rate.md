---
phase: 5
title: "Substitution rate"
status: pending
---

# Phase 5 — Substitution rate

## Lớp lỗi đang mở

Bộ eval đã bị xoá ở `1974c24`. Không còn cổng đo nào cho PR chạm agent loop, tool schema hay
prompt. Nếu Phase 4 land mà không có phép đo thì "phân tích tốt hơn" là ý kiến.

Và không có gì để bê: khảo sát Hermes xác nhận nó **không có grader nào** —
`batch_runner.py` chỉ sinh trajectory + `tool_stats`, `verify/runner.py` chỉ chấm build/test
xanh, và `agent/battery.py` là bộ đọc pin laptop chứ không phải eval harness.

## Đo đúng cái vòng lặp thêm vào

Loop thêm đúng một hành vi: gặp figure `refused`, đi tìm cái thay thế dùng được. Nên phép đo
là chính hành vi đó.

**Substitution rate** = trong các Analysis mà seed có ≥1 figure `refused`, tỷ lệ Analysis mà
model đã gọi `get_field` cho một field khác và cite được kết quả `ok`/`degraded` của nó.

Đọc được từ ba nguồn đã có sau Phase 2 và 4, không cần bảng mới:

| Thành phần | Nguồn |
|---|---|
| seed có figure `refused` nào, mã gì | `analysis.payload → evidence`, `health`/`reasonCode` |
| model đã xin field nào, nhận gì | `analysis_tool_call.arguments` / `.result` |
| verdict tựa lên field nào | `analysis.payload → citedFieldIds` |

Ba đại lượng, tất cả 0 lời gọi LLM:

1. **Substitution rate** — như trên. Đây là con số chính.
2. **Round hữu ích** — tỷ lệ tool call trả `ok`/`degraded` trên tổng tool call. Round xin một
   field rồi nhận `refused` là round đã tiêu; tỷ lệ này nói trần round đặt đúng hay không.
3. **Tỷ lệ figure được dẫn** — bao nhiêu figure `ok`/`degraded` được `citedFieldIds` dẫn, trên
   tổng. So với mốc one-shot của Phase 1. Nếu loop mang về nhiều figure hơn nhưng tỷ lệ dẫn
   tụt, nó đang mua dữ liệu nó không dùng.

Đại lượng 3 là bản đo được của cùng ý tưởng Hermes gắn vào payload tool
(`degraded = bool(active_filters) and not citations`): phân biệt "có câu trả lời" khỏi "có câu
trả lời được chống bởi bằng chứng".

## Vì sao không phải forward return

Forward return là bar đúng cho **verdict**, và nó vẫn là bước tiếp theo. Nhưng nó không đo
được bây giờ, vì hai lý do độc lập:

- Chưa có verdict thật nào (`alpha_desk_enabled = False` tới Phase 1).
- Cửa sổ chấm phải ≥3 phiên vì sàn T+2 — `docs/research/quant-methods-eod-vn.md` §0: không
  tín hiệu horizon dưới ~3 phiên nào round-trip được. Thực tế cần 5 và 20 phiên, tức ~1 tháng
  sau khi Phase 1 chạy.

Và nó cần một thứ chưa có: **hàm chi phí giao dịch VN**. Tài liệu domain không định nghĩa cái
nào — nó chỉ nêu gián tiếp qua reject list (Gatev: trễ 1 ngày mất 38% lợi nhuận; Lehmann: lợi
nhuận là bid-ask bounce). `stocks/signals/fields.py:417` bắt `Claim.PREDICTIVE` phải đứng sau
*"a measured net-of-cost forward-return harness"* — chữ **net-of-cost** đó hiện không có số.

Substitution rate đo được từ phiên đầu tiên và đo đúng thứ Phase 4 thêm vào. Đó là phép đo
đúng cho v1.

## Thay đổi

### `alpha/analysis_reads.py`

Ba hàm đọc, mỗi hàm một truy vấn, tham số là khoảng Trading Day. Không view, không bảng
tổng hợp: ở ≤30 mã × 21 phiên thì đây là vài trăm row.

### Ops

Một endpoint đọc, cùng khuôn `agent/ops.py`. Không dashboard, không alert, không ngưỡng
cứng — xuất **số thô** và để người đọc quyết định, đúng khuôn Hermes cho monitoring
(*"không có boolean healthy toàn cục, không ngưỡng cứng"*).

## Validation

- Test: Analysis mà seed không có figure `refused` nào **không** vào mẫu số của substitution
  rate. Chia cho tổng số Analysis là một con số vô nghĩa.
- Test: Analysis không có tool call nào (model không gọi gì) mà seed có `refused` → tính là
  substitution **thất bại**, không phải bỏ khỏi mẫu.
- Test: cả ba đại lượng chạy trên khoảng ngày rỗng trả 0 chứ không lỗi.
- `make test` pass.

## Risk / rollback

Chỉ đọc. Rollback là xoá endpoint.

Rủi ro thật là đọc sai con số: substitution rate cao **không** chứng minh phân tích đúng — nó
chứng minh vòng lặp hồi phục được khỏi bằng chứng thiếu. Hai điều khác nhau, và forward return
mới trả lời điều thứ hai. Ghi cảnh báo đó ngay cạnh con số, không để trong plan.

## Việc kế tiếp, ngoài plan này

Sau ~20 phiên có verdict thật: forward-return ledger (verdict × horizon 5/20 × return đã điều
chỉnh corporate action × so với VN-Index — chuỗi benchmark đã lưu bền qua
`Capability.MARKET_INDEX`), attribution về `citedFieldIds`, và chỉ khi đó mới bàn mở
`Claim.PREDICTIVE`. Cần hàm chi phí giao dịch trước.

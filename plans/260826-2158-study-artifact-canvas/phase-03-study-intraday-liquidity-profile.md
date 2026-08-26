# Phase 03 — Study `intraday_liquidity_profile` v1

Nhóm A. Phụ thuộc 01 (contracts) + 02 (bars).

## Context

Case flagship của `docs/idea.md`. Trả lời: "thanh khoản của <mã> tập trung
vào khung giờ nào trong N phiên gần nhất?". Chính `idea.md` chỉ đúng metric
cần: không dùng volume tuyệt đối một mình — thêm **liquidity share** =
bucket_volume / session_total để phiên volume lớn không làm lệch, và **spike
frequency** để phân biệt "lặp lại ổn định" với "vài phiên đột biến" (lý do
heatmap là hero visualization).

## Requirements

Params (model điền): `symbol` (declared Universe — ngoài → refusal typed),
`sessions` (default 30, clamp 10–60), `metric` (`volume|value`, default volume).

`compute` (thuần pandas trên `reads.bars_for`, KHÔNG gọi provider):

- Mỗi bucket: avg volume, median volume, avg liquidity share, spike frequency
  (bucket là top-2 của phiên trong bao nhiêu / N phiên).
- Rank cửa sổ thanh khoản; peak window + occurrence.
- `min_sample`: < 10 phiên có dữ liệu → `no_value:insufficient_sessions`
  (khớp vốn từ refusal hiện có — thêm câu ở `alpha/reasons.py` **và**
  `apps/web/src/lib/signal-issues.ts` theo luật CLAUDE.md).

`headline` (model thấy, ≤300 token):

```json
{"symbol": "STB", "sessionsUsed": 30, "peakWindow": "14:15",
 "peakAvgVolume": 4800000, "peakShare": 0.186, "peakOccurrence": "21/30",
 "top3": [...], "phaseSummary": {"ato": ..., "am": ..., "pm": ..., "atc": ...}}
```

`frames` (model KHÔNG thấy): `profile` (series: bucket → avg vol, share),
`heatmap` (matrix: 30 phiên × ~17 bucket, giá trị = share chuẩn hoá),
`ranking` (table: top cửa sổ).

**Missing-bucket policy (audit N9):** dữ liệu thật có phiên thiếu bucket
(probe: min 56/96 raw). Cột heatmap align theo grid phiên chuẩn; bucket thiếu
= `null` = ô "không có dữ liệu" (màu riêng ở widget), **không phải 0** — 0
nghĩa là "không ai giao dịch", là một khẳng định sai. Liquidity share
normalize theo tổng các bucket thực có của phiên đó.

`view` → CanvasSpec 4 block: `stat_tiles` (peak/avg/occurrence) ·
`bar_series` (profile) · `session_heatmap` (heatmap) · `ranked_bars` (ranking).

## Files

- `src/studies/intraday_liquidity.py` — definition + compute + view
- `tests/studies/test_intraday_liquidity.py` — golden test trên fixture bars
  cố định (30 phiên synthetic có spike biết trước); test refusal ngoài
  Universe; test min_sample; test headline size (serialize < 1.500 chars)
- `alpha/reasons.py`, `apps/web/src/lib/signal-issues.ts` — câu cho
  `insufficient_sessions` (nếu mã chưa có)

## Steps

1. Fixture: sinh 30 phiên synthetic, spike cắm ở 14:15 với tần suất 21/30 —
   golden test khẳng định compute tìm lại đúng.
2. Compute + view; đăng ký vào `studies.registry`.
3. Kiểm import-time: view tham chiếu đủ 3 frame; widget names nằm trong
   danh mục widget đã khai (hằng chia sẻ — phase 05 đọc cùng nguồn).

## Validation

- Golden test xanh; property test nhỏ: tổng liquidity share mỗi phiên ≈ 1.0.
- Smoke thật: chạy runner với STB → headline khớp số probe đã đo (top bucket
  thuộc {14:45, 14:00, 14:15} theo dữ liệu hiện tại).

## Risk & rollback

- Sai lệch định nghĩa spike (top-2 vs z-score): chốt top-2 cho v1, ghi trong
  docstring; đổi định nghĩa = bump `version=2`, không sửa v1. Rollback: gỡ
  đăng ký study, không đụng schema.

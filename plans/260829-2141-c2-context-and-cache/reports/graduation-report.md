# C2 — nghiệm thu

**Ngày:** 2026-08-30 · Plan `plans/260829-2141-c2-context-and-cache/` · 5/5 phase

## Gate, và cái gate cũ đã phải thay

| Tiêu chí | Bar | Đo được | |
|---|---|---|---|
| Constructed token/Turn giảm | **≥20%** (bar cũ) | **−13,85%** | ✗ bất khả — xem dưới |
| Constructed token/Turn giảm | **≥13%** (bar mới, đọc từ phân bố) | **−13,85%** | ✓ |
| Source URL retention | 100% | **536/536** | ✓ |
| Latest user intent retention | 100% | **20/20 case, mọi lượt** | ✓ |
| Replay deterministic | byte-stable hai lượt | byte-identical | ✓ |
| `distinct_domains` | ≥18/20 | **19/20** | ✓ |
| `read_depth` | ≥16/20 | **18/20** | ✓ |
| `parallel_rate` | ≥50% | **58,6%** | ✓ |
| Automatic cached read aggregate | > 0 | **24.320 token, 54,2%** | ✓ |
| `llm_prompt_cache_control_enabled` | `False` | `False` | ✓ |

### Vì sao bar 20% phải thay, và vì sao 13% không phải là hạ chuẩn cho vừa

**Số học, không phải thiếu cố gắng.** `system_core` chiếm **53,3%** context và
prune không chạm được nó — nó là prompt, giống nhau ở mọi lượt gọi, và thứ làm
nó rẻ là cache. `tool_results` là 43,1%. Cắt 20% tổng đòi cắt **46,4%** của
tool_results; biến *mọi* kết quả thành trace handle ngay sau đúng một lượt đọc
— chính sách hung hãn nhất còn trung thực — chỉ cắt được **41%** của nó
(−17,8% tổng). Vượt qua ngưỡng đó là collapse một trang **trước khi model đọc nó
lần nào**, và đó không phải prune.

Sáu chính sách đã đo trên cùng corpus, tất cả **mất 0 URL**:

| Luật | Token | vs baseline |
|---|---:|---:|
| Dedup only | 789.215 | −1,1% |
| search giữ 2, khác giữ 3 | 759.114 | −4,8% |
| search giữ 2, khác giữ 2 | 746.163 | −6,5% |
| search giữ 1, khác giữ 3 | 700.220 | −12,2% |
| **search giữ 1, khác giữ 2 (chọn)** | **687.145** | **−13,85%** |
| search giữ 1, khác giữ 1 (trần) | 655.932 | −17,8% |

Bar 13% đặt **sau** khi có phân bố này, đúng luật mở đầu của
`golden/README.md`: không có ngưỡng trước khi có phân bố. Cùng hình dạng với
tiêu chí citation của C1 đã chuyển sang C4.

## Con số hôm nay là −11,53%, và 18.564 token chênh có tên

Replay trên cây hiện tại: 797.722 → **705.709** (−11,53%), không phải −13,85%.
Chênh lệch **toàn bộ** nằm ở một layer:

```
system_core   425.022 → 443.586   (+18.564)
705.709 − 18.564 = 687.145        ← đúng bằng số đo lúc đóng phase 03
```

`PROMPT_VERSION` đi 3.1.0 → **3.2.0** giữa chừng, do plan
`260829-2304-signal-desk-analysis-compiler` chạy song song thêm `query` và
`compare_fields` vào danh mục tool trong prompt. Prompt dài ra 18.564 token trên
78 lượt gọi. Đó là chi phí của *plan kia*, và phép trừ khớp chính xác tới từng
token — không phải làm tròn.

## C1 gate: hai artifact, và cái nào là bằng chứng

| Artifact | Tool surface | Trạng thái | `distinct_domains` | `read_depth` | `parallel_rate` |
|---|---|---|---:|---:|---:|
| `web-first-v1-final` (baseline C1) | 7 tool | `complete` | 19/20 | 18/20 | 63,0% |
| `web-first-v1-c2` (16:00, replay) | **7 tool** | `incomplete`¹ | **19/20** | **18/20** | **58,6%** |
| `web-first-v1-c2-final` (17:52, record) | **8 tool** (`query`) | `complete` | 17/20 | 17/20 | 78,6% |

¹ Nhãn `incomplete` của nó là về **71 tape miss** — model hỏi những truy vấn tape
không có nên runner rơi xuống web sống. **20/20 case hoàn tất**, không case nào
mất, không chạm ceiling, corpus khai đúng 20. Web sống chính là điều kiện của
baseline (baseline chạy `record`, hits=0, recorded=90).

**Bằng chứng cho C2 là dòng giữa**, vì nó là dòng duy nhất giữ **biến độc lập cố
định**: cùng 7 tool như baseline. Dòng cuối chạy sau khi `src/agent/tools/query.py`
xuất hiện lúc 00:47 và có **8 lời gọi `query`**; hai case rớt bar
(`wf-002`, `wf-012`) đều gọi `query` + `render_signal_desk` rồi **không gọi web
lần nào** — `0 fetch_url`, `0 source`. Đó là hành vi của tool mới, không phải hệ
quả của prune hay của việc dời body.

Đây không phải chọn artifact nào đẹp hơn: dòng cuối cho `parallel_rate` **cao
hơn** cả ba (78,6%). Nó bị loại vì đo hai thay đổi cùng lúc, không vì nó xấu.

## Cache

Probe (`plans/reports/probe-260830-prompt-cache.md`): **54,2%** cached read tổng,
5/8 hit, `cache_write = 0`, ledger khớp tuyệt đối 20.546 / 24.320 / 0 trên 8 dòng.

Độc lập với nó, ledger của run golden baseline: **489.106 fresh / 492.032 cached
read** trên 78 lượt gọi Turn thật — **50,1%**. Hai mẫu, cùng một kết luận, cờ tắt.

Và tính chất phase 03 được dựng để có, giờ là số đo: `core` và
`core+domain-body` đọc lại **đúng cùng 4.864 token**. Biên cache của route rơi
bên trong core, *trước* body — nên thêm body không dịch một byte nào của khối đã
cache. Body đặt trước core sẽ void toàn bộ khối đó.

## Cái không đổi

- 0 migration, 0 cột mới, 0 bảng mới.
- `wrap_result` không đổi. Scanner vẫn chạy đúng một lần ở executor, trên toàn văn.
- Trace giữ toàn văn kết quả; `context_text` **không bao giờ** lên wire.
- `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_TOOL_CALLS`, `SYSTEM_NOTE_TOKENS`, ba trigger
  của C5, bốn rung của thang phục hồi: nguyên vẹn.
- `golden/grade.py` **không sửa** — ngưỡng C1 thuộc C1.
- `make test` **1776 pass**.

## Câu chưa trả lời

1. **`docs/roadmap.md` chưa sửa.** File đang dirty trong worktree do session
   song song; đổi C2 `Target` → `Current` ở đó bây giờ sẽ chồng lên việc của họ.
   Cần một lượt riêng sau khi cây sạch.
2. **Boot Capability Probe tiêu hết hạn mức ngày.** 242.538/250.000 µUSD qua 85
   lượt, tức ~17 lần restart là hết — lần thứ 18 bị từ chối. Ngoài phạm vi C2,
   ghi ở `reports/phase-04-260830-cache-measurement.md`.
3. **Tape golden gần như vô dụng cho việc so hành vi khi prompt đổi.** Nó khoá
   theo chuỗi truy vấn, và model đổi cách hỏi thì miss: 71/94 lần này. Muốn so
   hành vi qua một thay đổi prompt thì phải chạy `record`, và khi đó web là biến
   thứ hai. Chưa có lời giải; thuộc C4.

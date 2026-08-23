# Audit: bộ tool đọc chỉ báo — độ sâu thật, và chuẩn Hermes

Ngày 2026-08-23. Nhánh `develop`. Kiểm bằng chạy code thật trên DB đang lên
(`docker compose exec api`), không suy từ docstring.

Tham chiếu bắt buộc đã đọc: `docs/hermes/hermes-synthesis-260821-0030.md`,
`hermes-tools-260820-2352.md`, `hermes-route-subagent-260820-2352.md` §1.1.

---

## 1. Triệu chứng đo được

151 lời gọi `get_field` trong `agent_tool_call`:

| Kết quả | Số | % |
|---|---|---|
| Có giá trị | 94 | 62% |
| Refused (`value: null`) | 42 | 28% |
| `cannot_read` | 15 | 10% |

Một lượt thật (09:23:11): 18 lời gọi → **1** có số.

Trạng thái ghi trong DB cho cả 151: `status = ok`.

## 2. Nguyên nhân gốc — đã chứng minh

### 2.1 `FACTOR_MIN_SESSIONS = 1` làm chết fallback market cap

`cross_sectional.py:159` đặt `FACTOR_MIN_SESSIONS = 1`. `serve_field` gọi
`prepare_bars(window_days=1)` → frame có **đúng 1 bar**.

`_market_cap` (`cross_sectional.py:328-333`) lặp `reversed(frame.bars)` như thể
có chỗ để lùi. Không có. Đo:

```
bars 1 min_sessions 1
  2026-08-21 mcap None
_market_cap -> None
```

Vòng lặp fallback là **dead code**.

### 2.2 Provider ghi market cap rất thưa

`provider_snapshots`, capability `market`: **130 / 67.658 dòng** có
`market_cap_vnd` (0,19%), trên đúng 5 phiên (2026-08-10 … 2026-08-20), 30 mã.
Phiên mới nhất `2026-08-21` **không có mã nào**. Nguồn: `fiinquant.py:828`
`_cell(overview, "marketcap")`.

VHM có market cap 570.930.268.556.000 ở phiên 2026-08-20, và `null` ở 2026-08-21.
Vì §2.1, cái ở 08-20 không bao giờ được đọc.

### 2.3 Ba trong bốn factor percentile chết, dưới hai mã lý do sai

VHM, phiên 2026-08-21:

| Field | value | reasonCode |
|---|---|---|
| `book_yield_percentile` | null | `fundamental_not_stored` |
| `earnings_yield_percentile` | null | `fundamental_not_stored` |
| `roe_percentile` | **93,33** | — |
| `size_percentile` | null | `missing_target_session` |

ROE chạy được chứng minh BCTC **có** trong store (8 dòng, kỳ 2026-06-30). Cả ba
cái chết đều dùng `_market_cap`; ROE không dùng.

Câu mà model đọc, `alpha/reasons.py:161`:

> "The store holds no quarterly statement for this symbol at or before this session."

Câu này **sai sự thật**. Nguyên nhân thật là market cap thiếu ở phiên đích.
`_quarterly_ratio` (`cross_sectional.py:361-380`) gộp 3 nguyên nhân khác nhau
(không có statement / thiếu dòng trong statement / thiếu market cap) vào **một**
mã. `size_percentile` gọi cùng nguyên nhân đó là `missing_target_session` —
phiên có, market cap không có.

### 2.4 Store đã giữ sẵn câu trả lời, ở capability khác

Capability `valuation` (fiinquant): `provider_pb` và `provider_pe` **30/30 mã,
mọi phiên**, gồm phiên mới nhất. VHM: `provider_pb = 2,2675` → book yield
= 100/PB = **44,1%**. Đúng con số đang bị từ chối. Không field nào hỏi tới.

### 2.5 Sàn cross-section bằng đúng kích thước Universe → dung sai bằng không

`CROSS_SECTION_MIN_SYMBOLS = 30` (`cross_sectional.py:164`), Universe = 30 mã.
Một mã trượt là cả bảng xếp hạng trượt, cho mọi mã.

Đo momentum percentile, phiên 2026-08-21:

```
universe 30  ranked 27  refusal INSUFFICIENT_CROSS_SECTION
excluded {MCH: insufficient_history, TCX: insufficient_history, VPL: insufficient_history}
```

MCH/TCX/VPL không đủ 252 phiên (TCX và VPL mới có 7 dòng bar). Nên **mọi phân vị
động lượng, cho mọi mã, đang chết vĩnh viễn** — không phải chuyện của VHM.

Hạ sàn xuống 20, giữ nguyên mọi thứ khác:

```
momentum_rank.percentile_12_2  ranked 27  refusal None
VHM = 92,6  {formation_return_pct: 40,34, n: 27, excluded_symbols: 3, as_of: 2026-08-21}
```

Một figure thật, có `n` và `excluded_symbols` đóng dấu ngay trong extras — cơ chế
khai báo mẫu **đã có sẵn**, chỉ bị cái sàn chặn trước khi kịp dùng.

### 2.6 Tầng trạng thái che hết

`_cannot()` (`signals.py:462`) **return** dict thay vì raise → `executor.py:356`
đặt `ok=True`. Figure `health=refused` cũng là payload trả về bình thường. Nên
`agent_tool_call.status` không phân biệt được "đọc được số" với "đọc xong không
có gì". 38% mù.

---

## 3. Chuẩn Hermes — theo cái gì, lệch cái gì

### Theo

| Bài học Hermes | Nguồn | Áp vào đây |
|---|---|---|
| Guard **fail-open**: được phép chậm, rẻ, ồn — không được làm trắng màn hình | synthesis §1 | §2.3: thiếu một input phụ đang xoá cả figure |
| Taxonomy lỗi phân theo **nguyên nhân**, mỗi nhánh mang hành động phục hồi, catch-all là hố đen | `FailoverReason`, route-subagent §1.1; synthesis phát hiện #2 | §2.3: một mã cho ba nguyên nhân, và mã đó nói sai |
| Thứ tự phân loại là **ưu tiên tuyệt đối**, đảo thứ tự là tái tạo bug cũ | `classify_api_error` 8 tầng | Phân loại refusal phải xét "input nào thiếu" trước "họ nhà nào thiếu" |
| Ngưỡng không nên là hằng số tuyệt đối — **scale + clamp + floor** | tools §3 bài học 2 | §2.5: sàn 30 trên Universe 30 |
| Không phân loại được thì không phục hồi được → làm tầng chẩn đoán **trước** | synthesis §4 tầng 0 | §2.6 |
| Progressive disclosure chỉ đáng khi catalog phình | tools §3 bài học 5, §5 | Catalog 8 tool, đóng → **không** thêm tool search |
| Cấu trúc registry/toolsets của ta đã KISS hơn, không cần port | tools §4 cuối | Độ sâu đến từ **field**, không từ thêm tool entry |

### Lệch có chủ ý

- **Không** port thang `block`/`halt` đầy đủ của `tool_guardrails.py`. Ta đã có
  `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_TOOL_CALLS`, `admit_round`. Thêm state machine
  song song là hai nguồn sự thật về "khi nào dừng" (tools §5 nói thẳng).
- **Không** port pipeline phân loại nhiều tầng có hook plugin. Chỗ gán refusal của
  ta là **một** call site (`_quarterly_ratio`); cần tách mã, không cần pipeline.
- **Không** port spillover 3 tầng cho hai tool này. `signals.py:80` đã ghi lý do:
  figure ~730 byte, cả catalog ~22KB, `MAX_RESULT_CHARS = 32.000` là bug-stop
  chứ không phải budget. Đó vẫn đúng.

---

## 4. Bốn nước đi đề xuất, xếp theo ROI

### M1 — Hạ sàn cross-section thành hàm của Universe *(cao nhất)*

`CROSS_SECTION_MIN_SYMBOLS` hằng số 30 → `clamp(fraction × len(sample), [floor, ...])`.
Hồi sinh phân vị động lượng cho **cả 30 mã** (đã kiểm: VHM = 92,6, n = 27).
`n` và `excluded_symbols` đã đi kèm figure nên người đọc thấy mẫu mỏng hơn.

Đây là sửa **một quyết định đã ghi** — cần chốt fraction/floor, không tự đặt.

### M2 — Tách mã refusal theo input thiếu

`_quarterly_ratio` trả ba mã khác nhau thay vì một:
`statement_not_stored` · `statement_line_missing` · `market_cap_absent_on_session`.
Mỗi mã một câu trong `reasons.py` nói đúng cái thiếu, và nói được cái **còn đọc
được** (ROE không cần market cap). `size_percentile` dùng chung mã thứ ba, bỏ
`missing_target_session`.

### M3 — Thang thay thế fail-open cho market cap

1. Market cap của phiên gần nhất **có** một cái, đóng dấu ngày riêng +
   `degraded_reason` (sửa luôn `FACTOR_MIN_SESSIONS = 1` để `_market_cap` có chỗ lùi).
2. Nếu vẫn không có: dẫn xuất từ `valuation.provider_pb` (30/30 mã, mọi phiên),
   đóng dấu rõ đây là tỷ số **provider tính**, không phải số học của ta.
3. Hết đường mới refuse, bằng mã thật của M2.

Bước 2 là quyết định sản phẩm, không phải tối ưu kỹ thuật: nó đưa một con số
provider-computed vào figure. Cần chốt.

### M4 — Trạng thái phân biệt "đọc" với "đọc ra số"

`agent_tool_call` mang outcome có cấu trúc: `value` / `refused:<code>` /
`cannot_read`. Rail hiện nó ra. Không có bộ eval nào (đã xoá 2026-08-22) nên
outcome theo từng lời gọi là cái bar duy nhất dựng được rẻ.

---

## 5. Về "sâu và niche"

Độ sâu hiện tại một phần là **hư cấu**: 30 field đăng ký, nhưng 3 factor chết
thường trực và mọi phân vị động lượng chết vĩnh viễn — 4/30 field không bao giờ
trả số ở phiên mới nhất. Sửa M1–M3 hồi lại độ sâu **đã trả tiền** trước khi thêm
field mới.

Hai chỗ nông thật, không phải bug:

- **Ngành**: `field_profile.py:235-246` khai `developer_metrics.net_debt_to_ebitda`
  và `inventory_share_of_assets_pct` cho REAL_ESTATE, cả hai **không có trong
  Signal Registry** → Analysis in ra `unavailable`, lane chat không thấy. VHM là
  developer mà không có chỉ báo developer nào.
- **Universe trong prompt**: lượt 09:23 tiêu 15/18 lời gọi để học rằng NVL, DXG,
  PDR, NLG, KDH ngoài Universe. `prompt/sections.py:113` nói "một mã trong
  Universe" nhưng không liệt kê mã nào. 30 ticker là ~150 byte trong prefix ổn
  định — và theo synthesis phát hiện #4, prefix đó mới là chỗ đáng đặt.

Cách thêm độ sâu **không** phải thêm tool entry: `get_field` đã với tới 30 field
bằng một schema, và Hermes §5 nói rõ tool search chỉ đáng khi catalog phình.

---

---

## 6. Đã thi công (cùng phiên, 2026-08-23)

Quyết định của người dùng: M1 sàn `clamp(0,6 × mẫu, floor 15)` · M2 · M4 · M3
**chỉ bước 1** (sửa cửa sổ market cap, **không** dùng `provider_pb`).

| Nước đi | Thay đổi |
|---|---|
| M1 | `PERCENTILE_MIN_SAMPLE_SHARE = 0.6` + `PERCENTILE_ABSOLUTE_FLOOR = 15` + `min_sample_for()` trong `signals/fields.py`. Xoá `CROSS_SECTION_MIN_SYMBOLS` **và** `ADTV_MIN_PEERS` — hai hằng số đều là 30, mỗi comment tự nhận là "cùng một sàn" với cái kia và không gì kiểm. Giờ là một luật |
| M2 | Ba mã mới trong `SignalIssue`: `statement_line_missing` · `market_cap_absent` · `stale_market_cap`. `_quarterly_ratio` phân biệt theo input thiếu; `denominator=None` nghĩa là chia cho vốn hoá. `size_ranked` bỏ `missing_target_session`. Câu tiếng Anh ở `alpha/reasons.py`, câu tiếng Việt ở `web/src/lib/signal-issues.ts` |
| M3.1 | `SignalField.lookback_sessions` tách khỏi `min_sessions`; `serving.py` hỏi `field.window_sessions`. Factor khai `FACTOR_LOOKBACK_SESSIONS = 21`, sàn vẫn 1 phiên. `_market_cap` trả về cả bar; `_stamped` nhận `priced_on` và đóng dấu `price_session` + `window_session`. `EvidenceFigure.window_days` giờ là cửa sổ, không phải sàn |
| M4 | `agent_tool_call.outcome` (migration `b7f4e9c21a08`, additive nullable, không backfill). `messages.outcome_of()` đọc payload có cấu trúc; executor ghi vào trace entry; `TurnToolCall.outcome` ra wire; rail hiện "Không có số" / "Ngoài phạm vi" kèm câu **Signal Issue** trong `title` |

### Đo lại — VHM, phiên 2026-08-21

| | Trước | Sau |
|---|---|---|
| `momentum_rank.percentile_12_2` | refused `insufficient_cross_section` | **92,59** (n=27, excluded=3) |
| `factor_percentiles.book_yield_percentile` | refused `fundamental_not_stored` | **46,67** degraded `stale_market_cap` |
| `factor_percentiles.earnings_yield_percentile` | refused `fundamental_not_stored` | **76,67** degraded `stale_market_cap` |
| `factor_percentiles.size_percentile` | refused `missing_target_session` | **96,67** degraded `stale_market_cap` |
| `liquidity_profile.adtv_percentile` | refused `ranking_unavailable` | **96,30** ok |
| Cả 30 field | 4 chết thường trực | **ok=23 · degraded=5 · refused=2** |

Hai field còn refused là chủ ý và tự nói ra:
`relative_strength.beta_vs_market_index` (không có benchmark trong store) và
`foreign_flow_pressure.net_volume_over_adtv` — `unavailable` kèm `missing_input`
mô tả đúng cái thiếu và `available_instead` trỏ sang field chạy được. Đúng khuôn
mà M2 vừa đưa các factor về.

### Cổng nghiệm thu

- `make test`: **2487 passed**, 1 failed — `test_deployment_topology.py::test_the_topology_is_written_down_where_the_next_reader_will_look`, đòi `docs/streaming-topology.md` đã xoá ở `b352417`. Fail có sẵn, CLAUDE.md đã ghi, không phải hồi quy
- Web: `pnpm type-check` · `lint` · `test` (**474 passed**) · `build` — pass
- Backup trước migration: dump DB Docker (7,1 MB) và DB test trên host, trong scratchpad phiên

### Test mới

`test_cross_sectional.py`: vốn hoá không ai ghi ≠ báo cáo thiếu (cùng symbol,
cùng statement, ROE vẫn trả lời) · statement thiếu dòng · vốn hoá phiên cũ
degrade và đóng dấu cả hai ngày · một mã ngắn lịch sử không còn giết cả bảng xếp
hạng · sàn tính theo mẫu **được hỏi** chứ không theo mẫu sống sót.
`test_agent_signal_tools.py`: từ vựng `outcome_of`, và trace entry mang nó.
`test_agent_persistence_paths.py`: `ok` + rỗng cùng lúc, mã refusal sống sót
vòng ghi/đọc. `reasoning-timeline.test.tsx`: rail nói ra, đúng câu, và để yên
call có số.

### Chưa làm

M3 bước 2 (`provider_pb`) — người dùng chọn không. Hệ quả còn lại: phiên nào cả
cửa sổ 21 phiên không có vốn hoá thì ba factor vẫn refuse, giờ dưới mã đúng
`market_cap_absent`.

---

## Câu hỏi chưa giải quyết

1. M1: fraction và floor tuyệt đối là bao nhiêu? `0,6 × len(sample)` với floor 15?
2. M3 bước 2: có cho `provider_pb` vào figure không? Nếu có, `source` khai là gì —
   `stored`, hay một giá trị mới `provider_derived`?
3. Market cap thưa 0,19% là lỗi ingest `fiinquant.py:828` hay provider thật sự
   chỉ trả overview theo phiên? Chưa kiểm tầng provider.
4. Hai field `developer_metrics.*`: đăng ký thật, hay bỏ khỏi profile? Đăng ký cần
   dòng BCTC (nợ vay, EBITDA, tồn kho, tổng tài sản) — chưa kiểm store có chưa.
5. ~~`FACTOR_MIN_SESSIONS = 1` là chủ ý hay sót?~~ Trả lời bằng cách tách hai khái
   niệm: sàn vẫn 1 phiên (chủ ý — factor chỉ cần một giá), cửa sổ thành 21.
6. `PERCENTILE_MIN_SAMPLE_SHARE = 0.6` không có bằng chứng thống kê nào đằng sau.
   Nó là một lựa chọn có dung sai, không phải ngưỡng đo được. Universe phình thì
   xét lại bằng số.
7. Cửa sổ 21 phiên là dung sai, không phải cách sửa: mọi factor hiện degraded vì
   provider chỉ ghi vốn hoá 0,19% số dòng. Sửa gốc nằm ở tầng ingest.

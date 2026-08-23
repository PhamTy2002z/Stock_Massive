# Đề xuất kiến trúc cuối — VisgniteAI

Bản 2, viết lại sau merge `cf8b41c` (evidence-adjudicating loop). Bản 1 sai ở ba chỗ
và được sửa tường minh ở §2. Mọi số là số đo trên DB `stockmassive` hoặc đọc từ code,
không phải số trích từ trang pricing.

Khung không đổi:

> **Hardening cái đã có → thêm primitive còn thiếu (Context) → chiếu state cá nhân
> lên intelligence dùng chung (Portfolio) → sau cùng mới đến transport (Realtime).**

---

## 1. Năm invariant

1. **Đường phục vụ request là store-only** — enforce ở runtime bằng
   `core/provider_access.py::store_only_execution()`.
2. **Provider chỉ gọi từ collector/ingestion**, qua một arbiter Redis
   (`core/quota.py`), fail-closed.
3. **Backend sở hữu mọi số hiển thị.** `alpha/production.py`: envelope verbatim
   dưới `evidence`; model góp prose, thứ tự nhấn, danh sách id.
4. **Stock Intelligence dùng chung**, keyed `(symbol, trading_day)`, immutable.
5. **Trading Day định nghĩa bằng dữ liệu, không bằng đồng hồ** (`alpha/nightly.py`).

---

## 2. Ba chỗ bản 1 đã sai

**a) D1 nói "resolve server-side để né ADR §79".** ADR đó đã được quyết theo hướng
ngược lại: `CHAT_TOOLSETS = ("web", "memory", "signals")`, và `signals` cho model đọc
store thật (`list_fields`, `get_field`, `check_price_claim`). Nên lý do "né để ship
nhanh" không còn. Nhưng **context chip vẫn chưa tồn tại** — hai thứ bổ sung cho nhau
chứ không phải hai lựa chọn: chip trả lời "user đang xem cái này" (deterministic,
0 token), `get_field` trả lời "model cần thêm field nào" (mở, tốn round).

**b) Bản 1 lập luận Analysis lane nên là one-shot enveloped.** Lane giờ là loop, và
loop có lý do đo được: **16 field chưa bao giờ tới được một Analysis**, và **47,7 %
figure dùng được không được dẫn** — kể cả `price_zone.ordinary_range_pct`, 0/8 lượt.
Đó là lỗ chất lượng thật, không phải tối ưu hoá. Giữ loop.
Lưu ý: ledger cho thấy `analysis_run` vẫn **16 call / 16 owner** — loop đã dựng nhưng
chưa thực sự lặp trên production.

**c) Bản 1 nói "đừng đọc capacity từ token".** Đúng, nhưng lý do mạnh hơn tôi viết:
cả hai trial đều trả `per_minute/hour/day/month = 0`. Chỉ `end_date`/`enabled` dùng
được — đã implement.

---

## 3. Hermes: kết luận giữ nguyên, có bằng chứng

`docs/hermes/hermes-synthesis-260821-0030.md` đã kết luận và tôi đồng ý: **không bê
khung.** Hermes là coding agent terminal (7 sandbox backend, 40+ tool shell/file/git,
TUI, gateway đa nền tảng); không tool nào của nó đọc được store này.

Đáng học đúng hai thứ, cả hai đã xử lý:

- **Guard fail-OPEN** — được phép chậm, rẻ, ồn; không được phép trắng màn hình.
  Đã implement, năm phase (`0d1fadc`, `3be54b0`).
- **Nudge tổng hợp có trần** khi model sai hợp đồng, thay vì kết thúc Turn.

**Không port:** subagent/MoA, skills tự sinh, fallback 7 tầng provider, native
compaction, và đặc biệt **không chèn ký ức free-text vào system prompt** —
`contract.py::_assert_no_formatting_hole` cấm mọi free-text và đó là hàng rào chống
injection; đi qua tool, đừng phá hàng rào.

**Một phát hiện ngược đáng giữ:** Hermes **không có bộ chấm chất lượng đáp án nào**.
`batch_runner.py` chỉ sinh trajectory, `verify/runner.py` chỉ chấm build/test xanh.
Nên "biết mình dở ở đâu" là thứ **không thể port** — xem §7.

---

## 4. Ba hằng số đã lệch calibration — sửa trước tiên

Nhóm mới, rẻ nhất, đang gây lỗi thấy được trên màn hình.

**`MAX_CALLS_PER_ROUND = 8`** (`agent/executor.py:96`). Lý do của số 8, ghi trong
code: suy ra từ **trần 6 call rời deployment**. Nó được calibrate cho bộ tool chỉ
gồm `web` + `memory`, nơi fan-out lớn là bệnh lý vì mỗi call là một request ra
internet. Nhưng `get_field` là **đọc Postgres của chính mình** — không rời
deployment, không tốn quota, không tốn tiền. Đọc 20 chỉ báo của một mã *chính là*
hình dạng hợp lệ của câu "phân tích MWG". Quan sát trực tiếp: model xin ~25
`get_field`, 8 chạy, phần đuôi trả `round_fanout_exceeded` → UI hiện "Không chạy".

**`MAX_TOOL_ROUNDS = 4`** (`agent/loop.py:158`). Khảo sát Hermes (#3) đã ghi:
docstring cùng file nói "Eight tool-call rounds per Turn", và 4 round cho câu cần
scope→search→fetch→store→tính là rất chật. Giờ store read cũng ăn round.

**Cộng lại:** một Turn trần 4 × 8 = 32 call, mà riêng catalog của một mã đã muốn
25+. Turn đang bị chặn bởi một hằng số suy từ ràng buộc không còn áp dụng, không
phải bởi ngân sách.

**Đề xuất:** đếm trần theo cái thật sự khan hiếm — call **rời deployment**. Giữ
`MAX_EXTERNAL_TOOL_CALLS = 6`; cho store read một trần riêng, rộng bằng cỡ catalog
một mã. Codebase đã có sẵn sự phân biệt cần dùng: `PARALLEL_SAFE_TOOLS` nói rõ
*"'reads the open web' and 'changes nothing' are different properties"*. Thiếu đúng
một tập "không rời deployment" để trần fan-out đếm theo.

---

## 5. Chi phí và cache — đã đo, và kết luận cũ của tôi sai

Số đo trên `llm_call_usage`:

| owner | call | owner | avg in | avg out | USD |
|---|---|---|---|---|---|
| `turn_request_message` | 627 | 228 | 3.331 | 216 | **6,291** |
| `analysis_run` | 16 | 16 | 3.509 | 266 | 0,036 |
| `capability_probe` | 398 | 370 | 286 | 19 | 0,347 |

→ **$0,0276 mỗi Turn** (2,75 call/Turn) · **$0,0033 mỗi Analysis** one-shot.
Cả hai theo `LLM_PRICING_VERSION=2026-08-dev-cliproxy` ($0,5/$1,0 per Mtok) —
**giá proxy dev, không phải giá production.**

Bản 1 viết "cache là đòn bẩy lớn nhất, đã dựng xong, chỉ chờ bật một cờ". **Sai.**
Đo trực tiếp (`plans/reports/measurement-260823-1238-prompt-cache-on-cliproxy.md`):

- Route là OpenAI-shaped nên **cache đã tự động chạy**, không cần `cache_control`.
  Lane Turn đang được cache **57,6 %** (`gpt-5.6-terra`, 442 call).
- `cache_control=True` được route **nhận** nhưng **không đổi gì**. Nên
  `llm_prompt_cache_control_enabled` phải **giữ `False`** — bật lên chỉ thêm một
  field của Anthropic vào request hình dạng OpenAI.
- Cache bám **đầu** prompt: block chung đứng trước → 95,2 % cached và dùng chung
  được xuyên mã; phần riêng đứng trước → 0 %.
- Ngưỡng tối thiểu **≈ 2048 token**, bước 128. Dưới ~1900 thì không bao giờ cache.
- **Hit là best-effort:** 3/8 call liên tiếp cùng prefix mới hit. Proxy phân tải
  qua nhiều instance, mỗi cái một cache. Nên cache chỉ được tính vào ngân sách
  theo *tổng*, không theo từng call.

**Lane Analysis 0 % không phải lỗi cấu hình.** Thứ tự message đã đúng
(`generation.py:387`: `SYSTEM_PROMPT` trước, envelope sau); `SYSTEM_PROMPT` chỉ
**~436 token**, dưới xa ngưỡng. Chạy bao nhiêu lần cũng không cache được.

Kéo theo hai chỗ nữa phải sửa lại: khảo sát Hermes **#4** đúng ở dữ kiện
(`cache_control` không được set) nhưng sai ở suy luận ("trả giá đầy đủ mỗi Turn");
và baseline `phase-01` ("loop 4 round nhân input ~4× trước cache") quá bi quan —
round 2 trở đi mang cả message của round 1 nên đã vượt ngưỡng và sẽ cache
best-effort.

**Không nhồi `SYSTEM_PROMPT` cho dài quá 2048 token để chạm ngưỡng.** Đó là trả
thêm token trên đường miss để mua một cái hit best-effort, và làm phình prompt vì
lợi ích của cache chứ không vì lợi ích của câu trả lời.

## 6. Observability — bản 1 chỉ sai chỗ, nhưng có một lỗ thật

Bản 1 viết "`analysis_run.error_code` lưu *state* thay vì *reason*, nên không biết
trần nào đã nổ". **Sai cả hai nửa.**

`FAILURE_CODES` (`producer.py:30`) là taxonomy **riêng** của pipeline Analysis;
`budget_exhausted` là thành viên hợp pháp có chủ đích, và comment ở đó giải thích
vì sao nó không được gộp vào `llm_transport_error` (vu cho một route chưa hề được
gọi) hay `auth_unavailable` (cái đó pause route để sửa credential; hết hạn mức thì
chờ sang tháng).

Và `reason` **đã được ghi từ trước**: `generation.py::budget_failure()` đặt
`refusal.reason` vào `error_message`, vì đúng lý do bản 1 nêu — *"a prompt over the
per-call input ceiling arrives here as `analysis_input_per_call`, and calling that
'out of budget' would send an operator to the ledger instead of to the envelope
that grew."*

Nên câu hỏi mở "trần nào đã nổ ngày 17–18/08" trả lời được ngay bằng dữ liệu có
sẵn: **cả 8 đều là `analysis_cost`** — trần $0,015 mỗi Analysis. Đó đúng là trần
`_owner_cost_ceiling` đã nâng lên `inf` cho deployment `unmetered` ở §9, nên
failure mode này đã đóng. Reservation thật hiện ~3.300 micro-USD/call, tức dưới
trần cũ một Analysis chỉ đủ ~4 call và một loop 4 round chắc chắn đụng trần.

**Không sửa `error_code` để mang `reason`.** Làm vậy phá một quyết định có chủ
đích: interface branch trên một tập đóng của pipeline, không trên 14 reason của
admission.

### `usage_unknown`: không phải lỗ, và đã tự hết

`usage_unknown` là trạng thái **khởi tạo**, ghi trước khi gọi mạng và đổi thành
`reconciled` sau khi call trả về. Docstring `LlmCallUsage` nói rõ ý nghĩa: *"A
death after the provider accepted the request leaves `usage_unknown` with the full
reservation charged, which is the honest reading: the money is gone whether or not
the answer arrived."*

Nên cách đọc chi tiêu đúng là `sum(COALESCE(actual_micro_usd, reserved_micro_usd))`,
không phải `sum(actual_micro_usd)`. **Mọi con số USD ở §5 là số thiếu vì tôi sum
sai cột**, không vì ledger hỏng:

| | sum(actual) | COALESCE(actual, reserved) |
|---|---|---|
| Turn | $6,33 | **$8,50** |
| Analysis | $0,036 | $0,052 |
| Probe | $0,347 | $0,530 |

→ Turn thực tế ≈ **$0,037 mỗi Turn**, không phải $0,0276.

Và tỷ lệ chưa reconcile là chuyện **lịch sử**, không phải hiện tại:

```
16/08  31,3 %      20/08   0,0 %
17/08  24,4 %      21/08   1,4 % (3/207)
18/08  33,3 %      22/08   0,0 % (0/235)
19/08  46,4 %      23/08   0,0 %
```

Ranh giới trùng cụm sửa route ngày 19–21/08 (`fix/route-error-log`,
`fix/route-thought-signature`, `fix/route-rate-limit`,
`feat/route-streaming-flag`) — nhất quán với khảo sát Hermes **#1**: `gateway_timeout`
là 3/4 lỗi route và là nhánh duy nhất không có chẩn đoán. Những dòng
`usage_unknown` đó là **call thất bại**, và sửa route đã đưa tỷ lệ về ~0.

**Không có việc gì phải làm.** Chỉ cần dùng `COALESCE` khi đọc chi tiêu.

## 7. Lỗ đánh giá chất lượng — nói thẳng

Repo xoá bộ eval ngày 22/08. Hermes không có grader để port. Merge mang vào
`test_analysis_loop_measurement.py` (487 dòng) + `loop_ops_router.py`, nhưng cái nó
đo là **substitution rate** và **round yield** — khả năng *hồi phục khỏi bằng chứng
thiếu*. Chính phase doc viết: *"substitution rate cao **không** chứng minh phân tích
đúng"*.

Nên PR chạm agent loop, tool schema hay prompt **không có cổng chất lượng nào**. Đó
là một lựa chọn, không phải thiếu sót — nhưng phải tường minh, vì mọi thứ ở §4 và §5
đều làm đáp án đổi và không gì bắt được hồi quy đó.

---

## 8. Sáu quyết định sản phẩm

**D1 · Context chip resolve server-side** — bổ sung cho `signals`, không thay. Chip =
"user đang xem cái này", deterministic, 0 token. Primitive còn thiếu duy nhất.

**D2 · Portfolio là ledger giao dịch; position derived.** Giá vốn là phép tính chứ
không phải dữ kiện. Ép bởi corporate action: repo đã thu `corporate_actions`, và một
lần chia cổ phiếu làm giá vốn lưu sẵn sai >100%. Áp CA lúc đọc thì đảo được và vẫn
đúng khi CA về muộn. Thêm bẫy basis: backfill lấy `adjusted=True`, snapshot đo được
là `price_basis: "raw"`, giá vốn user nhập là nominal — **hoà giải basis trước khi
hiển thị bất kỳ P/L nào.** Nay gấp hơn bản 1: `signals` cho model đọc field, nên một
giá vốn sai trở thành con số model tự tin dẫn ra. Bán: **bình quân gia quyền**.

**D3 · Có position thì có watchlist entry.** Cohort nightly là union Watchlist; nếu
position tách riêng thì mã đang giữ có thể không có Analysis nào.

**D4 · Push phần phát hiện, pull phần văn.** "2 thay đổi đáng chú ý", "+0,82% vs
VNINDEX +1,03%", "tỷ trọng vượt 30%" — arithmetic thuần từ `analysis.verdict` (cột
extract, index `ix_analysis_symbol_day`), chi phí 0, push được. Văn sinh khi user mở,
cache theo `(user, trading_day)`. Nhân theo user *hoạt động*.

**D5 · Score chỉ gồm thành phần deterministic.** Ship concentration, sector exposure
(`listing_roster.icb_code`), P/L, phân bố verdict. Hoãn correlation/beta/VaR/scenario:
`stock_daily_ohlcv` = 1.710 mã · 119.525 dòng · nến mới nhất **2026-08-07** →
~70 dòng/mã khi correlation 1 năm cần ~250. Độ sâu lịch sử cho mã có position là
tiền đề tường minh, xứng một backfill lane riêng.

**D6 · Portfolio context + web trong một Turn.** Merge xử lý **một nửa**: `287fe78`
vẽ figure từ store khác với figure từ trang người lạ, và `check_price_claim` phủ định
số ngoại lai bằng số học — một giá không nằm trên bước giá HOSE thì chưa từng được
match. Đó mạnh hơn cả chương citation §51 của blueprint. **Nửa còn lại chưa xử lý:**
exfiltration — holdings rời hệ thống qua một `fetch_url` do model soạn. Hiển thị
provenance không chạm tới việc đó.

---

## 9. Thứ tự thi công

| # | Việc | Vì sao ở đây |
|---|---|---|
| ✅ | Trần giờ vnstock · entitlement monitor | xong |
| ✅ | Rà trần fan-out theo `reads_external`; trần chi phí per-owner → `inf` khi unmetered | xong |
| ✅ | Đo cache trên route này | xong — cache đã tự chạy 57,6 % ở lane Turn, **không** bật cờ nào |
| 2 | Lưu `reason` cạnh `state`; taxonomy cho 400 | trần nào nổ hiện vẫn không đọc được |
| 3 | Context chip (D1) | đòn bẩy sản phẩm lớn nhất |
| 4 | Thesis delta | retention cao nhất trên mỗi đồng; chuỗi + cột đã có |
| 5 | Portfolio (D2→D3→D5→D4) | bước đầu phải dùng được khi không có AI |
| 6 | Realtime transport | sau phép đo thứ Hai 24/08 |
| 7 | News story clustering | độc lập, song song lúc nào cũng được |

Hoãn/từ chối: dynamic subscription manager, scenario engine, decision journal,
subagent/MoA, model modes (Deep Research §64.8 không có lane trong $45 chia 3),
skills tự sinh.

**Realtime** (đo 23/08, thị trường đóng): `signalrcore 0.9.71` chạy — `1.0.x` fail
negotiate vì hub trả negotiate v0 không có `negotiateVersion`. Hub join
`Realtime.Ticker.STB` / `Realtime.Index.VN30`. **Stream và REST cùng tồn tại** (4/4
`fetch_market` OK khi stream đang mở) → không cần arbitration với collector.
`start()` non-blocking. Hình dạng: hub → Stream Worker → Redis hot keys → **SSE**
(không WebSocket: feed một chiều, repo đã có SSE) → browsers. Universe **tĩnh**
(VN30 + indices). Ba số phải đo thứ Hai 09:00–15:00: tick rate/mã, reconnect có còn
trong phiên, breadth có về khi subscribe index —
`prototypes/probe_fiinquant_realtime.py`.

**UI:** Stock Detail vào inspector rail, không phải route. Portfolio là view thứ năm.
Giữ invariant một màn hình.

---

## Câu chưa giải quyết

1. ~~Cache trên cliproxy~~ — **đã trả lời** (§5): nhận nhưng vô tác dụng; cache tự
   động đã chạy. Còn lại: tỷ lệ hit của round 2+ trong một Analysis, chỉ đo được
   khi loop chạy thật.
2. **Giá production thật** bao nhiêu? Mọi con số USD ở §5 là giá proxy dev.
3. **`budget_exhausted` 17–18/08** là bug hay trần per-call? §6 xong mới trả lời được.
4. **FiinQuant sau 06/09** — free tier thật hay gói trả phí?
5. **Trần 5 mã/danh mục** — ràng buộc sản phẩm hay dẫn xuất từ ngân sách?
6. **Basis giá cho P/L** — quy giá vốn về adjusted, hay giữ nominal và so chuỗi raw?
7. **Cổng chất lượng** (§7) — dựng lại, hay tường minh chấp nhận không có?

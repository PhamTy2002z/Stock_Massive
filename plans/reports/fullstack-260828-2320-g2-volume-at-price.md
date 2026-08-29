# G2 — Study `volume_at_price`, phễu miss, và dọn khoá máy khỏi bảng

Ngày 2026-08-28. Nhánh `feat/study-canvas-runtime`. Không commit.

## 1. Study mới `volume_at_price` v1

`apps/api/src/studies/volume_at_price.py` (mới, ~470 dòng).

**Params** — `symbol` (Universe) · `sessions` mặc định 1, kẹp 1–5 · `bins` mặc
định 24, kẹp 6–24. `requires=("intraday_bar_15m",)` nên `warmup.warm` nạp bar
tới hết hôm nay trước khi `compute` đọc.

**Thuật toán**

1. Chọn phiên (`_window`). `today` theo giờ VN. Nếu là ngày trong tuần và đã
   qua 09:30 (`FIRST_BUCKET_SETTLED_AT` — nến 09:15 đóng lúc 09:30) mà kho
   không có bar stamp hôm nay → `StudyRefused(SESSION_NOT_INGESTED)`. Không lấy
   phiên trước đội tên. Ngoài khung đó thì lấy `sessions` phiên gần nhất kho
   có, tính cả phiên đang chạy.
2. Xác định sàn: `price_band.resolve_band_regime(...).exchange`. Không có bản
   ghi niêm yết → `StudyRefused(EXCHANGE_UNKNOWN)`, không đoán bước giá.
3. Rải khối lượng (`_ladder`/`_steps`). Với mỗi nến 15 phút, đi bộ từ mức tick
   đầu tiên ≥ `low` lên tới `high`, bước lấy từ `price_band.tick_size(exchange,
   price)` — **import đúng hàm của `check_price_claim`, không copy bảng tick**.
   Đi bộ chứ không chia, vì HOSE đổi bước ở 10.000 và 50.000: một nến vắt qua
   50.000 phải quote 50 ở dưới và 100 ở trên. Volume chia đều cho các mức đó.
   Nến hẹp hơn một bước → một mức. Quá `MAX_STEPS_PER_BAR = 200` bước (mã giá
   thấp) → lấy mẫu đều trên đúng dải đó thay vì cắt cụt.
4. Gộp (`_fold`). Thang ≤ `bins` thì giữ nguyên từng tick. Dài hơn thì gộp
   thành đúng `bins` vùng đều nhau; **nhãn của mỗi vùng là tick khớp nhiều nhất
   trong vùng**, không phải trung điểm — để mức mà câu trả lời nêu vẫn là một
   mức thị trường thật sự quote. Vùng mang theo `low`/`high` của nó.
5. Đỉnh = rung khối lượng lớn nhất. Headline và frame nói cùng một mức.

**Frames** — `tiles` (`stat_tiles` v2, 4 ô, ô đầu role `focus`) và `ladder`
(`bar_series` v2, `kind="series"`, xếp theo giá tăng dần, đúng một `focus`, còn
lại `series`). Không thêm widget mới.

**Refusal** — `session_not_ingested` (phiên hỏi chưa có) · `exchange_unknown`
(không biết bước giá) · `no_traded_sessions` (có nến nhưng volume 0) ·
`missing_target_session` (ngoài Universe).

**Provenance** — `health="degraded"` khi phiên chưa đóng hoặc cửa sổ ngắn hơn
số phiên hỏi. `reason` ghép hai vế bằng `; `:
`"Phiên chưa đóng, tính tới 13:30"` · `"chỉ đọc được 1/3 phiên gần nhất"`.

**Hạn chế đã biết, ghi trong docstring:** ngày lễ giữa tuần. Kho không phân
biệt "thị trường nghỉ" với "bar chưa về", nên câu hỏi hôm lễ sẽ refuse thay vì
trả phiên gần nhất. Đó là hướng an toàn hơn trong hai hướng, và đúng theo yêu
cầu "không đội tên phiên".

### Headline thật (fixture một phiên, ATC 900k cổ ở 74.500)

```json
{
  "symbol": "ZZVAP", "session": "2026-08-20", "sessionsUsed": 1,
  "sessionUnderway": false,
  "peakPrice": 74500.0, "peakZone": null, "peakShare": 0.6127,
  "peakVolume": 1041667.0, "totalVolume": 1700000.0,
  "closePrice": 74500.0, "rangeLow": 74000.0, "rangeHigh": 74600.0,
  "levelCount": 7, "grouped": false,
  "top3": [
    {"price": 74500.0, "zone": null, "share": 0.6127, "volume": 1041667.0},
    {"price": 74400.0, "zone": null, "share": 0.1245, "volume": 211667.0},
    {"price": 74300.0, "zone": null, "share": 0.1,    "volume": 170000.0}
  ],
  "caveat": "Dữ liệu nến 15 phút không tách bên mua và bên bán, nên đây là mức giá giao dịch nhiều nhất chứ không phải mức được mua nhiều nhất."
}
```

`provenance.methodNotes`:

1. "Khối lượng mỗi nến 15 phút được rải đều cho các bước giá trong khoảng thấp
   nhất đến cao nhất của nến đó, nên đây là số ước lượng."
2. "Nến 15 phút không ghi bên mua hay bên bán, nên bảng này đọc là khối lượng
   giao dịch tại mỗi mức giá."
3. (chỉ khi có gộp) "Thang giá dài hơn số mức vẽ được nên đã gộp thành các vùng
   đều nhau; mức ghi cho mỗi vùng là mức khớp nhiều nhất trong vùng đó."

Headline serialize ~1,1 KB, dưới trần 1.500 ký tự test đang giữ. `frames` không
vào message — `run_study` chỉ trả headline + `artifactId`, test transcript sẵn
có vẫn pass.

**Ghi chú từ vựng:** yêu cầu viết `"ước từ bar 15 phút"`. Tôi dùng
**"nến 15 phút"** thay cho "bar" — "bar" là từ kỹ thuật, "nến" là từ người đọc
dùng. Nội dung không đổi.

## 2. `SignalIssue.SESSION_NOT_INGESTED`

- `apps/api/src/stocks/signals/issues.py` — mã mới `session_not_ingested`, kèm
  chú thích phân biệt với `missing_target_session` (ngày đó không có phiên nào)
- `apps/api/src/alpha/reasons.py` — câu tiếng Anh cho model
- `apps/web/src/lib/signal-issues.ts` — "Phiên được hỏi chưa có dữ liệu, chưa
  lấy phiên trước thay thế"

`signal-issues.test.ts` sẵn có đọc thẳng enum Python nên đã giữ hai đầu web ↔
API. Phía API trước đây **không có** test tương đương; tôi thêm
`test_every_signal_issue_has_a_sentence_for_the_model` vào
`tests/studies/test_volume_at_price.py`.

## 3. Routing

- `question` của Study liệt kê thẳng các cách hỏi: "mức giá mua nhiều nhất",
  "mức giá bán nhiều nhất", "mức giá khớp nhiều nhất", "vùng giá tập trung",
  "khối lượng theo giá", "hôm nay". `run_study_description()` sinh từ registry
  nên tự nhận — không hardcode chỗ nào.
- `agent/tools/studies.py::run_study_description()` thêm một câu: đọc danh mục
  theo *điều được hỏi*, không theo chữ dùng để hỏi.
- `agent/signal_tool_contract.py::GET_SERIES_DESCRIPTION` thêm: nó đọc một con
  số mỗi phiên đã đóng, **không đọc được gì bên trong một phiên** — câu hỏi về
  mức giá nào khớp nhiều nhất phải sang `run_study`. Đây là chỗ câu hỏi gốc bị
  lệch sang `get_series`.
- `agent/prompt/sections.py`: **không sửa**. Prompt không giữ danh mục Study
  (danh mục nằm trong schema của `run_study`), nên sửa prompt chỉ tạo rủi ro
  phải bump `PROMPT_VERSION` mà không thêm thông tin.

### Sửa kèm: mô tả tham số dùng chung không còn nói dối

`study_parameters()` gộp mọi Study lên một object phẳng và trước đây giữ **mô tả
đầu tiên** cho một key dùng chung. `sessions` của `intraday_liquidity_profile`
là 10–60; của `volume_at_price` là 1–5. Giữ nguyên thì model đọc "10–60", gửi
`sessions: 10` cho `volume_at_price`, bị kẹp về 5 — tức là câu hỏi "hôm nay" trả
về 5 phiên. Giờ khi hai Study mô tả khác nhau thì **cả hai mô tả cùng đi**, mỗi
cái có tiền tố tên Study của nó.

## 4. Phễu miss

`agent/loop.py`, chỉ phần log:

- `_TurnState` thêm `turn_id` / `thread_id` / `question` — copy từ request đúng
  theo cách `mode` đã copy sẵn (`_ended` không cầm request).
- `_log_catalog_without_a_run(state)` gọi trong `_ended`, sau checkpoint. Điều
  kiện: Turn có `list_studies` và **không** có `run_study`. Level `info`, logger
  `src.agent.loop`, `extra={"study_catalog_miss": True, "turn_id", "thread_id",
  "question"}`. Câu hỏi cắt còn 200 ký tự (`ASKED_LIMIT`, thêm `…`).
- Không cột DB, không migration. **Không sửa** `messages.py` / `events.py`.
- `turns.py` không đụng: `_ended` trong `loop.py` là chỗ duy nhất mọi đường kết
  thúc đi qua.

## 5. Dọn khoá máy khỏi bảng "xem dạng bảng"

Disclosure gọi `DataTableWidget` với `options={}` (`signal-desk-block.tsx:152`),
nên **không** ẩn cột được qua labels/options. Hai ca xử lý khác nhau:

**`earnings_dislocation` — thuần backend.** Bỏ hẳn cột `code` khỏi frame
`filters`; không widget nào đọc nó (block là `data_table` với `options={}`).
Sửa luôn ba chuỗi lộ từ vựng máy trong cùng bảng:
`"Chưa có báo cáo kỳ này trong store"` → bỏ "store" · `"cửa sổ giá cùng một
Price Basis"` → "cùng một cơ sở giá" · dòng đầu `("universe", "Universe",
"market = mã đang niêm yết", …)` → `("Tổng số mã xét", "toàn bộ mã đang niêm
yết", …)` (hằng `START_ROW_LABEL`).

**`entry_condition_review` — cần một sửa FE nhỏ.** Frame `conditions` trước có
cả `status` (`met`/`not_met`) lẫn `status_text` (`Đạt`/`Chưa đạt`); widget
`condition_checklist` v1 đọc `status` để chọn icon, nên không thể chỉ xoá cột.
Cách ít đụng FE nhất tôi tìm được:

- Study bỏ cột `status_text`, cột `status` **mang thẳng tiếng Việt**, label
  "Trạng thái". Bảng disclosure không còn khoá máy nào.
- `apps/web/src/components/signal-desk/widgets/condition-checklist.tsx`: map
  `STATUSES` nhận **cả hai cách viết** — thêm 3 khoá tiếng Việt, **giữ nguyên**
  `met`/`not_met`/`unknown` để artifact đã lưu vẫn vẽ đúng. Đây là toàn bộ thay
  đổi FE: 3 dòng dữ liệu + docstring, không đổi logic, không widget mới, không
  bump version widget.

**Đây là chỗ tôi bước ra ngoài `components/**`.** Mục 5 của brief nói "chọn cách
ít đụng FE nhất và nói rõ trong report", còn điều kiện BLOCKED ghi là "nếu cần
widget mới". Không cần widget mới; cần 3 khoá alias. Nếu anh muốn tuyệt đối
không chạm `components/**` thì phương án thay thế duy nhất là để nguyên
`met`/`not_met` lộ trong bảng — nói rõ để anh quyết.

## Files

**API**
- `src/studies/volume_at_price.py` (mới, 470)
- `src/studies/__init__.py` (+1 import đăng ký)
- `src/studies/entry_condition_review.py` (frame `conditions`: 6 cột → 5)
- `src/studies/earnings_dislocation.py` (frame `filters`: 5 cột → 4, +
  `START_ROW_LABEL`, 3 chuỗi)
- `src/stocks/signals/issues.py` (+`SESSION_NOT_INGESTED`)
- `src/alpha/reasons.py` (+1 câu)
- `src/agent/tools/studies.py` (`study_parameters` gộp mô tả, +1 câu mô tả
  `run_study`)
- `src/agent/signal_tool_contract.py` (`GET_SERIES_DESCRIPTION`)
- `src/agent/loop.py` (3 field `_TurnState`, 1 call trong `_ended`, 2 helper, 3
  hằng, `__all__`)
- `src/studies/registry.py` — **không đổi** (đăng ký đi qua `register()` sẵn có)

**Tests API**
- `tests/studies/test_volume_at_price.py` (mới, 25 case)
- `tests/studies/test_entry_condition_review.py` (status tiếng Việt, index cột)
- `tests/studies/test_earnings_dislocation.py` (`ladder()` map nhãn → mã)
- `tests/test_agent_loop.py` (+4 case phễu, fixture `study_tools`)
- `tests/test_agent_capability_contract.py` (hash schema đã khoá: `2ff91dfd…` →
  `b6abb53f…`; file tự ghi là phải đổi cùng commit thêm Study)

**Web**
- `src/lib/signal-issues.ts` (+1 câu)
- `src/components/signal-desk/widgets/condition-checklist.tsx` (+3 alias)
- `src/components/signal-desk/widgets/condition-checklist.test.tsx` (+6 case)

## Lệnh test và kết quả

| Lệnh | Kết quả |
|---|---|
| `make test` (apps/api), lúc G2 xong | **1384 passed**, 121 warnings, 37.71s |
| `make test` (apps/api), chạy lại sau đó | 1389 passed, **1 failed** — của phiên khác, xem dưới |
| `make test-one T=tests/studies` | 142 passed |
| 8 suite G2 chạm (studies · loop · study_tools · capability · signal_desk · transport · turn_lifecycle · prompt) | **376 passed** |
| `pnpm lint` (apps/web) | sạch |
| `pnpm test` (apps/web) | **58 file / 736 test passed** |
| `pnpm type-check` (apps/web) | **fail — không phải của G2**, xem dưới |
| `pnpm build` (apps/web) | `✓ Compiled successfully in 7.3s`, rồi fail ở thu thập page data |
| `make smoke-signal-desk` | **không chạy** — cần `SMOKE_EMAIL`/`SMOKE_PASSWORD` và tiêu tiền model thật |

**Lần `make test` thứ hai.**
`tests/test_signal_registry.py::TestTradedMoneyIsDerivedRatherThanRefused::
test_the_derived_money_reaches_the_gateways_own_standing` fail. Không phải của
G2: giữa hai lần chạy, phiên song song đã sửa `signals/{market_behavior,
registry,sessions}.py` + chính file test đó (đang dở, chưa commit), và số test
tăng từ 1384 lên 1389. Lần chạy đầu — trước khi họ ghi — sạch tuyệt đối, và 376
test của 8 suite G2 chạm vẫn pass sau đó.

**`pnpm type-check`.** Lần chạy đầu báo 7 lỗi ở `src/lib/alpha.ts` và
`src/app/api/alpha-desk/[...path]/route.ts`. Chạy lại vài phút sau: 7 lỗi đó
biến mất, thay bằng 3 lỗi `offStripCount` ở
`src/components/signal-desk/signal-desk-header.test.tsx`. Cả hai bộ đều là file
phiên song song (plan price-basis / G1 board switcher) đang sửa dở — trong lúc
tôi làm đã có thêm 2 commit mới (`99bdd77`, `2cee7f1`). Không file nào tôi sở
hữu bị báo lỗi.

**`pnpm build`.** Biên dịch xong sạch. Bước sau đó vỡ với `Cannot find module
'./337.js'` + `Failed to collect page data for /icon.svg` — đúng triệu chứng đã
ghi trong memory "Cổng production phá .next của dev": có `next dev` (PID 88451,
cổng 3000) đang chạy và ghi đè `.next`. Tôi **không** xoá `.next` để khỏi phá
dev server của phiên khác.

**Smoke.** `scripts/smoke_signal_desk.py` không nằm trong file tôi sở hữu; nó
giữ 5 câu hỏi cố định và chưa có câu nào cho `volume_at_price`. Đề xuất thêm
`("Mức giá được mua nhiều nhất của VCB trong phiên hôm nay là?", True)` khi anh
chạy smoke lần tới.

## Câu hỏi còn treo

1. Cột `status` của `condition_checklist` — chấp nhận 3 dòng alias trong
   `condition-checklist.tsx`, hay để nguyên `met`/`not_met` lộ trong bảng?
2. Ngày lễ giữa tuần: hiện refuse `session_not_ingested`. Có muốn nới thành
   "trả phiên gần nhất, health degraded, reason nêu rõ ngày" không? Cần một
   nguồn nói "hôm nay có phiên hay không" — lịch từ `bar_daily` chỉ biết phiên
   **đã đóng** nên không trả lời được câu đó.
3. `sessions` dùng chung tên với `intraday_liquidity_profile` (1–5 vs 10–60).
   Tôi vá bằng cách cho cả hai mô tả cùng đi. Nếu muốn theo lệ
   `horizon_sessions` của `entry_condition_review` thì đổi tên thành
   `price_sessions` sẽ sạch hơn — nhưng lệch với brief.

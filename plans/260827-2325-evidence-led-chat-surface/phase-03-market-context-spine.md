---
phase: 3
title: "Market context spine"
status: todo
priority: P1
effort: ""
dependencies: [1]
---

# Phase 03: Market context spine

> **BẢN NÀY ĐÃ LẠC HẬU — 2026-08-28. Phải viết lại trước khi thi công.**
>
> Hai lý do:
>
> 1. **Ba claim red-team nền của phase đã bị đảo.** Đo lại cho thấy
>    `latest_trading_day()` trả `2026-08-24 Monday` (đúng — `day_in_vn` đã
>    `astimezone(VN_TZ)`) và **0** dòng cuối tuần khi đếm theo
>    `Asia/Ho_Chi_Minh`. Lỗi thật là `provider_snapshots` không còn writer nên
>    lịch đứng ở 2026-08-24.
>
>    **Sửa 2026-08-29:** câu thứ ba ở bản trước — "FiinQuant khớp `bar_daily`
>    80/80 tuyệt đối" — **cũng sai**, và nó là phép đo **một mã** (STB, ngoại lệ).
>    Đo trên đủ 30 mã declared: khớp **1.367/2.256 = 60,59%**, 20/30 mã có lệch.
>    Toàn bộ khoảng lệch là chữ ký điều chỉnh: giá đã rebase so với giá công bố.
> 2. **Việc sửa `trading_day.py` đã đổi chủ sở hữu** sang
>    `plans/260828-2126-price-basis-and-signal-field-spine/` phase 02, vì nó phải
>    đi cùng nhánh với `signals/sessions.py`.
>
> Mọi chỗ trong file này ghi "25 Signal Field" đọc con số sai — đúng là **30**,
> và từ 2026-08-29 là **33** (thêm ba field `earnings.*`).
>
> **Phụ thuộc ngoài plan đã thoả 2026-08-29:** plan price-basis đóng 9/9 phase,
> nên phase này không còn bị chặn — chỉ còn nợ bản viết lại.
> Phase này khi viết lại chỉ còn phần **đọc** lịch cho market context, không sửa
> `trading_day.py`, không mở freeze.

## Overview

Backend cho câu "dữ liệu mới đến đâu, phiên đang ở đâu". Critique nói thẳng luật
của nó: *"Nếu có live status, hiển thị session và freshness từ dữ liệu thật;
không hard-code badge tạo cảm giác giả."*

**Phase này đã đổi bản chất sau red-team.** Bản đầu viết nó là phase read-only,
thêm một module mới đọc lịch giao dịch có sẵn. Đo trên DB thật cho thấy **lịch
giao dịch của hệ thống đã chết**, nên phase này giờ sửa nó — và đó là mở freeze
vào một hàm mà 25 Signal Field đọc.

## Sửa sau red-team (2026-08-28)

Đo trên `stockmassive` 2026-08-28:

| Nguồn | Dòng | Mới nhất |
|---|---|---|
| `provider_snapshots` capability `market` — cái `trading_day.latest_trading_day()` đọc (`stocks/trading_day.py:43-54`) | 67.688 | **2026-08-23** |
| `provider_snapshots` capability `reference` / `valuation` | 220 / 35.245 | 2026-08-24 |
| `bar_daily` `series='equity'` | 809.085 | **2026-08-27** |
| `bar_daily` `series='index'` | 3.991 | **2026-08-27** |

Collector ghi `provider_snapshots` đã rip 2026-08-25 (CLAUDE.md §Không còn tồn
tại). Bảng đóng băng và khoảng cách nới thêm mỗi ngày. Bốn hệ quả:

1. `latest_trading_day` trả **2026-08-23** thay vì 2026-08-27.
2. `trading_days_before/between` cũng đọc cùng bảng → cùng sai.
3. `sessionsBehind` mà bản đầu định tính (`bar_daily` so với
   `latestClosedSession`) sẽ ra **số âm**.
4. Acceptance #2 cũ ("tắt endpoint → chip biến mất") **không bắt được** ca này:
   endpoint vẫn 200, vẫn có số, số vẫn sai.

Ba lỗi cột của bản đầu, sửa cùng: bảng dùng `trading_day` **không** `session_date`;
`bar_daily` chứa cả `equity` lẫn `index` trong một bảng nên mọi truy vấn phải lọc
`series`; và `session_window.py` ở `src/stocks/intraday/`, `SESSION_SETTLED_AT` ở
`src/stocks/intraday/reads.py:34` — `src/stocks/session_window.py` không tồn tại.

Quyết định (user chốt 2026-08-28): **sửa tận gốc**, không tạo lịch thứ hai.

## Requirements

Functional:

- `trading_day.py` đọc nguồn **có writer sống** (`bar_daily`), không đọc
  `provider_snapshots`.
- Một endpoint đọc trả (a) trạng thái phiên tại thời điểm gọi, (b) độ mới dữ liệu
  của store cho Universe declared.
- Trạng thái phiên phân biệt: trước giờ · ATO · liên tục sáng · nghỉ trưa · liên
  tục chiều · ATC · sau giờ · đóng.
- Độ mới trả `as_of`, số phiên trễ, `health`.
- Không có dữ liệu → `null` cho đúng nhánh đó, không số đoán.

Non-functional:

- **Không con số nào của Signal Field đổi vì lý do khác lịch.** Suite signals chạy
  trước và sau, lệch nào cũng phải truy về được lịch.
- Không đụng `src/studies/*`. Điểm tiếp xúc với vùng plan Study sở hữu
  (`src/stocks/intraday/*`) là **chỉ đọc**: `phase_of`, `SESSION_SETTLED_AT`.
- **Không cache in-process.** Nhiều uvicorn worker (`Dockerfile:37`) → mỗi worker
  cache riêng, hai request liên tiếp trả số khác nhau. Bản đầu nêu cache 30s; bỏ.

## Architecture

**Sửa `trading_day.py` — ba hàm, một nguồn mới.**

```python
# Lịch giao dịch = các ngày store THẬT SỰ có bar cổ phiếu.
# bar_daily có writer sống (Study 08a); provider_snapshots không còn.
select(func.max(BarDaily.trading_day)).where(BarDaily.series == "equity")
```

`series == "equity"` là bắt buộc: không lọc thì VN-Index (`series='index'`) tham
gia định nghĩa "ngày giao dịch", và index có thể có ngày cổ phiếu không có.

`trading_days_before/between` đổi sang `SELECT DISTINCT trading_day` trên cùng
bảng + cùng filter. Đây thật sự **chính xác hơn** lịch cũ: một ngày có bar là một
ngày có giao dịch, không cần suy luận.

Giữ nguyên chữ ký hàm và nguyên nghĩa "None là câu trả lời thật, không phải lỗi"
(docstring hiện tại) — 25 Signal Field gọi chúng và không được biết nguồn đã đổi.

**Lịch nghỉ lễ: giờ giải được, và không cần đoán.** Bản đầu phải suy "hôm nay
nghỉ lễ" từ "chưa có dữ liệu" và ghi rủi ro báo động giả buổi sáng. Với `bar_daily`
sống, luật đơn giản hơn:

- Trước `SESSION_SETTLED_AT` (15:00): `isTradingDay` theo **thứ trong tuần**, và
  trạng thái theo đồng hồ. Không đoán lễ.
- Sau 15:00 mà `max(trading_day) < hôm nay`: `closed`, và `health` xuống một bậc
  — hoặc hôm nay là lễ, hoặc ingest hỏng. Cả hai đều là "không tin dữ liệu hôm
  nay", nên một trạng thái là đủ.

Đây vẫn không phải lịch lễ thật, và phase này **không** giả vờ là. Nêu ra để
người sau không hiểu nhầm chip là chính xác vào mùng Hai Tết.

**Module mới `src/market_context/`** — read model phục vụ surface, không phải logic
thị trường:

```
src/market_context/
  session.py      # trạng thái phiên từ đồng hồ + lịch
  freshness.py    # độ mới store cho một tập mã
  schemas.py      # payload typed
  router.py
```

`session.py` nhận đồng hồ **làm tham số**, không gọi `datetime.now()` — điều kiện
để test golden mọi mốc. Nó **import** hằng số giờ từ `src/stocks/intraday/`, không
viết lại; một test khẳng định điều đó.

`next_transition_at` cho FE hiển thị "còn 12 phút tới ATC" mà không cần FE biết
giờ giao dịch.

**Độ mới: một aggregate/nguồn, không phải một truy vấn/mã.**

```sql
SELECT max(trading_day) AS latest, max(observed_at) AS observed
FROM bar_daily
WHERE series = 'equity' AND symbol = ANY(:symbols)
```

`sessionsBehind` = số ngày giao dịch giữa `latest` và `max(trading_day)` toàn
market. Vì cả hai giờ cùng nguồn, con số này **không thể âm** — đó là kiểm tra
tự nhiên rằng S1 đã sửa đúng.

`health` **không phát minh mới**: dùng lại đúng ba giá trị của
`Provenance{as_of, health, sessions_used}` để một câu trả lời và một badge không
nói hai thứ khác nhau về cùng dữ liệu.

**Universe.** `universe.py` có 3 tập; `market` **không** nằm trong `symbols`.
Freshness báo theo tập `symbols` (30 mã declared) — tập user hỏi được. Nhánh riêng
cho index vì Study 08a đã ingest VN-Index.

**Endpoint.** `GET /api/v1/market/context`, **có auth** như mọi route khác. Auth ở
repo là per-handler (`main.py:116-119` không có `dependencies=`), nên thiếu
`CurrentUser` là **lỗi im lặng** — success criteria có một dòng riêng cho nó.
Payload rò gì nếu public: danh sách Universe declared + trạng thái ingest của kho
dữ liệu ràng buộc licence vnstock. Không đáng để public.

```jsonc
{
  "session": {
    "phase": "continuous_pm",
    "tradingDay": "2026-08-27",
    "nextTransitionAt": "2026-08-27T14:30:00+07:00",
    "isTradingDay": true
  },
  "data": {
    "latestClosedSession": "2026-08-27",
    "daily":    { "asOf": "2026-08-27", "sessionsBehind": 0, "health": "normal" },
    "intraday": { "asOf": "2026-08-27", "sessionsBehind": 0, "health": "normal" },
    "index":    { "asOf": "2026-08-27", "sessionsBehind": 0, "health": "normal" }
  }
}
```

Nhánh nào store rỗng → **`null`**, không phải `{"asOf": null, ...}`.

## Related Code Files

Modify:

- `apps/api/src/stocks/trading_day.py` — ba hàm đổi nguồn sang `bar_daily`
  (**mở freeze**, S1)
- nơi đăng ký router

Create:

- `apps/api/src/market_context/{__init__,session,freshness,schemas,router}.py`
- `apps/api/tests/market_context/{test_session,test_freshness,test_router}.py`
- `apps/api/tests/stocks/test_trading_day_source.py`

Read-only (không sửa):

- `apps/api/src/stocks/intraday/{session_window,reads}.py` — vùng plan Study sở
  hữu; chỉ đọc `phase_of` và `SESSION_SETTLED_AT`
- `apps/api/src/stocks/universe.py`, `listing_roster.py`
- bảng `bar_daily`, `bar_intraday_15m`

## Implementation Steps

1. **Chạy toàn bộ suite signals và ghi lại kết quả** — đây là baseline để so sau
   khi đổi lịch. Không có baseline thì không phân biệt được "lệch vì lịch đúng
   hơn" với "lệch vì lỗi mới".
2. Đổi `trading_day.py` sang `bar_daily` + filter `series='equity'`. Test mới:
   `latest_trading_day()` khớp `max(bar_daily.trading_day)`, **không** khớp
   `provider_snapshots`.
3. **Chạy lại suite signals.** So từng lệch với baseline bước 1. Mỗi lệch phải
   truy được về lịch trễ 4 phiên. Lệch nào không truy được → dừng, đó là lỗi mới.
4. `schemas.py` — mọi nhánh dữ liệu `Optional`.
5. `session.py`: `state_at(now, calendar)` hàm thuần. Test golden 14 mốc: 08:30 ·
   09:00 · 09:15 · 11:29 · 11:30 · 12:59 · 13:00 · 14:29 · 14:30 · 14:45 · 15:00 ·
   15:01 · thứ Bảy · ngày không có bar sau 15:00.
   *Chú ý ATC:* plan Study đã đo — ATC **khớp ở bucket 14:45**, đấu giá *chạy*
   14:30–14:45. Trạng thái *phiên* vào ATC ở 14:30 là đúng; đừng lẫn với nhãn
   bucket dữ liệu.
6. `freshness.py`: một aggregate/nguồn. Test: store rỗng → `None`; trễ 3 phiên →
   `sessionsBehind == 3`; và **`sessionsBehind` không bao giờ âm**.
7. `router.py` **có** `CurrentUser`. Test: gọi không token → 401.
8. Cổng: `make test` tại `apps/api` trên host.

## Success Criteria

- [ ] Baseline suite signals ghi lại **trước** khi đổi lịch (bước 1)
- [ ] `latest_trading_day()` khớp `max(bar_daily.trading_day)` cho
      `series='equity'`; test khẳng định nó **không** đọc `provider_snapshots`
- [ ] Mọi truy vấn `bar_daily` lọc `series` — grep khẳng định
- [ ] Cột dùng là `trading_day`, không `session_date` — grep khẳng định
- [ ] Suite signals: mỗi lệch so baseline truy được về lịch, có ghi lại; zero lệch
      không giải thích được
- [ ] 14 mốc golden `session.py` xanh
- [ ] `session.py` không gọi `datetime.now()`; **import** hằng số giờ từ
      `src/stocks/intraday/` thay vì viết lại — hai test riêng
- [ ] Store rỗng cho một nguồn → nhánh đó `null`, request vẫn 200
- [ ] `sessionsBehind` đếm bằng ngày giao dịch (test có cuối tuần ở giữa) và
      **không bao giờ âm**
- [ ] `health` chỉ nhận giá trị đã có trong `Provenance`
- [ ] Một request = một truy vấn/nguồn (test đếm query). **Không cache** — bỏ tiêu
      chí cache của bản đầu, nó đối đầu tiêu chí này và sai trong multi-worker
- [ ] `GET /market/context` **có auth**: không token → 401
- [ ] Không file nào trong `src/studies/*` hay `src/stocks/intraday/*` bị sửa —
      `git diff --stat` khẳng định
- [ ] `make test` ≥1060 pass

## Risk Assessment

**Sửa `trading_day.py` phá 25 Signal Field — rủi ro #1 của phase (R6 cấp plan).**
Tín hiệu: suite signals đỏ ở bước 3. Phản ứng đã định: lệch **là điều kỳ vọng**
(lịch cũ trễ 4 phiên), nhưng mỗi lệch phải truy về được lịch. Lệch không truy được
→ dừng và đọc, **không** sửa test để xanh. Đây là lý do bước 1 (baseline) không
được bỏ.

**`bar_daily` có lỗ ở giữa thành ngày nghỉ giả.** Nếu ingest bỏ sót một phiên thì
`trading_days_between` coi phiên đó không tồn tại, và mọi cửa sổ lịch sử lệch một
phiên. Lịch cũ cũng có đúng vấn đề này (nó cũng suy lịch từ dữ liệu), nên đây
không phải hồi quy — nhưng giờ nó là nguồn duy nhất nên đáng nêu. Tín hiệu: đếm
`DISTINCT trading_day` so với số ngày làm việc trong cùng khoảng. Phản ứng: không
giải ở phase này; ghi thành quan sát, và nếu lỗ đủ lớn thì nó là bug ingest của
plan Study, không phải bug lịch.

**Cả hệ thống giờ phụ thuộc một bảng.** `bar_daily` chết thì lịch chết. Nhưng
`provider_snapshots` **đã** chết và không ai biết trong ba ngày — nên tình trạng
mới không xấu hơn, chỉ là phụ thuộc đã tường minh. Đáng có một cảnh báo vận hành,
thuộc observability, không thuộc phase này.

**Chip vẫn nói dối vào ngày lễ.** `isTradingDay` theo thứ trong tuần trước 15:00 →
09:15 mùng Hai Tết trả `phase: "ato"`. Sai tới 15:00, trên ~11 ngày lễ + tuần Tết
mỗi năm. Chấp nhận có ghi: một lịch lễ thật cần nguồn dữ liệu chưa có, và đoán lễ
từ "chưa có bar lúc 09:15" sẽ sai vào **mọi** buổi sáng giao dịch bình thường —
tệ hơn nhiều. Ghi vào `docs/design-guidelines.md` như một giới hạn đã biết.

Rollback: `trading_day.py` revert được độc lập (một commit, ba hàm) và đưa hệ
thống về lịch đóng băng — trạng thái hôm nay, không tệ hơn. Module
`src/market_context/` bỏ đăng ký router là xong.

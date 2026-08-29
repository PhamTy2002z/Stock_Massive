# Hai đề xuất cho hai câu còn mở

**Ngày:** 2026-08-29 · **Nguồn:** hai unresolved question của
`plans/260828-2126-price-basis-and-signal-field-spine/plan.md`
**Trạng thái:** đề xuất, **chưa thi công**.

---

# Đề xuất 1 — Ai chạy `backfill_daily`

## Điều đã có, đừng dựng lại

`src/stocks/backfill_daily.py` **đã là một job production-ready**, không phải một
script nháp:

| Thuộc tính | Bằng chứng |
|---|---|
| CLI có argparse + `main(argv) -> int` | `:293`, `:308` |
| Resumable **không cần checkpoint table** | tiến độ suy từ store; upsert idempotent (docstring `:1-9`) |
| Một mã lỗi không giết cả run | `:20-25`, mỗi mã một session + một commit |
| Exit code cho operator | `1` khi có mã lỗi **hoặc** spine vẫn stale sau run clean (`:326-337`) |
| Tự báo độ tươi cuối mỗi run | `spine_freshness(session)` `:322` |
| Có make target | `make backfill-daily SCOPE=index\|declared\|market` |

Nên câu hỏi **không** phải "viết job", mà đúng hai việc: **pacing** và **lịch**.

## Chặn đường: không có pacing nào cả

`grep sleep|rate|throttle|backoff|retry|min_interval` trên
`backfill_daily.py` **và** `providers/vnstock_daily.py` → **0 hit**.

| | |
|---|---|
| scope `market` | **1.523** call tuần tự |
| trần vnstock Bronze (dev) | **180 req/phút** |
| trần Diamond (prod) | 600 req/phút |

Không có gì giữ nhịp. Một run `market` tự động hằng đêm là con đường ngắn nhất
tới việc bị throttle hoặc khoá key — và vì không có retry/backoff, mã bị từ chối
chỉ đơn giản là "không đủ sâu lần sau", **im lặng**.

**Đây là điều kiện tiên quyết, không phải cải tiến kèm.** Đặt cron trước khi có
pacing là tự động hoá một hành vi vi phạm rate limit.

Chi phí khi đã pace đúng: 1.523 ÷ 180 ≈ **8,5 phút** cho scope `market`. Không
phải vấn đề — chỉ cần tồn tại.

## Lịch đề xuất

Giờ chạy: **16:30 ICT**. Không phải số tôi chọn — đó là quy ước đã ghim trong
code: `observed_at=datetime.combine(day, time(16, 30), tzinfo=VN_TZ)`, mô tả là
*"when a run that waited for the close would have read it"*. Phiên đóng 15:00,
số liệu lắng sau đó.

| Scope | Call | Nhịp | Vì sao |
|---|---|---|---|
| `index` | 1 | **hằng ngày**, chạy **trước tiên** | VNINDEX **định nghĩa Trading Day calendar** (`CALENDAR_SERIES`). Thiếu nó thì mọi cửa sổ neo sai, mọi anchor mất. Rẻ nhất, quan trọng nhất, nên đi đầu và fail loud |
| `declared` | 30 | hằng ngày, sau `index` | 30 mã lane chat thật sự phục vụ |
| `market` | 1.523 | hằng ngày, sau hai cái trên, **có pace** | `earnings_dislocation` scope market cần nó tươi; 8,5 phút khi đã pace |

Thứ tự nối tiếp, không song song: ba scope cùng ghi `bar_daily` và cùng đụng một
rate limit; chạy song song là tự chia nhỏ trần của chính mình.

## Ba lựa chọn cho "ai gọi"

| | Cách | Ưu | Nhược |
|---|---|---|---|
| **A** ⭐ | **launchd trên máy dev** (macOS) gọi `make backfill-daily`, ba scope nối tiếp, log ra file | Không thêm service, không thêm dep, khớp đúng trạng thái pre-launch một máy. `launchd` chạy bù job bị miss khi máy ngủ — `cron` thì không | Chỉ chạy khi máy bật. Không phải giải pháp prod |
| **B** | **compose sidecar** `scheduler`, vòng lặp sleep trong container | Chạy cùng stack, không phụ thuộc OS host | Thêm một service phải trông; `CLAUDE.md` vừa cố ý rip toàn bộ job infra — dựng lại một cái mini là đi ngược quyết định đó |
| **C** | **Giữ tay** + cổng cảnh báo: `spine_freshness` bắn WARNING lúc API startup khi stale | Rẻ nhất, trung thực nhất | Người vẫn phải nhớ. Với một sản phẩm chưa launch thì chấp nhận được; sau launch thì không |

**Khuyến nghị: A, cộng C.** A cho việc chạy, C cho việc *biết* nó đã không chạy.
Cái đắt nhất không phải job không chạy — mà là job không chạy **mà không ai biết**,
trong khi mọi câu trả lời vẫn kèm một cái ngày trông có vẻ tươi.

Khi lên prod thì đây là việc của scheduler thật (ECS scheduled task / k8s CronJob),
và `main()` đã trả đúng exit code để một scheduler đọc được.

## Việc cần làm, theo thứ tự

1. **Pace provider call** — một `min_interval` suy từ trần req/phút, đặt ở
   `vnstock_daily` (một chỗ, mọi caller cùng hưởng) chứ không ở `backfill_daily`.
   Cấu hình qua `core/config.py`, mặc định theo Bronze.
2. **launchd plist** 16:30 ICT, ba scope nối tiếp, `index` trước, log có rotate.
3. **Cổng cảnh báo startup** đọc `spine_freshness` — hàm đã có, đang **0 caller
   ngoài `main()`**.
4. Ghi runbook vào `docs/`: chạy tay thế nào, đọc exit code thế nào, stale thì làm gì.

**Không** làm: checkpoint table (docstring `:1-9` giải thích vì sao cố ý không có),
retry trong job (một mã lỗi tự khỏi lần sau — đó là thiết kế).

---

# Đề xuất 2 — Nhánh BAND của `check_price_claim`

## Chẩn đoán chính xác

`agent/tools/price_check.py:369`:

```python
if anchor_bar.price_basis is not PriceBasis.RAW:
    return _unverified(BAND, "the previous session is stored adjusted at source, ...")
```

Sau khi lịch sang `bar_daily`, **không còn dòng `RAW` nào** → nhánh này trả
`unverified` **vĩnh viễn**.

Đo lại cho đúng, vì plan ghi sai một nửa (R7 nói mất 2/3 nhánh):

| Nhánh | Trạng thái | Lý do |
|---|---|---|
| TICK | ✅ chạy | không hỏi basis |
| STORE | ✅ chạy | `:461` chỉ `unverified` khi basis khác RAW **và** có `rescaled_since` → chỉ suy giảm quanh phiên có rescaling |
| **BAND** | ❌ **chết** | `:369` đòi RAW vô điều kiện |

**Chết 1/3, không phải 2/3.** Đây là control kiểm giá lấy từ nội dung web không
tin cậy, bị tắt như tác dụng phụ của việc đổi nguồn.

## Vì sao cổng cũ tồn tại, và vì sao nó sai cách

Cổng cũ đúng **ý**: band là phần trăm của một **giá tham chiếu sàn công bố**, và
một giá đã rebase không phải giá đó.

Nhưng nó kiểm **nhãn** thay vì kiểm **giá**. Với một mã không có sự kiện quyền nào
giữa phiên neo và hôm nay, giá đã điều chỉnh **bằng đúng** giá công bố — hệ số là
1. Nhãn nói "adjusted", sự thật nói "chưa ai rebase gì". Cổng cũ từ chối cả hai ca
như nhau.

Đây **chính xác** là lỗi Phase 06 vừa sửa cho `_basis_of_the_pair`, ở cùng một
tầng khái niệm. Cơ chế đã có sẵn và đã qua review.

## Đề xuất: mượn nguyên luật lưới bước giá của Phase 06

Thay cổng nhãn bằng cổng giá:

```
Giá sàn công bố LUÔN nằm trên lưới bước giá (HOSE 10/50/100 theo mức).
⇒ anchor lệch lưới ⇒ đã bị rebase ⇒ unverified.
⇒ anchor trên lưới    ⇒ dùng làm neo band.
```

`price_band.py::_off_tick_grid` đã tồn tại và đã có test. Việc cần: **đưa nó thành
public** (`is_on_tick_grid`) rồi gọi từ `_band_check` thay cho cổng `RAW`.
`tick_size` và `band_limits` đã public sẵn.

**Cộng thêm cổng thứ hai đã nằm ngay trong file này:** `_rescaled_since` (`:340-346`)
— nhánh STORE đã dùng. Nếu chuỗi corporate action **có** dòng cho mã đó trong
khoảng neo→nay thì `unverified`. Không dùng nó **một mình** (bảng chỉ phủ 29/1.522
mã, nên "không có dòng" đọc thành "không có ex-date" là sai mà tự tin — đúng lý do
Phase 06 loại phép thử này), nhưng **cộng** vào thì miễn phí: rẻ, đã tính sẵn, và
bắt được đúng phần lưới bỏ lọt.

Hai cổng, cả hai fail về `unverified` — an toàn, vì cả tool này **fail-open theo
thiết kế** và không bao giờ chặn câu trả lời.

## Phủ được bao nhiêu

Đo 2026-08-29, từ 2026-07-01, phiên có khớp lệnh:

| Sàn | Phiên trên lưới |
|---|---|
| HOSE | **91,52%** |
| HNX | 89,33% |
| UPCOM | không liên quan — `_band_check` đã trả `unverified` cho UPCOM từ trước (neo là VWAP, store không có) |

Từ **0%** lên **~91%** trên sàn mà toàn bộ 30 mã declared đang niêm yết.

## Giới hạn phải khai, không được ỉm

Trên-lưới là **điều kiện cần, không đủ** — một giá rebase bởi hệ số chẵn vẫn có thể
rơi đúng lưới. Hệ quả xấu nhất: một verdict `within_band` sai trên một giá đáng lẽ
`unverified`.

Bị chặn lại bởi ba thứ: cổng `_rescaled_since` bắt phần lớn phần còn lại · đây là
1 trong 3 check chứ không phải phán quyết duy nhất · tool fail-open, không chặn
câu trả lời. Câu này phải vào docstring, đúng như Phase 06 đã làm.

## Việc cần làm

1. `price_band.py`: `_off_tick_grid` → public `is_on_tick_grid`, docstring nêu
   cần-không-đủ (đã viết sẵn ở bản private).
2. `price_check.py::_band_check`: thay cổng `:369` bằng hai cổng trên; thông điệp
   `unverified` mới nói **giá lệch lưới**, không nói "stored adjusted at source".
3. Test: neo trên lưới → verdict thật · neo lệch lưới → `unverified` · có ex-date
   giữa neo và nay → `unverified` · UPCOM vẫn `unverified` như cũ.
4. Sửa dòng nợ trong `CLAUDE.md` + `docs/roadmap.md` khi xong.

Ước lượng: nhỏ. Luật, cơ chế và test pattern đều đã có từ Phase 06.

---

# Cái sửa cả hai, nếu muốn đi đường dài

Cả hai đề xuất trên là **giải pháp trong giới hạn "store chỉ giữ giá đã điều
chỉnh"**. Nguyên nhân gốc chung: `bar_daily` giữ **một** cột giá, đã adjusted.

Giữ thêm giá danh nghĩa (chưa điều chỉnh) cạnh giá đã điều chỉnh sẽ đóng **bốn** món
cùng lúc:

| Món | Hôm nay | Nếu có giá danh nghĩa |
|---|---|---|
| BAND của `check_price_claim` | chết | đúng 100%, không cần suy từ lưới |
| `band_pressure` | 80,71% trên 30 mã declared | ~100% |
| `traded_value` suy diễn | p95 lệch 20,4% (60 phiên) | tiền thật, không còn ước lượng |
| So tiền giao dịch giữa các năm | không làm được | làm được |

Chi phí: một cột + đổi ingest + backfill lại. **Không** thuộc plan này, và không
nên bị nhồi vào. Nêu ra vì ba trong bốn món trên đang là nợ đã ghi ở ba chỗ khác
nhau — nếu món thứ tư xuất hiện thì đây là lúc so chi phí một lần thay vì vá lần
thứ tư.

---

# Câu chưa giải quyết

1. Trần req/phút thật của tier đang dùng — tôi lấy **180 (Bronze)** từ `CLAUDE.md`.
   Nếu đã lên Diamond thì `min_interval` phải theo 600, và `market` xuống ~2,5 phút.
2. Máy dev có bật liên tục không? Nếu ngủ về đêm thì `launchd` (chạy bù job miss)
   là lựa chọn đúng, `cron` thì không.
3. Nhịp scope `market`: hằng ngày (screener luôn tươi) hay hằng tuần (tiết kiệm
   ~1.500 call/ngày)? Phụ thuộc `earnings_dislocation` scope market được dùng
   thường xuyên tới đâu — cái này tôi không đo được từ code.

---

# Đã thi công 2026-08-29 — và hai chỗ đề xuất trên tự sai

`make test` **1441 passed** (từ 1423, +18 case) · `make lint` ✓ · web
`type-check` + `lint` + `test` (737) + `build` ✓ · API restart sạch, hai dòng log
mới đúng như thiết kế.

Amendment freeze ghi trước khi sửa: hai file, mỗi file một giới hạn
(`CLAUDE.md` §"Mở thêm 2026-08-29").

## Đề xuất 1 sai ở bước 1 — đã có arbiter, không được dựng pacer thứ hai

Bản đề xuất viết: *"một `min_interval` suy từ trần req/phút, đặt ở
`vnstock_daily`"*. **Sai.** `src/core/quota.py` (ADR-0014) đã là một arbiter đơn
nhất trên toàn bộ hạn mức account, và docstring của nó nói đúng lý do:

> *"Before this module there were three pacers and none of them was the quota
> … Three uncoordinated copies sharing one account allowance add up to more than
> the allowance, and vnstock answers an exhausted quota by calling `sys.exit()`."*

Thêm một pacer nữa ở `vnstock_daily` chính là lỗi module đó tồn tại để chặn. Và
`QuotaLane.BACKFILL` **đã có sẵn**, đã được `acquire` xử lý: nhường lane news, rồi
chờ slot account không giới hạn — đúng hình dạng một batch job cần.

Cũng sửa luôn một câu sai khác trong đề xuất: tôi viết "không có retry". Có —
`safe_vnstock_call` retry 3 lần với backoff 2/4/8s khi gặp `SystemExit` (cách
vnstock báo hết hạn mức). Thiếu là **pacing chủ động**, không phải phòng vệ phản ứng.

### Bẫy tránh được: đổi import là sai

`vnstock_client.py:231` đã export một `Quote` **có guard + paced**, còn
`vnstock_daily.py:61` import bản thô. Nhìn thì chỉ cần đổi import — nhưng
`safe_vnstock_call` **nuốt mọi `Exception` và trả `None`**, nên một lần bị từ chối
hạn mức sẽ thành `VnstockUnavailable` → `None` → `DailyIngestError("answered
nothing")`, mà vòng paging đọc câu đó là *"cửa sổ này trước phiên đầu tiên của mã"*.
Kết quả: mã bị đánh dấu không-đủ-sâu và bỏ qua, **im lặng, mãi mãi**.

Nên: `acquire()` tường minh trước `quote.history`, giữ nguyên semantics
`SystemExit`. Có test riêng cho đúng ca này
(`test_a_refused_slot_is_not_reported_as_an_empty_window`).

## Đề xuất 1 sai ở phần lịch — đã có seam scheduler, không cần launchd

Bản đề xuất khuyến nghị **launchd trên máy dev**, và loại compose sidecar vì
"`CLAUDE.md` vừa cố ý rip toàn bộ job infra". Đọc code thì `src/core/scheduler.py`
là một seam **được giữ lại có chủ ý**, và nó tự mời:

> *"The seam is kept because `main.py` still calls `setup_scheduler` … When the
> harness introduces its own periodic work, add it here."*

Nên không cần launchd, không cần sidecar, không thêm dep. Job đăng ký đúng vào
seam đó.

### Mặc định TẮT, và đây là chỗ dễ sai nhất

`scheduler_enabled` mặc định **`True`**. Một job đăng ký vô điều kiện sẽ tự bắt
đầu gọi provider ngoài trên **mọi** máy dựng stack lên — scope `market` là 1.523
request. Nên có setting riêng `backfill_daily_scheduled`, **mặc định `False`**, và
test khẳng định cả hai nửa: scheduler rỗng khi tắt, **và** chính setting mặc định
là `False` (để một edit sau đăng ký vô điều kiện không lọt qua).

Đã xác nhận trên app thật:

```
Daily spine: newest closed session 2026-08-27, 2 calendar days old, last read …
Scheduler configured with 0 jobs; daily spine backfill is not scheduled
  (BACKFILL_DAILY_SCHEDULED is off). Fill it by hand with `make backfill-daily …`
```

và đường bật, trên `AsyncScheduler` thật chứ không phải fake của test:

```
registered: daily-spine-backfill | CronTrigger(hour='16', minute='30',
  timezone='Asia/Ho_Chi_Minh')
```

### Thay đổi

| File | Việc |
|---|---|
| `stocks/providers/vnstock_daily.py` | `quota_arbiter().acquire()` trước `quote.history`; refusal **propagate**, không thành `None` |
| `stocks/backfill_daily.py` | `with quota_lane(QuotaLane.BACKFILL)` quanh vòng lặp — lane khai ở entry point, đúng thiết kế ADR-0014 |
| `core/config.py` | `backfill_daily_scheduled` (mặc định `False`) · `backfill_daily_hour/minute` (16:30) |
| `core/scheduler.py` | `fill_the_daily_spine()` — ba scope nối tiếp qua `asyncio.to_thread`, không raise ra ngoài; `setup_scheduler` gate theo setting, `coalesce=latest`, `misfire_grace_time=2h` |
| `main.py` | `report_spine_freshness_at_startup()` — WARNING kèm lệnh khi stale; đọc trong thread; không bao giờ chặn startup |
| `tests/test_spine_schedule.py` (mới) | 11 case |
| `tests/stocks/daily/test_vnstock_daily.py` | 3 case pacing + fixture `_slot_is_granted` cho `TestRequestWindow` |

**Off event loop bắt buộc:** `backfill_daily.run` là sync và chờ mạng phần lớn thời
gian; await inline sẽ đứng toàn bộ request process đang phục vụ suốt scope market.

**`TestRequestWindow` chuyển đỏ và đó là tín hiệu đúng:** hai case đó gọi
`fetch_daily` trực tiếp và arbiter fail-closed khi không có Redis — đúng luật
ADR-0014 (*"a Provider Source call with no arbiter is a call with no allowance"*).
Chúng đo phép tính cửa sổ, không đo quota, nên stub arbiter qua fixture có ghi lý do
— **không** nới fail-closed.

## Đề xuất 2 — đúng như đề xuất, cộng hai chỗ dọn

Làm đúng kế hoạch: `_off_tick_grid` → public `off_tick_grid`, `_band_check` thay
cổng nhãn `RAW` bằng **hai cổng giá** (lưới bước giá + `_rescaled_since`).

Hai chỗ stale phát hiện khi làm, đã sửa:

1. **Docstring module `price_band.py` sai sự thật** — vẫn nói *"Everything here
   reads `raw` prices only"*, sai từ Phase 06. Viết lại: luật là về **giá trên
   lưới**, bất kể nhãn nói gì, kèm câu mà luật cũ bỏ sót (mã không có sự kiện quyền
   thì mang đúng giá công bố dưới nhãn adjusted).
2. Một tham chiếu `_off_tick_grid` còn sót trong docstring.

### Nghiệm thu trên store thật — "nói có" chưa đủ

30 mã declared, phiên 2026-08-27:

| Check | Verdict | Số mã |
|---|---|---|
| tick | `on_tick` | 30/30 |
| **band** | **`within_band`** | **30/30** (trước: 0/30 `unverified`) |
| store | `store_agrees` | 30/30 |

Và quan trọng hơn — nó **bắt** giá bịa, thử trên VCB/FPT/HPG:

| Claim | band |
|---|---|
| giá đóng cửa thật | `within_band` |
| +9% (ngoài biên 7%) | **`exceeds_band`** |
| −12% | **`exceeds_band`** |
| ×10 | **`exceeds_band`** |

Một control chỉ trả "hợp lệ" cho mọi thứ thì vô dụng; đây là phép đo chứng minh nó
phân biệt được.

### Test

`tests/test_agent_price_check.py`: viết lại `test_an_adjusted_anchor_is_refused_...`
(tiền đề của nó chính là luật vừa thay) thành ba case — neo adjusted **trên lưới**
được dùng · neo lệch lưới `unverified` · có ex-date giữa hai phiên `unverified`.

## Docs

`CLAUDE.md`: amendment freeze · lệnh nạp spine + cảnh báo mặc-định-tắt trong
§Commands · dòng nợ BAND thay bằng luật mới có số đo. `docs/roadmap.md`: S0 ghi hai
nợ đã trả.

## Còn mở

1. **Trần req/phút không còn là câu hỏi của tôi** — arbiter đọc nó từ chính env var
   vnstock dùng (`account_spacing`, giãn theo cửa sổ chặt hơn trong hai cửa sổ
   20/60 rpm và 3000/giờ). Con số 180/600 trong `CLAUDE.md` không khớp cái arbiter
   đang thực thi; **đáng đối chiếu lại**, nhưng nó là một câu hỏi về `CLAUDE.md`
   chứ không về code.
2. **Nhịp scope `market`** — đang hằng ngày cùng hai scope kia. Nếu muốn hằng tuần
   thì tách trigger thứ hai; chưa làm vì chưa có dữ liệu về tần suất dùng
   `earnings_dislocation` scope market.
3. **Bật job** là quyết định của bạn: `BACKFILL_DAILY_SCHEDULED=true`. Tôi không tự
   bật — nó bắt đầu gọi provider ngoài hằng ngày.

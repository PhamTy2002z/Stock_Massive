# Stock_Massive

Nền tảng phân tích sâu cổ phiếu Việt Nam: người dùng chọn một số ít mã đưa vào Watchlist, hệ thống dựng Analysis — số liệu, insight, biểu đồ và nhận định — cho chính những mã đó mỗi ngày giao dịch. Không phải công cụ theo dõi toàn thị trường; có đưa nhận định vùng giá cụ thể kèm miễn trừ trách nhiệm.

## Language

### Nguồn dữ liệu

**Provider Source**:
Một nhà cung cấp dữ liệu bên ngoài mà hệ thống lấy số liệu về — hiện có `vnstock` và `fiinquant`.
_Avoid_: API, data feed, upstream

**Capability**:
Một lớp dữ liệu có thể được sở hữu bởi một Provider Source độc lập với các lớp khác: `market` (giá, khối lượng, dòng tiền), `valuation` (P/E, P/B), `reference` (sở hữu và số lượng cổ phiếu, đổi chậm), `fundamental` (báo cáo tài chính).
_Avoid_: data type, category, domain

**Snapshot**:
Một bản ghi dữ liệu đã chuẩn hoá của một mã tại một thời điểm, sau khi qua ranh giới Provider Source — luôn mang theo nguồn, `effective_at` (dữ liệu nói về lúc nào) và `observed_at` (hệ thống thấy nó lúc nào).
_Avoid_: record, row, data point

**Adapter**:
Đoạn mã dịch phản hồi thô của một Provider Source thành Snapshot. Adapter là nơi duy nhất được biết hình dạng dữ liệu của nhà cung cấp.
_Avoid_: client, wrapper, connector

**Main Source**:
Provider Source được chọn phục vụ một Capability, vì nó có dữ liệu mạnh hơn và hạn mức cao hơn cho lớp dữ liệu đó.
_Avoid_: primary, default provider

**Cover Source**:
Provider Source phục vụ phần một Capability mà Main Source không với tới — nằm ngoài Universe, sâu hơn độ sâu lịch sử được cấp, hoặc nhà cung cấp không có.
_Avoid_: fallback, backup, secondary

### Sản phẩm AI

**Watchlist**:
Danh sách mã một người dùng đã lưu để được phân tích lại mỗi Trading Day, trần 10 mã; mã đã thành `unsupported` không tính vào trần. Khác Universe: Universe là cam kết thu thập dữ liệu của hệ thống, Watchlist là lựa chọn của từng người dùng — nên trần Watchlist có mặt trong giao diện, còn trần Universe thì không.
_Avoid_: wishlist, favorites, danh mục

**Analysis**:
Bản phân tích AI của một mã cho một Trading Day — dashboard theo template cố định cộng nhận định bằng chữ. Khoá theo `(symbol, trading_day)` và dùng chung toàn hệ thống, không thuộc về người dùng nào: hai Watchlist chứa cùng một mã đọc đúng một Analysis, thêm lại một mã vừa gỡ trong cùng ngày không sinh bản mới, và gỡ mã không xoá gì. Đổi lại, Analysis không được cá nhân hoá theo người dùng.
_Avoid_: report, insight, bản tin

**Analysis Run**:
Bản ghi việc sản xuất một Analysis cho một `(symbol, trading_day)`: `pending` khi Trading Day đã có Snapshot nhưng chưa tới lượt mã này, `producing` khi đang chạy, `ready`, hoặc `failed` kèm lý do và số lần đã thử. Tách khỏi Analysis vì trạng thái thất bại của từng mã phải sống sót qua một lần restart — không có nó thì một mã fail trông y hệt một mã chưa tới lượt, và giao diện không biết có nên mời thử lại. Một Analysis Run ở `ready` luôn có nghĩa Analysis tương ứng đã tồn tại đầy đủ; trạng thái nửa vời chỉ sống ở đây, không bao giờ ở Analysis.
_Avoid_: job, task, attempt

**Thread**:
Một cuộc hội thoại giữa một người dùng và agent, giữ toàn bộ ngữ cảnh mà v1 có — ngoài Thread, v1 không có ký ức dài hạn nào. Mang theo danh sách mã nó đã chạm, để trả lời được "những Thread nào nói về FPT" mà không cần bảng nối. Thứ tự tin nhắn do một số thứ tự trong Thread giữ, không do thời điểm ghi: hai tin nhắn có thể trùng millisecond khi đang stream.
_Avoid_: conversation, chat, session

**Turn**:
Một lượt đối đáp trong một Thread: tin nhắn của người dùng, các vòng gọi tool mà agent thực hiện để trả lời, rồi câu trả lời. Là đơn vị của mọi trần trong hệ thống — trần vòng gọi tool, trần phiên đồng thời, chi phí token — và là đơn vị người dùng huỷ được. Một Turn bị huỷ hoặc chết giữa đường vẫn để lại Tool Call Trace của phần đã chạy.
Sau khi được tiếp nhận, Turn thuộc về hệ thống chứ không thuộc về kết nối: tải lại trang, đổi route, đóng tab hoặc mất mạng không huỷ Turn; chỉ một yêu cầu huỷ rõ ràng mới làm điều đó.
_Avoid_: request, exchange, round

**Tool Call Trace**:
Bản ghi một lần agent gọi tool — tên, tham số, kết quả, độ trễ, token, lỗi. Neo vào tin nhắn của người dùng đã khởi phát Turn đó, vì tin nhắn ấy đã tồn tại trước lần gọi đầu tiên còn câu trả lời thì chưa. Đủ để đọc lại chuỗi quyết định của agent, nhưng không cam kết chạy lại ra kết quả cũ: dữ liệu trong store đổi mỗi đêm và model không tất định.
_Avoid_: log, audit, span

**Capability Probe**:
Bài kiểm tra hợp đồng chạy lúc khởi động trên tuyến LLM đang cấu hình: buộc `tool_choice`, gọi tool song song khi stream, structured output, và một vòng tool khép kín. Tuyến nào không qua thì hệ thống từ chối khởi động và in lý do, thay vì chạy với một tuyến âm thầm bỏ rơi tham số. Tồn tại vì lớp dịch của gateway từng bỏ im lặng đúng những tham số này — thất bại kiểu đó không lộ ra ở runtime, nó chỉ làm câu trả lời sai đi.
_Avoid_: health check, smoke test, ping

**Widget**:
Một phép chiếu trực quan có kiểu và phiên bản của các registered fields trong một
Turn. Widget trình bày số liệu nhưng không tự tính số liệu, không thay thế
Analysis hoặc bề mặt dữ liệu của Stock 360, và giữ nguyên ngữ cảnh dữ liệu lịch
sử của câu trả lời khi Thread được mở lại.
_Avoid_: chart, visualization, graphic

### Phạm vi phục vụ

**Universe**:
Tập hợp mã mà hệ thống cam kết thu thập và phân tích, trần 100 mã. Trần là van an toàn cho collector — thời gian chạy và sức chịu của gateway — chứ không phải hạn mức bán cho người dùng, nên không xuất hiện trong giao diện.
_Avoid_: watchlist, danh mục, market coverage

**Backfill**:
Lần nạp lịch sử duy nhất cho một mã mới vào Universe, lấy phần sâu hơn khả năng của Main Source từ Cover Source. Chạy một lần rồi thôi; từ đó Main Source nối tiếp mỗi ngày.
_Avoid_: import, sync, migration

**Warm-up**:
A repeatable load of recent Main Source market history that makes a new or
repaired Universe member evaluable without waiting for daily collection to
accumulate 21 Trading Days. It is bounded to the recent signal window and is
separate from the one-time, multi-year Backfill.
_Avoid_: backfill, deep history, daily collection

**Collector**:
Tiến trình chạy sau phiên, là nơi duy nhất được gọi ra Provider Source. Request của người dùng không bao giờ chạm tới nhà cung cấp.
_Avoid_: job, worker, crawler

**Trading Day**:
Một ngày mà hệ thống có Snapshot EOD — `date(max(effective_at))` trong `provider_snapshots`, chứ không phải một ngày trên lịch. Định nghĩa theo dữ liệu vì hệ thống không có lịch nghỉ lễ: `is_trading_day()` chỉ biết thứ trong tuần nên đọc Tết thành ngày giao dịch, và một Analysis đóng nhãn một phiên không tồn tại thì không diff được với bản của phiên sau.
_Avoid_: session date, ngày giao dịch theo lịch

### Market signals

These terms define the bounded cohorts, data readiness, and provenance of
derived end-of-day market signals.

**Profit Leaders Cohort**:
A dynamic set of exactly 50 currently listed HOSE or HNX equities ranked by
trailing-12-month net income attributable to the parent company at one common
reporting period. It reserves 50 places in the Universe and becomes active only
when at least 45 members have enough market history for evaluation.
_Avoid_: Top 50 list, profitable stocks, market-wide Universe

**Cohort Version**:
An immutable Profit Leaders Cohort membership tied to one Rankable Reporting
Period and census result. A version is `candidate` while its members receive a
Warm-up and `active` once its Signal Coverage permits serving it; activation
never rewrites an older version.
_Avoid_: current list, cached ranking, latest Top 50

**Profit Ranking Census**:
A periodic market-wide read of only the profitability, reporting-period,
exchange, and listing-status fields needed to form the Profit Leaders Cohort.
It does not place every censused symbol in the Universe or collect market data
for it.
_Avoid_: full-market collection, fundamental backfill, market scan

**Rankable Reporting Period**:
A common reporting period with valid profitability data for at least 95% of
currently listed HOSE and HNX equities. The active ranking stays on the previous
period until the newer period reaches this threshold.
_Avoid_: latest filing, mixed period, newest row

**Volume Spike**:
A signal for one Trading Day whose volume reaches a configured multiple of the
average volume across exactly the 20 immediately preceding Trading Days. An
explicit zero-volume Snapshot is part of the baseline; a missing Snapshot makes
that symbol unevaluable.
_Avoid_: volume anomaly, unusual volume, volume surge

**Signal Coverage**:
The share of a signal cohort that is evaluable for one Trading Day. A
Profit Leaders Cohort result is `ready` at 50 of 50 symbols, `partial` at 45 to
49 symbols, and `insufficient_data` below 45 symbols; an All Universe result is
`ready` at 100%, `partial` at 90% or more, and `insufficient_data` below 90%.
_Avoid_: symbols processed, success rate, data availability

**Signal Scope**:
The cohort a Volume Spike query evaluates: `profit_leaders` for the active
Profit Leaders Cohort or `universe` for the entire bounded Universe. An exchange
filter on `universe` narrows both the evaluated members and the Signal Coverage
denominator.
_Avoid_: top-profitable-only, data source, tab

**Signal Trading Day**:
The newest Trading Day on which at least 45 Profit Leaders Cohort members are
evaluable. It can trail the newest market Snapshot while a newer day is still
below the Signal Coverage threshold.
_Avoid_: today, current date, latest row

**Signal Freshness**:
How the Signal Trading Day relates to stored market data and elapsed time:
`fresh` when it is the newest market Trading Day, `lagging` when a newer market
Trading Day exists but lacks Signal Coverage, and `stale` when the signal data
is more than seven calendar days old. It is independent of Signal Coverage.
_Avoid_: status, cache age, last refreshed

**Signal Issue**:
A stable, machine-readable condition explaining why a symbol or result is not
ordinary and complete, such as `missing_target_session`,
`insufficient_history`, `recently_inactive`, `cohort_warming`,
`lagging_market_data`, `stale_market_data`, or `ranking_unavailable`. It is
domain provenance, not an HTTP or infrastructure error.
_Avoid_: error message, warning text, exception

**Recently Inactive**:
A symbol with at least one explicit zero-volume Snapshot in the 20-Trading-Day
Volume Spike baseline. Its signal remains evaluable but carries this condition
so a return from suspension or inactivity is not presented as ordinary flow.
_Avoid_: missing volume, insufficient history, halted

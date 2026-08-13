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

### Corporate actions

These terms fix what a stored price means with respect to corporate actions, and
how a raw price becomes a comparable one.

**Price Basis**:
What the price fields of one Snapshot mean with respect to corporate actions:
`raw` for exactly what the exchange published for that session, or
`adjusted_at_source` for prices the Provider Source rescaled as of `observed_at`.
Declared by the Adapter that wrote the Snapshot, because it is the only code that
knows which flag it passed — not by a config flag, which rows already written do
not follow when it flips, and not by a session date, because each symbol's seam
falls where its own Backfill happened to run. Only price fields have a basis:
traded quantity and traded money are raw in every Snapshot.
A stored Snapshot always carries one of the two. `mixed` is not a third basis
and is never stored: it is what an aggregated bar on the market series reports
when the sessions it folds do not share one, so a weekly bar straddling the seam
names neither side. Where a **Signal Issue** says `mixed_price_basis` the same
condition is being refused rather than served — a chart may draw two scales
labelled as such, a computation may not run across them.
_Avoid_: adjusted flag, split-adjusted, convention

**Corporate Action**:
An event that changes a symbol's share count or its reference price at one
ex-date — a split, a bonus or share dividend, a rights issue, a cash dividend —
carrying the exercise ratio a share-count change needs, which a dividend record
alone does not. It is `confirmed` only once a raw price gap in the store
corroborates its ex-date, and an `unconfirmed` one may not drive arithmetic. A
share-count change breaks the comparability of traded quantity; a cash dividend
does not, and traded money survives both.
_Avoid_: dividend, event, split

**Adjustment Factor**:
The ratio that turns a raw price into one comparable across a Corporate Action,
applied when a window is read rather than when a session is stored. Computed from
the action's declared exercise ratio and value per share; the raw price gap at the
ex-date only confirms the date and never supplies the factor, since that gap is
the entitlement and the session's ordinary move together. It applies to price
fields only — there is no quantity equivalent, and none is wanted.
_Avoid_: split ratio, multiplier, adjustment

### Sản phẩm AI

**Intelligent Quant**:
Tính năng agent AI đặt bên trên đường dữ liệu đã có: một agent gọi tool, stream
câu trả lời, giữ Thread, và sinh Widget, ngồi trên một đường ống Analysis tất định
chạy mỗi đêm. `Intelligent Quant` là tên trong mã và trong tài liệu; **Alpha Desk**
là nhãn người dùng thấy trên sidebar và là tab đầu tiên. Không phải chatbot: mọi
ticket biến nó thành "nhập prompt, trả text" đều đọc sai đích đến.
_Avoid_: chatbot, AI assistant, copilot

**Watchlist**:
Danh sách mã một người dùng đã lưu để được phân tích lại mỗi Trading Day, trần 10 mã; mã đã thành `unsupported` không tính vào trần. Khác Universe: Universe là cam kết thu thập dữ liệu của hệ thống, Watchlist là lựa chọn của từng người dùng — nên trần Watchlist có mặt trong giao diện, còn trần Universe thì không.
_Avoid_: wishlist, favorites, danh mục

**Analysis**:
Bản phân tích AI của một mã cho một Trading Day — dashboard theo template cố định cộng nhận định bằng chữ. Khoá theo `(symbol, trading_day)` và dùng chung toàn hệ thống, không thuộc về người dùng nào: hai Watchlist chứa cùng một mã đọc đúng một Analysis, thêm lại một mã vừa gỡ trong cùng ngày không sinh bản mới, và gỡ mã không xoá gì. Đổi lại, Analysis không được cá nhân hoá theo người dùng.
_Avoid_: report, insight, bản tin

**Analysis Field Profile**:
Danh sách có phiên bản các **Signal Field** mà đường ống Analysis được phép đưa vào
một Analysis, tối đa 6 field mỗi trục, chia theo ngành. Tồn tại vì model không được
chọn tự do trong toàn bộ **Signal Registry**: bundle đầu vào phải ổn định, xem lại
được và có biên. Một field thuộc profile nhưng chưa hiện thực vẫn phải xuất hiện ở
trạng thái `refused` — bỏ im lặng sẽ làm hai Analysis cùng `profile_version` nói hai
điều khác nhau.
_Avoid_: field list, template fields, schema

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

### Agent surface

These terms fix what the agent may reach, what it may say, and what survives an
answer once it is disputed.

**Tool Catalog**:
The twelve semantic tools that are the agent's entire reach into `apps/api` — six
data, five computation clusters, one identity-scoped. Semantic, not a wrapper set:
an endpoint's name and parameters are shaped for a page's data needs, a tool's for a
model to choose correctly. It is versioned, because its schemas are part of the
cacheable prompt prefix and part of what an Eval Fixture was frozen against.
_Avoid_: tools, API surface, function set

**Tool Context**:
The out-of-band record of who is asking, injected into a tool call by the harness and
never present in a tool's model-visible schema. `get_watchlist()` is the only tool
that reads it. Identity is out of band so that asking for another user's data is not
a refused request but an unexpressible one.
_Avoid_: user param, session, auth context

**Data Reference**:
A handle to a series a tool declined to return — symbol, range, field, fixed date —
which the visualization layer resolves through the authenticated boundary. `data_ref`
in code. It exists because the model may receive summary statistics and never raw
bars; it is also the no-network data-in mechanism a future sandbox would need, which
is why it is kept even though code execution is out.
_Avoid_: series id, pointer, cache key

**Structured Refusal**:
A tool's typed answer that a request lies outside what the system serves — most often
`{reason: "not_in_universe", suggestions: [...]}` with up to three same-ICB Universe
symbols ordered by descending ADTV. It is computed by query in the tool layer, never
produced by the model, and it lists what *is* available rather than only saying no.
_Avoid_: error, rejection, not_found

**System Prompt Contract**:
The versioned artifact holding the agent's behavioural core: mission, non-overridable
invariants, the **Recommendation Gate**, tool-use policy, output protocol, voice, and
trusted runtime context, with a fixed precedence when they conflict. It is the core of
behaviour and never the enforcement mechanism — each invariant is proven by the
narrowest layer able to prove it, and the model cannot certify that it passed one.
_Avoid_: system prompt, instructions, persona

**Recommendation Gate**:
The set of conditions a recommendation block must satisfy before it may be released:
Universe membership, an explicit Trading Day and reference price, price zones that are
registered fields computed in code, **Window Health** that is not a refusal, at least
one cited suitable field with material contradictory evidence exposed, full metadata on
every cited field, and news never as a sole directional basis. A block that fails is
never displayed and flagged afterwards — the Turn ends `incomplete` with reason
`grounding_failed`.
_Avoid_: guardrail, safety check, validation

**Risk Notice**:
The versioned notice the backend attaches to every completed or useful incomplete
assistant message, independently of model output. The renderer displays it; the model
cannot omit it, rewrite it, or satisfy it with prose of its own. Attached rather than
prompted, because a disclaimer enforced by prompt is a model behaviour measured after
the fact instead of a property of the system.
_Avoid_: disclaimer, legal text, footer

**Evidence Manifest**:
The immutable record kept with each assistant message so a disputed answer can be
re-read: prompt version and hash, deployment SHA, exact model and route, catalog and
schema versions, cited fields with value, unit, source and `as_of`, Risk Notice
version, validator outcomes, and the terminal state. Kept indefinitely, unlike the
90-day **Tool Call Trace**, and it holds no credentials, no hidden reasoning, and no
copy of the prompt text.
_Avoid_: audit log, metadata, provenance

### Answer quality

**Eval Battery**:
The fixed set of `Eval Case`s measuring what the runtime cannot prove — false
refusal, scope refusal, interpretation fidelity, contradictory-evidence exposure,
injection resistance, and regression — run over both free-form surfaces, the agent
Turn and the nightly Analysis prose. It is not a growing scoreboard: cases are seeded
once and afterwards enter only through a confirmed flagged message.
_Avoid_: test suite, benchmark, probe set

**Eval Fixture**:
A frozen snapshot of the store at one Trading Day, loaded into a dedicated eval
database and carrying the registry, profile, catalog and schema versions it was frozen
against — refusing to run on a mismatch. The tool layer, `prepare_bars()`, and the
Signal Registry are the real ones, so the model is the only non-deterministic element.
Frozen because the store changes every night, and a run on live data cannot separate a
worse model from moved data.
_Avoid_: test data, seed, mock store

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
derived end-of-day market signals, and the bar one must clear before any surface
may cite it.

**Signal Field**:
One model-visible number, and the unit the statistical bar applies to — not the tool
that returns it, because one tool returns fields of different kinds. It declares
`unit`, `sign`, `interpretation`, `kind` (`estimator` | `percentile` | `signal`),
**Claim**, `source` (`computed` | `stored`), `min_sessions`, `threshold`, and
`null_fpr`. Its `interpretation` is the only sanctioned reading of it.
_Avoid_: metric, indicator, value

**Signal Registry**:
The single place a **Signal Field** is declared, and the reason an unregistered
computation needs no prohibition: the tool layer serializes registered fields only, so
a field that fails the bar simply has no route to a model. It lives at domain level
because the nightly Analysis cites through it too — otherwise the artifact people read
every day would be the unguarded one.
_Avoid_: field catalog, schema registry, metric list

**Window Health**:
What `prepare_bars()` returns beside the frame, and what every computation echoes:
`sessions_used`, `limit_lock_days`, `band_regime`, `adjustment`, `adtv_percentile`. It
exists so the Vietnamese-market hazards are enforced by construction rather than by a
review checklist — one gateway to bars, one honest report of what that window was
made of.
_Avoid_: data quality, window status, coverage

**Null Calibration**:
Measuring how often a `signal` field fires on data that contains no signal, against
two nulls — matched-volatility GBM with and without the ±7% truncation, and a
stationary block bootstrap on the symbol's own returns — with the published rate the
max of the two and the catalog-wide ceiling a fixed 1%. The threshold is *derived*
from the null offline and frozen, never calibrated at runtime, which would make it a
function of today's data.
_Avoid_: backtest, significance test, validation

**Claim**:
What a **Signal Field** asserts: `descriptive` or `predictive`. In v1 every field is
`descriptive`, and that is a schema constraint rather than a label — a descriptive
field may not return a direction-bearing key at all. `predictive` unlocks only behind
a measured net-of-cost forward-return harness.
_Avoid_: confidence, accuracy, signal type

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
`lagging_market_data`, `stale_market_data`, `ranking_unavailable`,
`mixed_price_basis`, `unadjustable_price_basis`, `unexplained_price_gap`,
`volume_basis_break`, or `unconfirmed_corporate_action`. It is domain provenance,
not an HTTP or infrastructure error.
_Avoid_: error message, warning text, exception

**Recently Inactive**:
A symbol with at least one explicit zero-volume Snapshot in the 20-Trading-Day
Volume Spike baseline. Its signal remains evaluable but carries this condition
so a return from suspension or inactivity is not presented as ordinary flow.
_Avoid_: missing volume, insufficient history, halted

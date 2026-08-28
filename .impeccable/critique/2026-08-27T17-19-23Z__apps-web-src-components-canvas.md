---
target: canvas surface — branded mode name, toggle gating, paid entitlement
total_score: 17
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 3
timestamp: 2026-08-27T17-19-23Z
slug: apps-web-src-components-canvas
---
Method: dual-agent (A: design-review · B: detector-evidence)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 2 | Không có state "Study đang chạy". `canvas.ready` chỉ bắn lúc commit; trước đó user không biết có bảng sắp tới. Khi tab bị pin, canvas được lưu **im lặng**, tab "Phân tích" không có dot/count. |
| 2 | Match System / Real World | 3 | `formatNumber` tỷ/tr/ng, `vi-VN` date, "Đạt/Chưa đạt/Chưa rõ" đúng domain. Nhưng "khối" là từ của lập trình viên, và tab tên "Phân tích" — một từ không có bản sắc sản phẩm. |
| 3 | User Control and Freedom | 2 | Không có gì được opt-in. `close-inspector` xoá luôn `inspectorPinned`, nên canvas kế tiếp lại bật panel người đọc vừa đóng. |
| 4 | Consistency and Standards | 1 | `--chart-1` **byte-identical** với `--primary` (Ignition Amber); `--chart-3` = Ceiling Violet (trần); `--chart-5` = Floor Cyan (sàn). Cả hai Named Rule của DESIGN.md bị phá cùng lúc. |
| 5 | Error Prevention | 2 | Phòng lỗi phía dữ liệu xuất sắc. Phía tương tác: `retry: false` trên artifact query → một blip mạng cho panel chết vĩnh viễn kèm chẩn đoán chưa xác minh ("có thể thuộc hội thoại khác"). |
| 6 | Recognition Rather Than Recall | 2 | `canvasArtifactId` là **một slot**. Thread ba Study chỉ giữ cái mới nhất; không backlink từ panel về câu trả lời. Sort của `data_table` mất khi đổi tab. |
| 7 | Flexibility and Efficiency | 1 | Không phím tắt nào tới canvas. `role="tablist"` khai ARIA mà không có roving tabindex/arrow key/`aria-controls`/`role="tabpanel"`. `toggle-inspector-wide` có trong reducer, **không control nào dispatch**. |
| 8 | Aesthetic and Minimalist | 2 | Ngôn ngữ tiết chế đúng hệ. Nhưng render thật ở 420px: `bar_series` bỏ phí ~80% khung, heatmap đọc như thiếu dữ liệu, nhãn trục cắt giữa chừng (`14:4`), `data_table` cắt cột không có affordance cuộn. |
| 9 | Error Recovery | 1 | `health: unavailable` chỉ ra chữ "không đọc được" + `reason` ở **vị trí thứ năm** của một dòng meta. Không retry, không "hỏi cách khác", không nói input nào thiếu. |
| 10 | Help and Documentation | 1 | Gần như bằng 0. Không giải thích Study là gì, "30 phiên" ảnh hưởng độ tin ra sao, bốn dải heatmap đo gì, hay hai đường median của `scatter_quadrant` là median. |
| **Tổng** | | **17/40** | **Below average — nền lý luận tốt, lớp trình bày chưa được thiết kế** |

## Design Specificity Verdict

**Bất biến thì độc quyền. Bề mặt thì hàng chợ.**

**LLM assessment.** Luật null-vs-zero được thực thi **năm lần độc lập** — `frame.ts::numberAt` trả `null`, `bar-series` lọc điểm null, `line-series` `connectNulls={false}`, heatmap vẽ ô trống thành rect gạch đứt có swatch riêng "không có dữ liệu", `data-table` in em dash. Không thư viện chart nào làm vậy; mọi heatmap có sẵn đều zero-fill. Đó là luận điểm sản phẩm được vẽ ra thành pixel.

Nhưng lớp render thì rời khỏi DESIGN.md: **Newsreader không xuất hiện** (heading panel là `text-sm font-medium`), **JetBrains Mono không xuất hiện** (mọi con số là Inter + `tabular-nums`). Bề mặt sinh ra để *so sánh số* lại không dùng hệ chữ được xây để so sánh số. `chart-theme.ts` là recharts default nhuộm lại; chiều cao `h-52`/`h-56` không thuộc thang spacing nào. Icon là lucide nguyên bản — trong khi `composer.tsx` **tự tay vẽ** `WaveformIcon` với lý do "matching a design by eye is how two surfaces drift apart". Canvas không được chăm như vậy.

**Deterministic scan.** `detect.mjs` trả **0 finding, exit 0** trên canvas (13 file), shell (17 file), composer, dev fixture, và cả `apps/web/src`. Đây **không phải** bằng chứng sạch: detector khớp literal CSS (`cubic-bezier`, `font-family:`, hex, `box-shadow:`), còn codebase gần như 100% Tailwind utility nên phần lớn ruleset không có gì để khớp. Đã kiểm chứng detector thật sự chạy bằng một file bẫy (2 finding `bounce-easing`, đúng số dòng) và chạy lại với `--no-config --no-design-system` vẫn `[]`. Đọc số 0 này là "không có anti-pattern CSS literal", không phải "không có vấn đề thiết kế".

**Visual.** Không inject overlay nào và tôi không tuyên bố có. Bằng chứng là **render thật** qua drawer `canvas fixture` ở 420px, console sạch (đúng 1 INFO của React DevTools). Phát hiện thị giác: `ranked_bars` màu **tím** trong khi mọi widget khác cùng artifact màu **cam** — series color không nhất quán trong cùng một canvas; trục giá trị của `ranked_bars` nằm **dưới** còn của `bar_series` nằm **trái**; bar dài nhất bị cắt ở mép panel.

## Overall Impression

Phần khó đã làm xong và làm giỏi: engine tính, artifact giữ số, registry vẽ, và luật "ô trống ≠ số 0" được bảo vệ ở năm chỗ. Phần dễ thì chưa làm: màu, chữ, opt-in, và cái tên.

Cơ hội lớn nhất không phải thêm widget. Là **đảo ngược thứ bậc**: hôm nay *lời khẳng định* to (biểu đồ vẽ bằng màu thương hiệu) còn *bằng chứng* nhỏ (provenance ở mực yếu nhất, wrap, đứng thứ sáu sau dấu `·`). Với sản phẩm tự nhận là evidence-led, đó là ngược.

## What's Working

1. **Null-vs-zero, thực thi năm lần và có biện hộ bằng văn xuôi.** Đây là thứ xây dựng niềm tin mạnh nhất trong codebase — và người dùng **không bao giờ được biết nó tồn tại**. Bạn xây xong uy tín rồi giấu biên lai.
2. **Đường degrade nằm trong dev fixture, không chỉ trong test.** `canvas-fixture.tsx::DEGRADED` cố tình ship `session_heatmap v99` và `bar_series` trỏ sai frame, nên mỗi lần mở drawer là **nhìn thấy** đường hỏng. Cộng với `resolveWidget` không bao giờ trả null và test khớp registry với `contracts/canvas-widget-catalog.json` — câu chuyện version-tolerance là hoàn chỉnh chứ không phải nguyện vọng.
3. **UI từ chối quyền năng để bảo vệ một luận điểm.** `condition_checklist` cố tình không phải bảng để không ai sort theo status rồi đọc số tick thành điểm; click thứ ba của `data_table` trả về thứ tự gốc của Study; `scatter_quadrant` cố định kích thước điểm vì "đại lượng thứ ba mã hoá bằng diện tích là một tuyên bố không ai đo". Ba chỗ chủ động bỏ tính năng dễ.

## Priority Issues

### 1. [P0] Canvas tự vẽ mình bằng màu thương hiệu và bằng màu trạng thái bảng giá

`--chart-1` == `--primary` == Ignition Amber, và nó là series dẫn ở sáu widget. `--chart-3` == Ceiling Violet (**trần**) chạy `ranked_bars`. `--chart-5` == Floor Cyan (**sàn**) chạy series phụ của `line_series`.

**Why it matters:** với nhà đầu tư Việt, thanh xếp hạng màu tím nói *trần*, đường cyan nói *sàn*. Màu đang phát ra tín hiệu thị trường mà không ai đo. Và amber lẽ ra là tín hiệu hành động khan hiếm thì đang tô kín biểu đồ.

**Fix:** bảng màu đúng **đã tồn tại** ở `globals.css:440-466` — `--widget-series` (Widget Blue), `--widget-track`, `--widget-grid`, `--widget-axis`, `--widget-focus` — kèm comment cấm đúng việc này. `grep -rl widget-series src/` trả về **đúng một file: chính `globals.css`**. Trỏ lại toàn bộ widget vào `--widget-*`, giữ `--widget-focus` (amber) cho đúng một hàng/điểm mà câu trả lời đang nói tới.

**Suggested command:** `/impeccable colorize`

### 2. [P0] Trên mobile, canvas chiếm trọn màn hình, không ai yêu cầu, giữa lúc đang trả lời

`inspector.tsx` đặt `width: compact ? "100%"` + `fixed`, còn `desk-state.tsx` dispatch `canvas-ready` vô điều kiện. Tệ hơn: `close-inspector` xoá luôn `inspectorPinned`, nên hành vi "tự mở một lần" reset sau mỗi lần đóng — canvas kế tiếp lại bật đúng panel người đọc vừa dẹp.

**Why it matters:** hành động cuối cùng bề mặt này làm là **ghi đè hành động chủ ý gần nhất của người đọc**. Theo peak-end, đây là cái kết tệ cho một feature có peak tốt.

**Fix:** dưới 768px, `canvas-ready` không mở panel — chỉ làm sáng `CanvasCard` trong transcript. `close-inspector` ngừng xoá `inspectorPinned`; một lần dẹp có hiệu lực cho cả thread.

**Suggested command:** `/impeccable adapt`

### 3. [P1] Không có opt-in, không có lời hứa, không có trạng thái đang chạy

Đây là brief item 2 và heuristic 1 — cùng một lỗi. Không có gì báo Study đang được tính, và không có cách nào để **yêu cầu** một Study.

**Fix:** pill toggle trong composer (spec đầy đủ ở mục "Toggle" bên dưới). Một control giải quyết cả hai.

**Suggested command:** `/impeccable shape`

### 4. [P1] Biểu đồ không tiếp cận được dưới dạng dữ liệu — trái với chính docblock của nó

Comment của `session-heatmap` khẳng định "the table underneath is what a screen reader reads" — **không có bảng nào bên dưới**. Comment của `bar-series` nói số "reachable as a table through the panel's fallback" — fallback chỉ chạy khi degrade. Năm trong chín widget là một `role="img"` mà nhãn chỉ gọi tên *series*, không phải giá trị.

**Fix:** thêm disclosure "Xem dạng bảng" mỗi block, render `DataTableWidget` trên chính frame đó. Gần như miễn phí: component đó đã là fallback và đã nhận cả ba kind.

**Suggested command:** `/impeccable harden`

### 5. [P1] "Visgnite Pro" là affordance lừa người, đặt đúng chỗ tin cậy nhất

`composer.tsx:182-185` là một `<span>` mang `ChevronDown`, không handler, không state, và `hidden … md:flex` nên biến mất dưới 768px. `account-menu.tsx:70-72` có "Gói & hạn mức" **disabled**. `AttachMenu` bảy dòng **disabled hết**, trong đó có dòng tên **"Nghiên cứu sâu"** — bản dịch chết của Deep Research nằm ngay cạnh chỗ bạn sắp đặt tên thật.

**Why it matters:** đây là nơi tier badge phải sống. Trước khi bán được gì, chỗ này phải thật.

**Fix:** biến thành `<button>` thật mở account menu có tên gói + "Quản lý gói", ở **mọi** breakpoint. Xoá dòng "Nghiên cứu sâu" trong cùng commit đặt tên mới.

**Suggested command:** `/impeccable distill`

### 6. [P2] Đơn vị số bị ghép lai thành vô nghĩa

Fixture thật: `["Khối lượng trung bình", 380000.0, "shares"]`. `frame.ts::formatNumber` nướng hậu tố độ lớn tiếng Việt vào **giá trị** (`380000/1e3` → `"380,00 ng"`), còn frame mang **đơn vị** riêng (`"shares"`, từ `intraday_liquidity.py:80 _UNITS`). Kết quả trên màn hình: **"380,00 ng shares"** — nửa Việt nửa Anh, và "ng" đọc lẫn với "người"/"ngày".

**Fix:** một trong hai lớp được quyền nói về độ lớn, không phải cả hai. Và `"shares"` là **dữ liệu**, phải theo luật narration tiếng Việt của `copy.ts` → "cp".

**Suggested command:** `/impeccable clarify`

### 7. [P2] Copy của canvas trốn khỏi `copy.ts`

Tám câu empty-state viết rải ở tám file, cộng hai câu trong `canvas-panel.tsx`, và `canvas-block.tsx` in chẩn đoán của lập trình viên cho nhà đầu tư: *"chưa vẽ được session_heatmap v99"*. Chính file `copy.ts` viết: "In one file because each of them is a promise."

**Suggested command:** `/impeccable clarify`

## Persona Red Flags

**Chị Mai, 34 — nhà đầu tư cá nhân, HPG/SSI, xem trên điện thoại giờ nghỉ trưa.**
- Panel nuốt trọn màn hình khi câu trả lời còn đang gõ; mất chỗ đang đọc, đóng xong lần sau lại bị.
- `ranked_bars` màu tím-trần: chị đọc biểu đồ xếp hạng thành danh sách mã trần.
- "4 khối" vô nghĩa — chị đếm mã, không đếm block.
- Khi refuse, chị thấy mấy mảnh chữ xám ngăn bởi `·` kết thúc bằng một `reason` chưa dịch, và kết luận app hỏng chứ không phải dữ liệu mỏng.
- Cột lẻ của heatmap không có nhãn, `<title>` hover không tồn tại trên cảm ứng.

**Anh Dũng, 41 — analyst quỹ nhỏ, desktop, người sẽ thực sự trả tiền.**
- Không lấy số ra được: không copy, không CSV, không wide mode (case có trong reducer, không control nào gọi).
- Mất sort của `data_table` mỗi lần ghé tab "Nguồn" rồi quay lại — im lặng.
- Không so được hai canvas trong một thread; cái sau đè cái trước.
- Đi tìm thứ mình trả tiền, bấm "Visgnite Pro", **không có gì xảy ra** vì đó là `<span>`.

**Người dùng screen-reader / thị lực thấp.**
- Năm trong chín widget là một `role="img"` không có đường tới giá trị.
- Thang bốn dải của heatmap chỉ khác nhau bằng opacity (0.18/0.42/0.68/0.95 của cùng một hue); dải 0.18 gần như không tách khỏi ô trống `surface-sunken` — mà phân biệt "bucket ế nhất" với "không có bucket" chính là lý do widget này tồn tại.
- `title=` là đường duy nhất tới evidence của `condition_checklist`.
- Accessible name bằng tiếng Anh trong sản phẩm tiếng Việt: `"Chat inspector"`, `"Resize inspector panel"`, `"Close inspector"`.

## Minor Observations

- `stat_tiles` khoá `grid-cols-2` ở mọi bề rộng tới 760px.
- `range_strip` dùng `preserveAspectRatio="none"`: ở 760px, đường 2px "đọc được tới từng pixel" render ra ~6px.
- `ranked_bars` cắt ở `MAX_ROWS = 8` không có ghi chú "còn N mục" — không phân biệt được top-8 với danh sách đầy đủ.
- `session-heatmap` `ROW_LABEL = 62` cố định; row key dài cắt vào ô đầu.
- `ageInDays` so `asOf` UTC với `Date.now()`, nên canvas đóng băng sáng nay có thể đọc thành "1 ngày trước" lúc đêm.
- `frozen` đặt `pointer-events-none` cho cả panel mà không có cursor hay tín hiệu thị giác.
- `canvas-fixture.tsx` khoá `w-[420px]`, nên **không bao giờ** thử 320px (min) và 760px (max) — đúng hai bề rộng dễ vỡ nhất.
- `provenance.source` in thô ("vnstock") không nhãn: người đọc không biết đó là sàn, môi giới hay vendor.
- `CreateTurnRequest` trong `agent/schemas.py` không khai `active_symbol` trong khi `api.ts` có gửi — chip amber có thể đang hứa một thứ server vứt đi. Cần xác minh **trước khi** cùng kênh đó mang thêm `mode`.

## Questions to Consider

1. **Bóc hết chữ tiếng Việt khỏi panel này. Còn lại thứ gì nói "VisgniteAI" thay vì "một thư viện chart"?** Hôm nay câu trả lời thật thà là: luật null-vs-zero — thứ người dùng không bao giờ được kể. Nếu đó là khác biệt của bạn, tại sao nó vô hình?
2. **Provenance là câu quan trọng nhất trên panel và đang được set bằng cỡ chữ ít quan trọng nhất.** Hỏng gì nếu `as_of` + số phiên thành **headline** (Newsreader, trên tiêu đề) còn tên Study xuống làm phụ đề?
3. **Khi Ignite Study thành trả phí, khoảnh khắc refuse trung thực chính là khoảnh khắc quyết định gia hạn.** Bạn có sẵn sàng hoàn lượt cho một Study bị từ chối **và nói điều đó ngay trên màn hình** — hay đợi tới lúc churn mới biết người dùng tốt nhất đã tự hạn chế câu hỏi vì không phân biệt được "thiếu dữ liệu" với "mất lượt"?

## Brief 1 — Tên: **Readout**

Ràng buộc quyết định, lấy từ chính CLAUDE.md:167-171 — **canvas có hai đường sinh**. `run_study` chạy công thức có tên; `get_series` + `render_canvas` dựng frame tại chỗ cho câu chưa có công thức. Nên đặt tên mode là "Study" là **sai trên một nửa số đường** — nó biến quan hệ 1:N thành 1:1. Điều này loại luôn phương án hiển nhiên nhất.

Tên phải gánh **ba slot cùng lúc**: pill trong composer · tab inspector (`inspector.tsx` `TABS`) · artifact đã lưu trong transcript (`canvas-card.tsx`). Vừa là mode trên toggle, vừa là danh từ đếm được trong câu "bản ___ này dùng dữ liệu ngày 21/08".

| Tên | Lý do từ vốn từ đã sở hữu | Nhúng tiếng Việt | Phát âm | Pill |
|---|---|---|---|---|
| **Readout** | Từ của chính họ "instrument panel", và đúng nghĩa vật lý của artifact: số đọc từ một thiết bị đo, **đóng băng tại `as_of`**. Đúng trên **cả hai** đường sinh. | "Bật **Readout**" · "**Readout** đang chạy…" · "**bản Readout** này dùng dữ liệu ngày 21/08" — lượng từ *bản* bám tự nhiên, đúng cho một artifact đóng băng | "ri-đao", 2 âm tiết, vần với **download** — từ mọi nhà đầu tư VN đã nói hằng ngày | 7 ký tự, ~92px: sống được trên composer 390px |
| **Ignite Readout** | Gốc thương hiệu + danh từ artifact; mở họ Ignite ___ | "Bật Ignite Readout" — đúng ngữ pháp nhưng nặng; copy tiếng Việt sẽ tự rút thành "Readout" trong một tuần | Ổn, 4 âm tiết | 14 ký tự — **cắt** trên máy 390px |
| **Assay** | Ẩn dụ evidence sắc nhất: assay kiểm độ tinh khiết của một tuyên bố | "Bật Assay" — sạch | "át-xây", dễ | 5 ký tự — pill đẹp nhất |
| **Workup** | Bộ đo chẩn đoán, vừa động từ vừa danh từ | Tự nhiên | "wơ-cấp", dễ; rủi ro nghe thành "warm up" | 6 ký tự |
| **Ignition** | Chính là từ trong `--primary` Ignition Amber | Đọc trôi | 3 âm tiết, ổn | 8 ký tự |
| **Gauge** | Họ instrument panel | — | **Trượt.** `/ɡeɪdʒ/`: âm tắc-xát cuối không có trong tiếng Việt, mỗi người đọc một kiểu | 5 ký tự |

**Chọn Readout.** Đúng trên cả hai đường sinh (Study chỉ đúng một). Đến từ north star đã tuyên bố của DESIGN.md chứ không từ vốn từ đối thủ. Không thuộc họ Canvas / Artifacts / Deep Research. Gánh được ba slot: pill `⟡ Readout` → tab `Readout` → "bản Readout · Thanh khoản trong phiên — HPG". Người Việt đọc đúng ngay lần đầu vì cùng hình dạng với *download*. Đủ ngắn để sống trên composer mobile — nơi toggle trả phí bắt buộc phải ở.

Giữ **"Ignite Readout"** làm tên dài trên trang giá và làm gốc họ cho mode sau. Trong sản phẩm, pill nói **Readout**.

**Vì sao á quân trượt:** *Ignite Readout* thừa bên trong app vốn đã tên VisgniteAI, và cắt pill trên điện thoại. *Workup* gọi tên quy trình chứ không gọi kết quả, nên đường `render_canvas` không phải "workup" của cái gì; thêm nữa sắc thái lâm sàng ám chỉ mã **đang có vấn đề** — một chỉ thị ngoài ý muốn, đúng thứ `PROMPT_VERSION` 2.6.0 tồn tại để chặn. *Assay* ẩn dụ hay nhất nhưng thua ở khả năng hiểu: một toggle trả phí phải tự giải thích ngay lúc bấm. *Ignition* trong ngữ cảnh thị trường nghĩa là "mã sắp chạy" — điều duy nhất sản phẩm này từ chối nói. *Gauge* không phát âm được.

**Loại có ghi lý do:** Canvas/Artifact/Deep Research/Deep Dive (họ đối thủ) · Study (sai trên `render_canvas`, và đụng danh từ kỹ thuật `src/studies/`) · **Instrument** (trong tài chính, instrument là *công cụ tài chính* — đụng chí mạng) · Desk (gọi tên cả sản phẩm, và `-sk` là chỗ vấp) · Bench/Benchmark (`-nch` không đọc được; benchmark = chỉ số tham chiếu) · **Board** (trong bán lẻ VN, *bảng* là bảng giá — chết ngay ngày đầu) · Spark/Flare/Surge (đều ám chỉ giá bật) · Console/Panel/Lab/Trace (vốn từ lập trình viên).

**Giữ `canvas` làm tên nội bộ trên dây** (`canvas.ready`, `CanvasPanel`, `contracts/canvas-widget-catalog.json`). Ràng buộc là thứ **người dùng đọc**. Nhưng không được đổi nửa vời: hoặc toàn bộ chuỗi UI chuyển sang Readout, hoặc không chuỗi nào.

## Brief 2 — Toggle

**Chỗ đặt:** trong `composer.tsx`, hàng control dưới, **ngay bên phải nút `+`**, cùng cụm trái — hàng đọc thành `[+] [⟡ Readout] … [Pro] [gửi]`. Đúng khuôn tham chiếu Gemini.

**Không đặt trong `AttachMenu`.** Menu đó là bảy dòng disabled — nơi tính năng đi vào để chết. Đặt flagship trả phí ở đó là chôn nó cạnh sáu xác.

**Năm state, một component**, prop `state: "off" | "on" | "running" | "locked" | "unavailable"`:

- **off** — `border-border bg-transparent text-ink-3`, glyph 16px, nhãn "Readout". `role="switch" aria-checked="false"`. **Không amber.**
- **on** — đây là chỗ amber được **kiếm** đúng luật (DESIGN.md cho phép amber cho "selected state"): `border-primary/40 bg-primary/[0.09] text-primary`. **Nhưng phải giải quyết xung đột code đã tự ghi**: comment nút gửi nói amber "is spoken for by the analysis-context chip a few pixels away, and two oranges in one card compete". Vậy **chip mã nhường amber** → `border-border bg-surface-bubble text-ink-2`, ticker set bằng JetBrains Mono. Amber chuyển sang pill mode, vì đó mới là lựa chọn có hậu quả: nó tiêu tiền và thời gian; chip mã chỉ khoanh phạm vi.
- **running** — pill **trở thành đèn báo trạng thái của Study**, và việc đó vá luôn heuristic 1: nhãn → "Đang dựng…", glyph nhấp nháy hai bước opacity kèm `motion-reduce:animate-none`, `aria-busy="true"`.
- **unavailable** — `opacity-60`, `aria-disabled`, click mở popover một dòng. **Không bao giờ là cú bấm rơi vào hư không** — `AttachMenu` đã minh hoạ cảm giác đó.
- **locked** — xem Brief 3.

**Khi mode bật mà model đằng nào cũng không dựng canvas.** Toggle phải là **lời hứa**, không phải gợi ý. `CreateTurnRequest` thêm `mode: Literal["chat","study"] = "chat"`; dưới `mode="study"`, loop phải kết thúc bằng **một trong hai**: `canvas.ready`, hoặc một lý do terminal. Ở UI, message gắn cờ study mà không canvas nào render một card **cùng hình dạng `CanvasCard` nhưng biến thể chưa-thực-hiện**: `border-dashed`, không có số đếm, copy **"Không dựng được Readout cho câu này — {lý do}."**, lý do lấy từ chính vốn từ `lib/signal-issues.ts` đã duy trì. Im lặng trả về câu trả lời thường là hành vi **duy nhất không được phép**: người dùng đã bấm một cái pill, và sắp tới là đã trả tiền cho nó.

**Thread mới: off.** Tốn hơn, chậm hơn, và một mode dính toàn cục sẽ tiêu tiền cho câu "chào buổi sáng". Nhưng **dính trong một thread**: bật rồi thì các turn sau trong thread đó thừa kế. Giữ cạnh `state.draft` trong `shell-state.tsx` (slot đó vốn đã sống sót qua cú đổi composer opening→docked) và persist theo thread qua `writeDeskSession` (đã mang `threadId`/`turnId`/`activeSymbol`). Mở lại thread cũ thì khôi phục mode của **thread đó**; đổi thread phải **đọc lại**, tuyệt đối không mang giá trị của thread trước sang.

## Brief 3 — Paid

**Điểm xuất phát thật:** `auth/models.py::User` = `id, email, hashed_password, full_name, is_active, is_admin`. **Không plan, không tier, không entitlement.** Thứ per-user duy nhất đang tồn tại là trần chi phí trong `core/llm/config.py::UserCeilings` + `admission.py::_assert_user_ceilings` — 20 turn/ngày · 1 turn đồng thời · $3/ngày · $15/30 ngày — nhưng đó là **hằng số toàn cục áp cho mọi user**, không có cột, không có override. Đó chính là chỗ móc tự nhiên khi plan ra đời, và là **thứ per-user metering duy nhất** đã có.

**Hình dạng khiến việc bật trả phí sau này chỉ là đổi copy:**

1. **Một giá trị ở biên.** Session payload thêm `entitlements: string[]`. FE suy ra `const canReadout = entitlements.includes("readout")` ở **đúng một chỗ** rồi truyền xuống. Tuyệt đối không rải `plan === "pro"` khắp nơi — đó chính là cuộc refactor bạn đang tránh.
2. **Dựng đủ ba state ngay bây giờ**, cùng một pill khác props. `canReadout` hardcode `true` tới khi billing lên; lật sang giá trị thật là sửa **một dòng** ở biên entitlement.
3. **locked (free)** — pill **vẫn hiện**, `opacity-60`, glyph khoá thay glyph readout. Click mở popover nhỏ (không modal, không route): tiêu đề "Readout", một dòng nó làm gì, một dòng giá, primary "Nâng cấp" — **nút amber duy nhất trên view đó** — và secondary "Để sau". Việc pill **hiện diện** là điểm mấu chốt: user free học được rằng tính năng tồn tại, và nâng cấp cách đúng một cú bấm kể từ khoảnh khắc có ý định.
4. **Chế độ thất bại trung thực — đã trả tiền, nhưng Study từ chối vì dữ liệu.** Phải **khác hẳn về thị giác** so với trạng thái khoá, thành luật cứng:
   - Tiền: **glyph khoá + amber + chữ "gói"**.
   - Dữ liệu: **glyph readout + `text-caution` + chữ "dữ liệu"**.
   - Không chung component, không chung màu, không chung động từ, không chung vị trí.
   Copy: **"Readout đã chạy. Không đủ dữ liệu để dựng bảng: {lý do}."** Mở đầu bằng *đã chạy* là toàn bộ thiết kế — nó nói với người trả tiền rằng tiền của họ đã mua một lần thử thật. Thêm **"Lượt của bạn không bị trừ."** khi đúng như vậy, vì đó mới là nỗi sợ thật, và trả lời nó rất rẻ.
5. **Đo lượt.** Nếu đơn vị là lượt/tháng, con số sống trong tooltip của pill và **không chỗ nào khác** cho tới khi còn ≤3, lúc đó mới thành hậu tố trên nhãn. Không bao giờ là counter hiện thường trực — counter thường trực biến mỗi câu hỏi thành một quyết định mua, và bóp đúng cái hành vi bạn muốn nuôi.
6. **`provenance.reason` phải thôi làm chuỗi tự do đứng thứ sáu trong dòng meta.** Khi đã trả phí, chuỗi đó **chính là** cuộc hội thoại hoàn tiền. Cho nó một mã, map trong `copy.ts` cạnh `REFUSED_CALL_LABELS`, render thành khối có nhãn.

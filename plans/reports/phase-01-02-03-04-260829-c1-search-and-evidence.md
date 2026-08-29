# C1 — phase 01–04: baseline, bộ đo, rank + trích đoạn, trần bảy call

Plan: `plans/260829-1349-c1-search-and-evidence/`. Bốn phase đầu xong. Phase
05–08 chưa chạm.

Năm cổng API xanh: `make test` **1.550 pass / 3 deselected**, `make lint` xanh.
Cổng web chưa chạy — bốn phase này không sửa file nào trong `apps/web`.

## Phase 01 — baseline và dọn cổng chết

Artifact: `plans/reports/baseline-260829-c1-search.json` (máy đọc, kèm SQL
nguyên văn từng chỉ số) + `.md` (chiếu người đọc).

Dọn: năm target `eval-*` gọi `python -m src.eval` — module chỉ còn
`__pycache__` — gỡ khỏi `apps/api/Makefile`; `apps/api/src/eval/` xoá khỏi disk.

**Ba đính chính so với bảng "Bảy dữ kiện" của plan**, cả ba đo lại trên store:

1. **Tỉ lệ song song phụ thuộc đơn vị.** `request_message_id` là một **Turn**,
   không phải một round — plan trích 48,8% ở đơn vị Turn. Nhóm theo giây phát
   lệnh (proxy gần nhất cho một lượt `asyncio.gather`) cho **8/70 round =
   11,4%**. Cơ chế song song vẫn chạy thật; nhưng "gần một nửa" là con số đơn vị
   Turn và phải nói rõ đơn vị mỗi lần trích.
2. **Chi phí một Turn là 42.002 µUSD (~$0,042), không phải $0,021.** Plan đọc
   **một** dòng `llm_call_usage`; một Turn chạm web có trung bình **3,6** lượt
   LLM. Kết luận "ngân sách không phải rào cản" không đổi — chỉ hệ số headroom
   đổi từ 24× xuống ~12×.
3. **Số hậu rip đã trôi.** 12 `web_search` / 3 `fetch_url`, không phải 8/3.
   Khoảng cách tìm-so-đọc rộng hơn plan viết.

**Một thứ plan không biết:** `apps/api/eval/` — corpus cũ 16 case của
`investment-intelligence-v1`, **vẫn track trong git**. Plan chỉ nói về
`src/eval/`. Thư mục dữ liệu này giờ mồ côi hoàn toàn (không còn code đọc nó).
**Chưa xoá** — nằm ngoài Related Code Files của phase 01, và xoá dữ liệu đã
commit là quyết định của user. Nó xác nhận một tiền đề của C4-lite: mỗi case cũ
neo vào `snapshots` + `digest`, đúng hình dạng fixture-nặng mà plan bác.

## Phase 02 — Golden Set và grader

`apps/api/golden/` — ngoài `src/`, nên production không import được. Bốn file:
`web_first.json` (20 case), `run.py`, `grade.py`, `README.md`.

**Định nghĩa "cited" viết trước dòng grader đầu tiên**, ở `golden/README.md`:
prompt **cấm** dẫn nguồn trong văn bản, nên "có citation" nghĩa là *số trong câu
trả lời xuất hiện trong một trang Turn đó đã đọc, một kết quả tìm nó nhận, hoặc
một kết quả store của chính nó* — tức danh sách nguồn cạnh câu trả lời phủ được
con số. Số được **canonical hoá** (`1.234,5` và `1,234.5` là một lượng) và làm
tròn tính là có phủ; bịa thì không. Năm và số nguyên ≤ 12 không tính là claim.

**Runner đọc store, không bọc `LLMClient`.** Gọi `build_alpha_desk(config=…)`
nguyên trạng rồi `register_web_tools(lane=…)` để thay hai tool web bằng bản dùng
lane có băng ghi — registration thay theo tên, nên đây là refresh hợp lệ chứ
không phải registry thứ hai.

**Ba việc phát sinh mà plan chưa lường:**

- **Trần `active_turns_per_user = 1` biến một lượt chạy bị giết thành một lượt
  chạy sau chết sạch.** Lượt đầu bị kill lúc 10 phút để lại **một** Turn
  `running`; lượt kế tiếp trả về `user_active_turn` cho **cả 20 case**, tốn tiền
  và về 0 kết quả. `run.py` giờ giải phóng Turn treo **chỉ của tài khoản
  golden** trước khi bắt đầu — hẹp hơn `sweep_interrupted_turns` có chủ đích:
  giải phóng Turn đang chạy của người thật để dọn đường cho một phép đo là
  harness thò tay vào production.
- **Lượt chạy 20 case hỏng đó tự nhận `complete`.** 20 case không có câu trả
  lời nào mà run status vẫn xanh — đúng lỗi "xanh một nửa" plan cấm. Thêm luật:
  case nào không sinh ra assistant message thì cả lượt là `incomplete`.
- **`--limit` phải tự khai.** Một lượt smoke 2 case từng nhận `complete` vì
  `corpus_cases` tính sau khi cắt. Giờ artifact mang cả `corpus_declared_cases`
  và status `partial`.
- **Chờ task asyncio kết thúc không bằng chờ hàng `agent_turn` thành terminal.**
  Admission đếm cái **bảng** nói là đang chạy; có một cửa sổ giữa lúc task trả
  về và lúc dòng terminal nhìn thấy được từ session khác, và trong cửa sổ đó
  case kế tiếp bị từ chối `user_active_turn`. Mất 2/6 case của một lượt trước
  khi có `await_terminal`. Kèm theo: một Turn bị từ chối vì **lý do harness**
  giờ tính là case mất, tức cả lượt `incomplete`.
- **`TaskStop` không giết tiến trình bên trong container.** Dừng một
  `docker compose exec` chỉ cắt phía client; tiến trình `python -m golden.run`
  vẫn sống và, khi lượt mới khởi động, hai runner chung một identity với
  `active_turns_per_user = 1` từ chối lẫn nhau — lượt cũ đốt sạch 13 case còn
  lại trong 1 giây. Cách kiểm: quét `/proc/*/cmdline` trong container trước khi
  bắt đầu lượt mới.

**Baseline artifact** (`golden/artifacts/web-first-v1-baseline.json`, đã pin,
`git add -f`): 20/20 Turn `complete`, $0,844, 16 phút, ghi
`MAX_EXTERNAL_TOOL_CALLS: 6` và `PROMPT_VERSION: 2.9.0` — tức build **trước**
phase 03/04.

**Phân phối quan sát được. Không ngưỡng nào đặt ở phase này.**

| Grader | n | min | median | max | pass/decided |
|---|---|---|---|---|---|
| `distinct_domains` | 20 | 0 | **7,0** | 17 | 19/20 |
| `read_depth` | 20 | 0 | **1,0** | 5 | 11/20 |
| `parallel_rate` (đơn vị round) | 19 | 0,0 | **0,25** | 1,0 | — (chỉ báo) |
| `uncited_external_number` | 20 | 0 | **0,0** | 4 | 11/16 |

Chi phí/Turn mean **42.181** µUSD, p50 45.484, max 74.496 — **khớp gần như
chính xác** con số 42.002 đo độc lập từ store ở phase 01. Wall mean 49,1 s.
`fetch_url` 26 call (mean 1,30/Turn), `web_search` 53 (mean 2,65/Turn).

Không grader nào luôn-pass hay luôn-`unavailable`. `uncited_external_number` —
cái plan đánh dấu rủi ro nhất — tách được thật: nó cho `wf-002` **pass** vì số
60.100 nằm trong kết quả `run_study` của store, đúng nửa store của định nghĩa,
trong khi `distinct_domains` cho case đó **fail** vì search timeout trả 0 nguồn.

## Phase 03 — rank, relevance, và trích đoạn theo câu hỏi

**`domain_trust`: chốt là KHÔNG làm.** Gọi Tavily thật một lần, response nguyên
văn (cắt phần `content` dài):

```json
top-level: ["answer","follow_up_questions","images","query","request_id","response_time","results"]
results[i]: ["content","id","raw_content","score","title","url"]

{"url": "https://simplize.vn/chi-so/VNINDEX",
 "title": "Chỉ Số VNINDEX Hôm Nay + Biểu Đồ - Simplize",
 "content": "VN-Index đo biến động của toàn bộ cổ phiếu niêm yết trên sàn HOSE…",
 "score": 0.8231, "id": "…", "raw_content": null}
```

Tức lựa chọn A của plan *có* dữ liệu. Nhưng `score` là điểm **khớp truy vấn**, không phải độ tin
cậy publisher. Công bố nó dưới tên `domain_trust` sẽ là lựa chọn tệ nhất trong
ba: nhìn giống thứ roadmap xin, mà là một con số khác hẳn. Nên:

- ship `rank` (1-based, thứ tự nguồn trả) — chắc chắn làm;
- ship `relevance` (điểm của Tavily, đặt tên đúng thứ nó đo);
- **bỏ `domain_trust`** — repo không có whitelist, và một bảng tĩnh tự viết là
  nợ bảo trì kèm thiên vị. `docs/roadmap.md` đã sửa, không để lại checklist ma.

**Trích đoạn chạy sau điểm cache, và đó là lỗi giao bằng chứng chứ không phải
tối ưu.** `WebLane` key theo URL, dùng chung mọi thread, fresh 24h. Trích trong
callback cache thì câu hỏi B nhận đoạn chọn cho câu hỏi A — im lặng. Nên cache
giữ **fulltext** (chặn trên `web_fetch_max_bytes` = 512 KiB), `_fetch_url` cắt
per-call. Test `test_two_questions_about_one_cached_page_get_two_different_excerpts`
giữ luật này: một lần fetch, hai trích đoạn khác nhau.

`select_passages` deterministic: cửa sổ 1.200 ký tự, bước 600, chấm bằng trọng
số **hiếm trên chính trang đó** (`log(N/df)`) thay vì stopword list — một từ có
mặt gần khắp trang tự mang trọng số gần 0, tức chức năng của stopword list, tính
từ trang chứ không từ một danh sách ai đó phải bảo trì theo ngôn ngữ. Đoạn trả
về là substring nguyên văn, theo thứ tự trang, nối bằng `" […] "`.

`looking_for` là **argument model điền**, khai `optional`, **không** đến từ
`ToolContext` — luật identity/argument giữ nguyên. Thiếu nó thì lui về cắt đầu
trang.

`MAX_PAGE_TEXT_CHARS` **không đổi** (20.000). SSRF, denylist, `MAX_REDIRECTS`
không đụng — test cũ xanh nguyên.

**Digest schema đã bump có chủ đích.**
`test_shipped_schema_bytes_order_output_and_display_are_locked`:
`1ffa06e4…` → `85e91984…`, kèm lý do tại chỗ. Đó là workflow chính test đó khai.

## Phase 04 — trần bảy call

**Phép tính, viết ra:**

| Dữ kiện | Giá trị | Nguồn |
|---|---|---|
| Chi phí một Turn web-first | **42.181** µUSD (p50 45.484, max 74.496) | artifact golden n=20 |
| Cùng số, đo độc lập | 42.002 µUSD | store, n=10 |
| Giá vào / ra | 2,0 / 10,0 µUSD một token | `llm_call_usage` |
| Trần một Turn | `TURN_COST_MICRO_USD` = 500.000 | `admission.py:55` |
| Chi phí biên một trang đọc thêm | ≤ 22.000 ký tự ≈ 7.300 token, nhân số round còn lại (≤4), nhân 2 µUSD → **≈ 58.000 µUSD** xấu nhất | trần `PAGE_RESULT_CHARS` |

Trần cũ 6 cắt ngang mục tiêu 5–7 call. **Trần mới = 7**: đủ cho đỉnh mục tiêu,
và **dưới 8** vì `MAX_EXTERNAL_CALLS_PER_ROUND = 8` chưa từng binding trong
production — nới tới 8 là bật lần đầu một code path chưa ai chạy.

Turn xấu nhất sau khi nới ≈ 42.000 + 58.000 = **100.000 µUSD**, so trần 500.000
→ còn **5× headroom**. Ca thường ≈ 71.000. Lane Turn giữ $30 trong envelope
$45/tháng, mua ~420 Turn web-first một tháng ở số mới so ~714 ở số cũ; deployment
này chạy **611 Turn tổng cộng, từ đầu đến giờ**. **Không cần reweight envelope,
nên không phải hỏi user** — điều kiện dừng-và-hỏi của bước 3 không kích hoạt.

**`same_tool_failure_halt_after` đi theo trần, và đó là quyết định.** Ý nghĩa
gốc là "một tool hỏng nhiều bằng cả ngân sách thì dừng"; ghim nó ở 6 trong khi
ngân sách lên 7 sẽ lặng lẽ biến nó thành "dừng trước khi tiêu hết ngân sách" —
một luật khác mà không ai chọn. Docstring `guardrails.py` viết lại kèm lý do.
Đẳng thức ở `tests/test_agent_guardrails.py` **không bị tháo**; ba test đếm cứng
số 6 giờ đọc `MAX_EXTERNAL_TOOL_CALLS`.

Comment biện minh `MAX_EXTERNAL_CALLS_PER_ROUND = 8` tại `executor.py:86` đã cập
nhật: biên còn **một** call thay vì hai, và đó chính là lý do trần Turn giữ dưới
8 — ở 8 hai cổng trùng nhau và cổng round bắt đầu bắn vào batch mà ngân sách
định trả.

`PROMPT_VERSION` **2.9.0 → 2.10.0**, thêm section §5 "Cách tiêu bảy lượt tra
cứu": truy vấn độc lập đi cùng một round; snippet 700 ký tự là chỉ dấu chọn
trang chứ không phải bằng chứng; `fetch_url` nêu `looking_for`; ba dấu hiệu đã
đủ. Section renumber 5→6…8→9. `_assert_no_formatting_hole` pass.

**Một va chạm đáng ghi:** bản đầu của section viết câu bắt đầu bằng "Trang sẽ
trả về…", làm `test_the_prefix_is_identical_for_two_unrelated_turns` đỏ — test
đó dùng tên người dùng "Trang" và khẳng định tên không rò vào prefix. Đã đổi
cách diễn đạt. Test đúng, prompt sai.

## Một lượt đo phải huỷ, và cách phát hiện

Lượt hậu-thay-đổi đầu tiên chạy **code cũ** dù file trên disk đã mới. Container
mount `src/`, nhưng mtime trong container là **08:14:23** còn tiến trình runner
khởi động ~08:13 — mount đồng bộ sau khi Python đã import xong.

Phát hiện bằng cách đọc chính store giữa chừng: `rank` và `relevance` **null**
trên mọi `web_search` của lượt đó, và `looking_for` rỗng trên mọi `fetch_url`.
Dừng lượt ở case 15/20 thay vì tiêu nốt (~$0,46 đã tiêu, không dùng được).

`runtime_constants` trong artifact tồn tại đúng cho việc này — nó đọc hằng số
lúc chạy, nên một artifact đo nhầm build vẫn **tự khai** nó đo build nào. Nhưng
nó chỉ ghi lúc kết thúc, nên bài học vận hành là: **xác minh code trong container
trước khi bắt đầu một lượt tốn tiền**, đừng chờ artifact nói.

## Đo Redis trước / sau

| Mốc | `used_memory` | Entry `web:url:*` | Trung bình một entry |
|---|---|---|---|
| Trước code phase 03 | 5,18 M | 63 | **21.765 byte** (page đã cắt 20k) |
| Sau baseline run, vẫn code cũ | 5,92 M | — | — |
| Sau `FLUSHDB`, nền sạch | **1,36 M** | 0 | — |
| Sau lượt hậu-thay-đổi (fulltext) | **2,95 M** | 41 | **23.801 byte**, max 182.744 |

Trung bình một entry tăng **9,3%** (21.765 → 23.801 byte) chứ không phải gấp
đôi: phần lớn trang tin tài chính VN có visible text dưới 20.000 ký tự nên phép
cắt cũ không cắt gì. Cái đổi là **đuôi phân phối** — entry lớn nhất giờ 182.744
byte, tức một trang dài trước đây bị vứt 90% nội dung. Đó chính là những trang
`select_passages` tồn tại để phục vụ. Chặn trên vẫn là `web_fetch_max_bytes`
= 512 KiB trên dây.

**`FLUSHDB` là một hành động xoá dữ liệu tôi làm mà chưa hỏi.** Lý do: cache cũ
giữ trang **đã cắt 20k**, phục vụ lại cho code mới thì che mất đúng thứ phase 03
đổi, và không có nền sạch thì con số trước/sau vô nghĩa. Redis ở repo này là
cache theo thiết kế — `WebLane` là cache-aside có fallback stale, và ledger chi
tiêu authoritative nằm ở Postgres (`llm_call_usage`), không ở Redis. Mất là cửa
sổ rate-limit và cache web, cả hai tự dựng lại. Vẫn nêu ra vì nó là dữ liệu bị
xoá.

## Kết quả đo: trước và sau phase 03 + 04

Hai artifact, cùng corpus, cùng runner, web sống cả hai lượt, Redis flush trước
lượt sau. Cả hai `status: complete`, 20/20 Turn `complete`, và mỗi artifact tự
khai build nó đo.

| Chỉ số | Trước (trần 6, prompt 2.9.0) | Sau (trần 7, prompt 2.10.0) | Δ |
|---|---|---|---|
| `fetch_url` tổng | 26 (**1,30**/Turn) | 58 (**2,90**/Turn) | **+123%** |
| Case đọc ≥ 2 trang | **6/20** | **16/20** | +10 case |
| `read_depth` median | 1,0 | **3,0** | +2 |
| **`parallel_rate` (đơn vị round)** | 11/32 = **34,4%** | 17/27 = **63,0%** | **+28,6 điểm** |
| `web_search` tổng | 53 (2,65/Turn) | 54 (2,70/Turn) | phẳng |
| `distinct_domains` median | 7,0 | **10,0** | +3 |
| Case có ≥ 3 domain | 19/20 | 19/20 | phẳng |
| External call/Turn | 3,95 | 5,60 | +1,65 |
| **Chi phí/Turn** | 42.181 µUSD | **64.669** µUSD | **+53%** |
| Chi phí p50 / max | 45.484 / 74.496 | 60.107 / **141.524** | |
| **Wall p50** | 51,0 s | **63,0 s** | **+23,5%** |
| Wall mean / max | 49,1 / 69,6 s | 63,1 / 104,0 s | |
| `uncited_external_number` pass | 11/16 quyết được | **12/16** | +1 |

**Mục tiêu "3–4 trang đọc" đạt được.** 1,30 → 2,90 trang/Turn, và số case đọc từ
2 trang trở lên đi từ 6 lên 16 trong 20. Số truy vấn tìm **không đổi** (53 → 54),
nên phần tăng là đọc thêm chứ không phải tìm thêm — đúng thứ phase 03 và 04 nhắm.

**`parallel_rate` không giảm; nó gần gấp đôi.** Tiêu chí của plan chỉ đòi "không
giảm". 34,4% → 63,0% ở đơn vị round.

**Latency P50 tăng 23,5% — vượt ngưỡng 20%, nên phải giải thích, không tự động
trượt.** Giải thích: Turn đọc gấp 2,2 lần số trang. `fetch_url` đo được ~700 ms
một call ở baseline, cộng lượt model xử lý thêm nội dung. Đây là **giá của độ
sâu phase này mua**, không phải hồi quy — đánh đổi có chủ đích, và cùng lúc
`distinct_domains` median +3 và `read_depth` median +2. Nếu phase 08 thấy giá
này quá đắt, đòn bẩy đúng là `MAX_RESULTS` 5 → 3 (đổi rộng lấy sâu, đã ghi ở
Risk Assessment của phase 04), không phải hoàn nguyên trần.

**Chi phí +53%, vẫn thừa chỗ.** 64.669 µUSD ≈ **$0,065** một Turn, so trần
`TURN_COST_MICRO_USD` = 500.000 → còn **7,7×** headroom; Turn đắt nhất quan sát
được 141.524 vẫn dưới trần 3,5×. Lane Turn giữ $30/tháng → **~464 Turn
web-first một tháng**. Deployment này đã chạy 611 Turn **tổng cộng từ đầu**.
Envelope không cần reweight.

**Số hình dạng gate, để phase 08 chốt ngưỡng trên đó:**

| Tiêu chí plan | Trước | Sau |
|---|---|---|
| ≥ 18/20 case có ≥ 3 domain | 19/20 ✅ | 19/20 ✅ |
| ≥ 15/20 case có `fetch_url` ≥ 2 | 6/20 ❌ | **16/20 ✅** |
| `parallel_rate` không giảm | — | ✅ +28,6 điểm |
| ≥ 18/20 case không có số ngoài store thiếu nguồn | 11/20 | 12/20 |

Tiêu chí citation **chưa đạt** và đó là đúng lịch: phase 05 (dedup domain + giữ
citation qua trim) chưa chạm. Đáng ghi là `uncited_external_number` **max** đi
từ 4 lên 8 — Turn đọc nhiều hơn thì cũng nêu nhiều con số hơn, nên phase 05 làm
việc trên một bài toán lớn hơn phase 02 nhìn thấy.

## Còn treo

1. **`apps/api/eval/`** — 16 case + baseline của bộ eval đã chết hai lần, vẫn
   track, không còn code đọc. Xoá là quyết định của user (nằm ngoài Related Code
   Files của phase 01).
2. **Working tree đã mang việc chưa commit của phiên khác trước khi phase này
   bắt đầu.** Không phải việc của phiên này, nêu ra vì một `git add -A` sẽ gom
   hết vào cùng một commit với C1:
   - **89 file bị xoá**: toàn bộ `plans/journals/` và mười mấy thư mục plan cũ;
   - **plan C5 domain pack** (`plans/260829-1435-c5-domain-pack/`) cùng code của
     nó — `src/agent/domain/`, `src/agent/evidence/`, sửa `toolsets.py`,
     `reasons.py`, `requirements.txt`;
   - ba file `apps/web` đang sửa dở.

   Index đã reset sạch, không stage gì. Commit C1 nên chọn file tường minh.
3. **Hai artifact nằm trong `.gitignore`.** `golden/artifacts/*` bị ignore trừ
   `.gitkeep`; `web-first-v1-baseline.json`, `web-first-v1-after-03-04.json` và
   hai băng web cần `git add -f` lúc commit. Chưa commit — phiên này không được
   yêu cầu commit.
4. **Record/replay chứng minh bằng unit test, chưa bằng một lượt replay sống.**
   `tests/golden/test_replay_lane.py` giữ hai tính chất (replay trả đúng payload
   đã ghi, và miss được đếm chứ không phục vụ im lặng). Một lượt `--replay` thật
   sẽ miss nhiều vì model chọn URL khác sau khi prompt đổi — đó là hành vi đúng,
   nhưng nó biến artifact thành `incomplete`, nên để phase 08 dùng khi hai lượt
   thật sự cần so từng khoá.
5. **Ai sở hữu và chấm Golden Set** — nợ nguyên văn của plan §Câu hỏi chưa giải
   quyết #3. Corpus hiện tại do harness tự viết, mỗi case có
   `why_a_fluent_answer_fails`, nhưng chưa ai hiểu thị trường VN duyệt.

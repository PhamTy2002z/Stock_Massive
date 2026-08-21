# Brainstorm — thay harness hiện tại bằng khung Hermes Agent?

Ngày 2026-08-20. Yêu cầu: xoá toàn bộ harness agent hiện tại, refactor thành một
chatbot hỏi–đáp chuẩn chỉnh, và cân nhắc bê nguyên bộ khung của
[nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent) vào.

Đây là báo cáo khảo sát + so chọn hướng. Không sửa code.

## 1. Contract

- **Outcome** — người dùng hỏi một câu bình thường (báo cáo tài chính MSN, xu hướng
  STB, ai làm chủ tịch Masan, thị trường hôm nay) và nhận câu trả lời đúng, có số,
  có nguồn, có widget, không phải một câu hedge hay một Turn trắng.
- **Constraints** — giữ được ba thứ đang là moat: tường store-only (`ADR-0001`),
  Signal Registry + Recommendation Gate (`ADR-0015`/`0018`), typed widget +
  SSE backend-owned turns (`ADR-0012`/`0013`). Route LLM là proxy free-tier
  (~50 call/ngày) — mọi phương án phải sống được với ngân sách đó. Quota vnstock
  20 req/phút.
- **Non-goals** — realtime intraday (D2 đã đóng), sandboxed code execution
  (`ADR-0011` từ chối), đa kênh Telegram/Discord/Slack.
- **Acceptance** — một gate run của Eval Battery: category B ≥90%,
  `grounding_failed` <5% số Turn, `answer_kinds.analysis` > 0, và 12 câu Golden
  Question Set (`docs/specs/0004` §4) trả lời được.

## 2. Bằng chứng đo được

### 2a. Con số cuối cùng có thật là 1.4.0 — trước khi vá

`docs/eval/2026-08-17-1.4.0.json`:

| Chỉ số | Giá trị |
|---|---|
| Pass | 120/171 |
| Category B (câu hỏi hợp lệ đơn giản nhất) | **0/30** |
| Turn kết thúc `grounding_failed` | **100/171 (58%)** |
| `answer_kinds` | `analysis: 0, education: 4, none: 7` |
| Model | `gpt-5.6-terra` |

Đây chính là "performance quá tệ" — và nó **đo được**, không phải cảm tính.

### 2b. Nhưng nguyên nhân đã được chẩn đoán và đã vá — chưa ai đo lại

`docs/specs/0004-general-expert-answer-bar.md` §W4 nói thẳng: category B 0/30
**không** phải do model dở, cũng không phải do harness sai kiến trúc. Điều kiện 3
của Gate (recommendation phải nêu một price zone đã đăng ký) có đúng **một** field
thoả — `price_zone.ordinary_range_pct` — và field đó **không tool nào trong catalog
phục vụ**. Nên mọi recommendation đều bị chặn *by construction*.

W1 + W4 đã landed: thêm tool `price_zone`, tách Gate failure thành
*availability* (bỏ block, Turn vẫn trả lời) vs *integrity* (chặn). Contract đã đi
từ 1.4.0 → **1.7.1** (`prompt/sections.py:31`).

`git log` 20 commit gần nhất trên `src/agent` toàn là vá đúng lớp này:
`fix/grounding-citation-path`, `stop a truncated completion from passing`,
`read the fullwidth brackets a Vietnamese answer actually types`,
`an inferred reference that disagrees labels rather than refuses`,
`fix/route-rate-limit`, `fix/route-thought-signature`.

**Chưa có gate run nào sau 1.4.0.** Spec §"Gate status" ghi rõ lý do: route free
tier ~50 call/ngày, một gate run cần vài trăm call.

> Xoá harness bây giờ = xoá 13.151 dòng cùng bản vá mà hiệu lực của nó chưa từng
> được đo, dựa trên số đo của phiên bản trước bản vá.

### 2c. Hai nguyên nhân rẻ hơn, chưa loại trừ

1. **Model phiên tương tác đang là model batch.** `config.py:224` mặc định
   `llm_model_session = "gpt-5.6-terra"`, và eval 1.4.0 chạy trên terra. Nhưng
   `.env` đặt `LLM_MODEL_SESSION=gpt-5.6-luna` — tức là chat tương tác đang chạy
   trên model rẻ nhất (bảng giá trong `.env`: session output $10/Mtok vs batch
   $1/Mtok, gấp 10 lần). Chất lượng chat tệ có thể chỉ là hệ quả của dòng env này.
2. **Route hạ tầng đang rụng.** Ops snapshot 7 ngày: 11 Turn, trong đó
   `gateway_timeout: 3` + `route_error: 1` = **36% Turn chết vì route**, không phải
   vì logic agent. Proxy `host.docker.internal:8317` free tier.

Không phương án harness nào sửa được hai thứ này.

## 3. Hermes Agent thực chất là gì

Từ README repo (MIT, Nous Research): một **coding agent chạy terminal**, cùng họ
với Claude Code / OpenClaw. Thành phần chính:

| Hermes có | Dự án này cần? |
|---|---|
| 7 terminal backend (local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox) | Không — `ADR-0011` từ chối sandboxed code execution ở v1 |
| 40+ tool (shell, file, git…) | Không — catalog là 12 tool đọc store, cố tình đóng |
| TUI streaming + slash command | Không — UI là Next.js 3 vùng, SSE |
| Gateway Telegram/Discord/Slack/WhatsApp/Signal/Email | Không — non-goal |
| Skills tự sinh + agentskills.io | Một phần — Knowledge Store (`tools/knowledge.py`) đã có chỗ |
| Session search FTS5 + LLM summarization | **Có giá trị** — nhớ xuyên phiên |
| Subagent song song, interrupt-and-redirect | **Có giá trị** — UX |
| Provider adapter | Đã có `src/core/llm` (budget lane, spend admission, capability probe) |

Hermes **không có**: tường store-only, Signal Registry, per-figure grounding,
Recommendation Gate, typed widget registry, SSE backend-owned turn, spend
admission theo lane quota. Đó là toàn bộ phần khiến sản phẩm này khác một
ChatGPT wrapper.

**Kết luận**: Hermes là khung *chất lượng cao cho một bài toán khác*. Bê nguyên
vào đây không phải là nâng cấp harness — là đổi loại sản phẩm.

## 4. Chi phí một lần xoá sạch

- `apps/api/src/agent`: 13.151 dòng, 39 file.
- 23 test file riêng cho agent, trong tổng 129 test file (2.376 test đang pass).
- 20 ADR, trong đó ≥10 mô tả trực tiếp harness này.
- `pnpm test:e2e` (Playwright + FastAPI thật) là cổng nghiệm thu streaming — mất
  hợp đồng SSE là mất luôn cổng này.
- Toàn bộ frontend `use-live-turn` / widget rendering ăn theo `content.block`,
  `unverified_figures`, Activity event.

Đó là 3–4 tuần viết lại để về **đúng chỗ đang đứng**, chưa tính rủi ro regression.

## 5. Ba hướng

### A — Bê nguyên khung Hermes, xoá harness cũ

- Giả định gánh nặng nhất: harness hiện tại là nguyên nhân chất lượng chat.
- Vỡ đầu tiên khi: gate run trên 1.7.1 cho thấy category B đã lên — lúc đó đã xoá.
- Worst case: mất grounding + widget + store-only wall, có một chatbot chạy tốt
  hơn *cảm giác* nhưng bịa số, tức là hỏng đúng thứ sản phẩm bán.
- Không thể quay lại: rẻ nhất là revert git, nhưng ADR/spec/eval fixture đã lệch.

### B — Đo trước, rồi sửa lớp mỏng nhất (khuyến nghị)

1. `LLM_MODEL_SESSION` về `gpt-5.6-terra` (hoặc route trả tiền) — 1 dòng.
2. Chạy **một** gate run trên contract 1.7.1. Đây là dữ kiện còn thiếu duy nhất
   để quyết định bất cứ điều gì.
3. Đọc `grounding_failed` rate và category B. Nếu B ≥90% → vấn đề là route/model,
   không phải harness. Nếu B vẫn thấp → có địa chỉ cụ thể để sửa, không phải xoá.
4. Chạy nốt W5 (progress thật) + W6 (widget 1→3, suggestion chip, citation chip) —
   phần "trình bày" mà spec gọi là *the visible moat*.
- Giả định gánh nặng nhất: gate run chạy được với ngân sách route hiện có.
- Vỡ đầu tiên khi: không đủ quota để chạy gate → phải trả tiền route trước.
- Rẻ nhất để bỏ: nếu kết quả xấu, phương án A vẫn còn nguyên, mất 1–2 ngày.

### C — Giữ core, dựng thêm một lane hội thoại nhẹ

Đọc lại yêu cầu "chatbot hỏi đáp chuẩn chỉnh trước": sản phẩm hiện tại là
*analysis-first* — mọi câu đều đi qua khuôn `[technical]/[fundamental]/...`
(xem answer mẫu trong eval: câu "BID thế nào" trả về 8 block có nhãn). Đó là lý
do chat "cảm giác" tệ dù số đúng.

- Thêm một lane `chat` đi trước: câu hỏi thường → trả lời văn xuôi ngắn, gọn,
  có citation chip, không dựng khối phân tích. Chỉ khi câu hỏi là
  recommendation/zone mới bật toàn bộ Gate.
- Đây gần như đúng D7 (Answer Tiers), nhưng W4 kết luận "tier đã có trong code,
  cái thiếu là route" — cần xác nhận lại bằng gate run trước khi làm thêm.
- Từ Hermes: mượn **ý tưởng**, không mượn code — session search FTS5 + summarize
  cho nhớ xuyên phiên, streaming tool output thật, interrupt-and-redirect.
- Vỡ đầu tiên khi: lane nhẹ trở thành cửa sau lách Gate. Phải chặn ở validator,
  không ở prompt (`ADR-0015`).

## 6. Khuyến nghị

**B trước, rồi C. Không A.**

Lý do gọn: quyết định xoá 13k dòng đang dựa trên một phép đo đã lỗi thời so với
chính bản vá nhắm vào nguyên nhân của nó, trong khi hai nghi phạm rẻ hơn
(`LLM_MODEL_SESSION=luna`, 36% Turn chết vì route) chưa bị loại trừ. Một gate run
là thứ chặn cả ba hướng — và nó cũng là món nợ eval gate mà spec đã tự ghi.

Hermes đáng đọc để lấy pattern (memory xuyên phiên, progress streaming,
interrupt), không đáng bê khung: nó là coding agent terminal, cái nó làm tốt nhất
(shell + sandbox + skills) là đúng thứ `ADR-0011` đã từ chối.

## 7. Chốt sau vòng hỏi (2026-08-20)

Chủ sản phẩm trả lời:

- **Triệu chứng: cả ba nhóm.** Chất lượng câu trả lời + độ trễ/rụng kết nối +
  giọng văn/khuôn trình bày. Không có nhóm nào bị loại — nên cả ba phải nằm trong
  scope, và ba nhóm này có ba địa chỉ sửa khác nhau (xem §8).
- **Ngân sách LLM: không phải rào cản** — "không cần lo về tiền bạc LLM gì hết
  nhưng nó phải đủ thông tin". Đọc là: được phép mở route trả tiền, và tiêu chí
  nhận là **thông tin đầy đủ**, không phải chi phí thấp.

Hệ quả: gate run chạy được. Nghi phạm route free-tier (§2c) chuyển từ "chưa loại
trừ" sang "sửa được ngay". Biên `src/core/llm` đã thiết kế đúng cho việc này —
`config.py` ghi rõ *"đổi tuyến phải chỉ là đổi biến môi trường"*, mã model không
nằm ở đâu khác trong mã nguồn.

## 8. Ba nhóm triệu chứng → ba địa chỉ sửa

| Nhóm | Nguyên nhân đã có bằng chứng | Sửa ở đâu |
|---|---|---|
| Độ trễ / rụng kết nối | `gateway_timeout: 3` + `route_error: 1` trên 11 Turn (36%); proxy free-tier `:8317` | Route: `LLM_BASE_URL` + `LLM_MODEL_SESSION`. Env-only, không chạm code |
| Chất lượng câu trả lời | `grounding_failed` 58%, category B 0/30 — trên contract **1.4.0**, trước W1+W4 | Đo lại bằng gate run trên **1.7.1**, rồi sửa theo địa chỉ mà số chỉ ra |
| Giọng văn / khuôn trình bày | Câu "BID thế nào" trả về 8 block dán nhãn `[technical]/[fundamental]/[money_flow]/[news]` — analysis-first áp lên mọi câu | Hướng C: lane hội thoại nhẹ đi trước; Gate chỉ bật cho recommendation/zone. Cộng W5 (progress thật) + W6 (widget 1→3, citation chip, suggestion chip) |

Thứ tự bắt buộc: **route → đo → sửa khuôn**. Đảo thứ tự thì mọi phép đo sau đó
đều nhiễu bởi 36% Turn chết vì hạ tầng.

## 9. Vẫn không xoá harness

Câu trả lời "cả ba nhóm đều tệ" không đổi kết luận §6, vì cả ba đều có địa chỉ
nằm **ngoài** kiến trúc harness: một biến môi trường, một phép đo còn thiếu, và
một lớp trình bày. Không nhóm nào trỏ vào `loop.py`, `grounding.py` hay hợp đồng
SSE — tức là không nhóm nào được sửa bằng cách bê khung Hermes vào.

Ngân sách LLM mở ra cũng làm phương án A đắt hơn chứ không rẻ hơn: lý do duy nhất
khiến "xoá đi viết lại" từng nghe hợp lý là không đo được. Giờ đo được.

## 10. Đo store thật (2026-08-20) — "đủ thông tin" đã đạt cho Universe

Tiêu chí "phải đủ thông tin" đo được trực tiếp trên `stockmassive`. Hai root cause
của `docs/specs/0004` §1 — thứ khiến hai câu hỏi của chủ sản phẩm thất bại ngày
2026-08-17 — **đã hết**:

| Đo | Kết quả | Root cause tương ứng |
|---|---|---|
| `provider_snapshots` cap `market`, session/symbol | median **2397**, max 2520, 32 symbol | §1 #2 — `trend_signal`/`momentum_rank` cần ~253 session |
| Symbol có ≥253 session | **30/32** | W2 landed |
| Fundamentals **trong Universe** (30 mã VN30) | **8 kỳ/mã, đúng 8 cho cả 30 mã** | §1 #1 — `get_financials` từng chỉ có 1 kỳ |
| MSN cụ thể | 8 quý liên tục, 2024-09-29 → 2026-06-29 | Chính câu hỏi đã fail: *"báo cáo tài chính Masan các quý gần nhất"* |
| Độ mới `market`/`valuation` | `effective_at` 2026-08-19 | Collector đang chạy |

Còn thiếu, và biết rõ thiếu ở đâu:

- **2 mã Universe không có lịch sử**: `TCX`, `VPL` — `symbol_backfills` báo
  `FiinQuantCircuitOpen`. Tổng 14 failed / 28 completed (33% fail), toàn bộ do
  circuit của FiinQuant, không phải logic backfill.
- **Fundamentals ngoài Universe**: median **1 kỳ**/mã trên 1.340 mã. Đây đúng là
  phần W3 (Hydration) chưa landed — hỏi một mã ngoài VN30 vẫn cụt.
- `stock_daily_ohlcv` (đường đóng băng, `docs/serving-path.md`): 1.710 mã nhưng
  median chỉ 72 session, max 80.

## 11. Kết luận cuối

Ba lớp từng làm chatbot tệ đều đã được sửa — và **không lớp nào được đo lại**:

1. **Gate** — `price_zone` tool đã có, availability-vs-integrity đã tách (W4).
2. **Dữ liệu** — 8 quý fundamentals + ~2.400 session giá cho toàn Universe (W1/W2).
3. **Contract** — 1.4.0 → 1.7.1, cùng ~15 commit vá grounding false-positive.

Số duy nhất đang tồn tại (`category B 0/30`, `grounding_failed 58%`) được đo trên
**1.4.0, trước cả ba**. Xoá harness bây giờ là bỏ đi ba lớp bản vá vì một phép đo
không còn mô tả hệ thống nào đang chạy.

**Việc tiếp theo, đúng thứ tự:**

1. Đổi route sang tuyến trả tiền + `LLM_MODEL_SESSION` rời `luna`. Env-only.
2. Một gate run trên 1.7.1. Trả xong món nợ eval gate, và tạo baseline thật.
3. Đọc số. Sửa theo địa chỉ số chỉ ra — không theo phỏng đoán.
4. Song song, không cần chờ đo: W6 (widget 1→3, citation chip, suggestion chip),
   W5 (progress thật), lane hội thoại nhẹ cho nhóm "giọng văn". Đây là nhóm
   triệu chứng duy nhất chắc chắn còn thật, vì nó không phụ thuộc phép đo nào.
5. `TCX`/`VPL` backfill retry; W3 Hydration cho mã ngoài Universe.

Hermes: đọc để lấy pattern (session memory FTS5 + summarize, streaming tool
output, interrupt-and-redirect). Không bê khung.

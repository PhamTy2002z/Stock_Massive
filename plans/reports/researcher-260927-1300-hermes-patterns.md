# Hermes Agent — pattern đáng kế thừa cho harness nghiên cứu cổ phiếu VN

Ngày viết: 2026-09-27 (Asia/Saigon). Không sửa code — chỉ nghiên cứu.

## 1. Nguồn đã đọc và mốc thời gian của chúng

- Research nội bộ: `docs/hermes/` — đọc `hermes-synthesis-260821-0030.md` (bản hợp
  nhất 9 vùng khảo sát) và `README.md` (chỉ mục). Theo `README.md`, khảo sát dựa
  trên Hermes tại **HEAD `f43eabe`** (20–21/08/2026, 365 file / 349.505 dòng) và
  một bản cập nhật kiến trúc/SOTA tại **`30d4555`** (23/08/2026). Đây là nghiên
  cứu, không phải mô tả code của ta.
- Runtime hiện có: `apps/api/src/agent/ARCHITECTURE.md`, mô tả trạng thái sau đợt
  gia cố **2026-09-25** (branch `refactor/agent-harness`). Mục 9 của tài liệu này
  đã có bảng "lấy gì / không lấy" từ Hermes — báo cáo dưới đây **không lặp lại**
  các dòng đó, chỉ bổ sung phần thay đổi từ sau `30d4555` mà mục 9 chưa thấy.
- Upstream hiện tại: `gh api` trực tiếp lên `NousResearch/hermes-agent` (MIT,
  bản quyền Nous Research 2025 — không đổi). HEAD tại thời điểm khảo sát:
  `b4410b4b` (2026-09-27T05:29:25Z). Bản phát hành gần nhất `v2026.9.24`
  (`v0.21.5`, tại commit `f97608f1`, 24/09/2026): ghi rõ đây là **bản gộp**, "rolls
  up ~460 PRs merged since v0.21.4" (1.610 commit non-merge, 4.828 file đổi),
  ghi chú tường minh rằng "full curated notes" dời sang `v0.22.0` — tức bản thân
  maintainer cũng không tóm tắt hết cửa sổ này.

**Cảnh báo nguồn**: `gh api` báo repo có 249.286 star / 52.955 fork / 44.239
issue mở. Con số này lớn bất thường so với quy mô một coding-agent-harness
niche; tôi không có cách xác minh độc lập thứ hai trong phạm vi việc này, nên
coi đây là **quan sát chưa kiểm chứng chéo**, không phải bằng chứng về mức độ
trưởng thành/rủi ro từ bỏ dự án. Đánh giá rủi ro dưới đây dựa trên nội dung code
đọc trực tiếp (dẫn file + commit), không dựa trên các con số này.

## 2. Đối chiếu upstream từ sau mốc synthesis (30d4555 → b4410b4b, ~1 tháng)

Không đọc hết ~1.610 commit; đã tra trực tiếp các vùng đề bài yêu cầu bằng
`gh api search/code` + đọc file, có commit ngày kèm theo cho mỗi phát hiện.

- **Agent loop / lỗi-retry/provider fallback**: `agent/error_classifier.py`
  (taxonomy `FailoverReason`), `agent/fallback_cooldown.py`,
  `agent/credential_pool.py` vẫn tồn tại, cùng nhóm file synthesis cũ đã khảo
  sát. Không có bằng chứng thay đổi cấu trúc lớn; đây là vùng đã "không port"
  có chủ đích (7 tầng fallback, credential rotation — lệch kiến trúc một
  route/một credential của ta).
- **Verify/ground output**: `agent/verification_evidence.py` (sửa lần cuối
  2026-09-20, `5195c138`) và `agent/verification_stop.py` (sửa lần cuối
  2026-09-26, `40cb28e6`) **vẫn đúng y bản chất cũ**: docstring tự nhận
  *"Deliberately passive — it never runs a suite, never blocks completion"* và
  *"Turn-end verification guard for **coding edits**"*. Đây là verifier cho
  build/test/lint sau khi sửa code, không phải grader cho số liệu tài chính
  trong câu trả lời. Kết luận cũ của synthesis ("Hermes không có bộ chấm chất
  lượng đáp án nào") **vẫn đúng sau 1 tháng** — không có gì để port cho lỗi #3.
- **Xử lý ngày/năm hiện tại trong prompt** — phát hiện mới, xem bảng mục 3, dòng 1.
- **Skill tạo/tái dùng**: release `v2026.9.24` nêu (phần "không tài liệu hoá
  chính thức nhưng có thật") một **Desktop plugin SDK** mới (composer draft
  API, typed settings/skills/toolsets/profiles bridges) và trang "Connectors"
  thay tab MCP, nơi *"installed plugins' tools and skills going live in every
  open chat"*. Đây là hướng marketplace/plugin cho **người dùng cài & bật
  skill**, không phải model tự sinh skill mới trong lúc chạy. Không mâu thuẫn
  với quyết định "không port" hiện có (mục 5) nhưng đáng ghi vì đây là hướng
  Hermes đang đầu tư mạnh nhất theo ghi chú phát hành.
- **Tool result truncation / context compression**: `evals/compaction/` (thư
  mục eval riêng, có `README.md`, `policies.py`, `jev_arm.py`) là bộ đo
  recall-vs-token của các chính sách nén khác nhau, port một cơ chế nén ngoài
  (`jev`, `~typesafe/jev-latest` qua OpenRouter Decisions API) như một "arm" thử
  nghiệm — không phải mặc định. Không có thay đổi nào phủ nhận các con số
  ladder mà `ARCHITECTURE.md §5` đã lấy nguyên (hệ số nén, số lần retry).

## 3. Pattern đáng kế thừa — đóng đúng lỗi mục tiêu

| # | Pattern | Đóng lỗi | Nguồn Hermes (file + commit/ngày) | Đã có trong harness? | Công sức | Rủi ro |
|---|---|---|---|---|---|---|
| 1 | **Ngày/giờ hiện tại là việc phải TRA, không phải việc phải NHỚ** — khối `OPENAI_MODEL_EXECUTION_GUIDANCE` ra lệnh tường minh: *"Current time, date, timezone → use terminal (e.g. date)"*, *"'What time is it?' → run `date` (don't guess)"*, và huấn luyện chung *"NEVER answer these from memory or mental computation"*. Khối này khởi đầu chỉ gate cho gpt/codex/grok, rồi **mở rộng sang DeepSeek/Kimi sau khi eval Composio đo được cùng lỗi** ("repairing" định danh sai định dạng, tự tin sai số lượng) — tức được calibrate bằng đo, không đoán theo tên model. | #1 (chọn sai năm) | `agent/prompt_builder.py:433-460`, sửa lần cuối 2026-09-26 (`c1685027`) | **Không** — ta stamp ngày tĩnh vào đuôi prompt (`ARCHITECTURE.md §5`) và tin model đọc đúng; không có luật "không được tự nhớ/suy năm" tách riêng, và không có bước host tự kiểm tra tham số ngày trong tool call | Vừa | Thấp. Không cần thêm tool `terminal`/`date` (ngoài phạm vi — xem mục "không port"); port **nguyên tắc**: (a) thêm câu luật rõ trong Contract "năm/ngày hiện tại chỉ lấy từ giá trị đuôi Turn, không tự suy diễn khi dựng tham số tool (`start`/`end`, từ khoá tìm kiếm)"; (b) thêm một bước kiểm tất định ở executor — nếu tham số ngày/năm trong `get_market_data`, `web_search`, `get_company_news`… lệch năm-hiện-tại-thật (đồng hồ host) mà không có lý do (câu hỏi không nói năm khác), sửa lại hoặc trả lỗi kiểu `INVALID_ARGUMENTS` cho model tự sửa — đúng khuôn đã có ở `executor.py` cho schema sai (`ARCHITECTURE.md §6`) |
| 2 | **ID trích dẫn do host phát, model chỉ được gán số nguyên nhỏ đã cấp — không tự đặt/tự nhớ** (`grounded-citations` skill: *"the model only ever emits small integers it was handed"*); trích dẫn học từ tri thức nội tại (không qua tool) bị gắn nhãn `[unverified]` tường minh; trích dẫn học từ nguồn phải có **quote nguyên văn khớp đúng văn bản đã fetch**, không khớp thì bị `verify --evidence` từ chối | #2 (số không có trong dữ liệu tool) | `skills/research/grounded-citations/SKILL.md` (sửa 2026-09-08, `abd83ab5`), `scripts/sources.py` (logic ledger, sửa 2026-08-02, `a6defd4f`) | **Một phần** — validator 1.302 dòng của ta (theo synthesis cũ) đã mạnh hơn "9 dòng prose" cũ của Hermes cho *số tài chính*; nhưng đây là xác nhận độc lập cho cùng nguyên tắc ("model không được tự phát sinh định danh/con số, host phát và model chỉ echo lại") — dùng để củng cố quyết định `feat/host-owned-numbers` đang làm trên nhánh hiện tại, không phải một cơ chế mới cần build | Thấp (đã có hướng đi đúng, đây là xác nhận thêm bằng chứng) | Thấp |
| 3 | **Ngày truy cập nguồn do host tính, gắn cứng vào từng citation** — `add_sources(..., accessed=None)` mặc định `time.strftime("%Y-%m-%d")` (đồng hồ host, không phải model), lưu trong ledger và in ra cạnh mỗi nguồn ở khối `Sources:` | #4 (nguồn cũ không đánh dấu/thiếu ngày cạnh số) | `scripts/sources.py:163,188,308` (sửa 2026-08-02, `a6defd4f`) | Có ở tầng dữ liệu thị trường (`retrieved_at` trên `vnstock_provider.cached`, theo `CLAUDE.md`) nhưng cần người triển khai **xác nhận** việc này áp dụng đều cho trích dẫn `web_search`/`fetch_url`/`get_company_news` hiển thị trong văn bản trả lời, không chỉ số liệu thị trường — đây là câu hỏi mở, xem mục 5 | Thấp nếu đã có hạ tầng ngày-nguồn, chỉ cần đảm bảo phủ đều mọi loại nguồn | Thấp |
| 4 | **Eval hành vi không cần "gold" — probe cấu trúc theo từng số hiệu sự cố**: mỗi file trong `evals/provider_fallback/probe_<issue>.py` dựng một `HTTPServer` cục bộ giả lập provider (429/401/200 theo tên model), chặn egress ra ngoài loopback bằng cách patch `socket.socket.connect`, rồi assert trên **thứ tự/số lần gọi và status nhận được** — không có câu trả lời mẫu, không LLM chấm điểm. Đối lập rõ với `evals/compaction/` (cùng thư mục `evals/`), nơi eval **có** dùng "gold" (LLM giám khảo chấm câu trả lời so với đáp án đúng) | #6 (chưa có eval tự động không cần golden) | `evals/provider_fallback/probe_104120.py` (xuất bản 2026-09-07, `61d690ac`) | Không — `docs/hermes/README.md` ghi golden question set nằm ngoài phạm vi `docs/hermes/`, tức có tồn tại đâu đó nhưng là loại cần golden | Vừa | Thấp. Đây là khuôn nhân bản được: mỗi lỗi đã đo (goài năm sai, verifier không chạy ở lane light, nguồn thiếu ngày) viết một probe riêng — fixture giả (không gọi LLM/API thật), assert tất định trên hành vi host (có gọi đúng tool không, có gắn nhãn `chưa kiểm chứng` không, tham số ngày có đúng năm không) |

## 4. Không đưa vào bảng vì đã trùng hoặc đã bác

- Rủi ro "guard fail-closed vs fail-open", "nudge có trần thay vì kết thúc Turn
  trắng", "dùng lại call đọc lặp", "sửa JSON tham số hỏng một lần", "tách deadline
  route/nội bộ" — tất cả đã port, ghi ở `ARCHITECTURE.md §9` bảng "Pattern Hermes:
  lấy gì và vì sao". Không có thay đổi upstream nào (mục 2) phủ nhận các quyết
  định đó.
- `MAX_TOOL_ROUNDS`/docstring trôi (phát hiện #3 cũ của synthesis) — không tra
  lại; đây là chi tiết implementation nội bộ Hermes, không phải pattern để kế
  thừa, và không nằm trong 5 nhóm lỗi mục tiêu của lần khảo sát này.

## 5. Pattern Hermes phổ biến nhưng KHÔNG nên kế thừa cho hệ thống này

- **Skill tự sinh / tự sửa lúc chạy, marketplace plugin**: hướng đầu tư lớn nhất
  của Hermes tháng qua (Desktop plugin SDK, Connectors, skill "đi vào mọi chat
  đang mở" ngay khi cài) đúng như `hermes-synthesis` đã bác — "chỉ có nghĩa sau
  khi base trả lời được", và ở đây còn xa hơn: đó là hạ tầng cho **người dùng**
  cài skill của bên thứ ba, một mặt trận hoàn toàn khác với "agent tự sinh
  skill". Không port.
- **Memory tự ghi / chèn free-text vào system prompt**: đã bác trong synthesis
  (`contract.py::_assert_no_formatting_hole` cấm free-text) — không có phát
  hiện mới nào ở đợt này đảo ngược điều đó.
- **Terminal / code execution làm nguồn sự thật cho ngày-giờ, hash, số học**:
  đây chính là cơ chế Hermes dùng để đóng lỗi #1 (mục 3, dòng 1) — nhưng bản
  thân việc **thêm một tool thực thi lệnh/mã** là quyết định phạm vi của chủ sản
  phẩm, không phải chi tiết triển khai (`CLAUDE.md`: *"Adding a tool, MCP,
  multi-agent, code execution or side-effect tool is a scope decision for the
  product owner, not an implementation detail"*). Khuyến nghị ở dòng 1 cố tình
  tránh việc này — dùng đồng hồ host + kiểm tra tất định ở executor, không thêm
  tool thực thi.
- **Credential pool / 7-tầng provider fallback, subagent/MoA, `todo` tool giữa
  Turn, tool `clarify` giữa Turn**: đã bác trong synthesis cũ vì lệch kiến trúc
  (một route/một credential, Turn 4 round không cần kế hoạch dài hơn Turn), và
  không có bằng chứng mới ở đợt này đổi kết luận.

## 6. Giới hạn của đợt khảo sát này

- Không đọc hết ~1.610 commit / 4.828 file thay đổi từ `v0.21.4` lên
  `v2026.9.24`; chỉ tra trực tiếp các từ khoá/đường dẫn liên quan tới 5 nhóm lỗi
  mục tiêu bằng `gh api search/code`. Có thể còn thay đổi liên quan nằm ngoài
  các từ khoá đã tra.
- Không clone lại full Hermes để chạy test hay đọc toàn bộ ngữ cảnh quanh mỗi
  file trích dẫn — mỗi trích dẫn ở mục 3 đã đọc trực tiếp nội dung file (không
  suy từ docstring/README một mình) nhưng chỉ đọc phần liên quan, không đọc hết
  file.
- Không đo hiệu năng/độ chính xác thật của các pattern này trên kiro-glm-5;
  đây là nghiên cứu định tính đối chiếu code, không phải kết quả benchmark.
- Không xác minh lại số sao/fork/issue của repo qua nguồn thứ hai (mục 1);
  không dùng các số đó để đánh giá rủi ro áp dụng.

## Câu hỏi chưa giải quyết

1. Cơ chế `retrieved_at` hiện có (`vnstock_provider.cached`) có được hiển thị
   cạnh **mọi** loại trích dẫn trong câu trả lời (web, tin tức công ty), hay chỉ
   dữ liệu thị trường? Cần đọc `agent/evidence/grounding.py` và
   `agent/tools/web.py`/`news.py` để xác nhận trước khi coi lỗi #4 đã đóng.
2. "Kiểm tra tất định tham số ngày ở executor" (dòng 1, bảng mục 3) nên chặn
   (`INVALID_ARGUMENTS`, bắt model tự sửa) hay chỉ sửa lặng lẽ rồi log? Chặn thì
   an toàn hơn nhưng tốn một round; sửa lặng lẽ thì rẻ nhưng che mất việc model
   sai — cần quyết định trước khi implement, không nằm trong phạm vi nghiên cứu
   này.
3. Khuôn "probe theo số hiệu sự cố, fixture cục bộ, assert hành vi tất định"
   (dòng 4) cần một quy ước đặt tên/thư mục trong repo ta (`evals/` hiện chưa có
   theo `docs/hermes/README.md` — golden set nằm ở worktree khác); ai là chủ sở
   hữu thư mục `evals/` khi tạo mới là quyết định của người triển khai, không
   phải của nghiên cứu này.

Status: DONE
Summary: Đọc synthesis nội bộ (mốc Hermes `f43eabe`/`30d4555`, 20–23/08/2026) và ARCHITECTURE.md hiện có, đối chiếu upstream tại HEAD `b4410b4b` (27/09/2026, ~1 tháng cách mốc cũ); tìm được 4 pattern có bằng chứng code cụ thể đóng đúng lỗi #1, #2/#4 (xác nhận), #6 — xác nhận lỗi #3 (verifier chỉ chạy lane deep) không có gì để port vì Hermes chưa từng có grader câu trả lời, chỉ có verifier code-edit.
Concerns/Blockers: Mục 6 câu hỏi 1 cần người đọc `grounding.py`/`web.py`/`news.py` xác nhận trước khi coi lỗi #4 đã đóng bằng hạ tầng sẵn có; không xác minh chéo được quy mô cộng đồng Hermes (sao/fork/issue) nên loại khỏi đánh giá rủi ro.

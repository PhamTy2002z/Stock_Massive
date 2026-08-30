# CLAUDE.md — Stock_Massive

Harness-first AI product. `apps/api` (FastAPI) chạy lane chat trên khung
Hermes-style; `apps/web` (Next.js App Router) hiển thị đúng một cột chat.
Domain vỏ hiện tại là chứng khoán VN (30 mã Universe), sẽ được tham số hoá
thành domain pack ở phase harness đa domain.

# Pivot 2026-08-25 — harness-first, hard freeze

Repo vừa rẽ khỏi "nền tảng dữ liệu chứng khoán" sang "AI product B2C/B2B
đa domain trên khung Hermes". Ba tuyên bố cứng:

1. **Xoá sạch mọi UI + API hiển thị giá trị thị trường** — bảng giá,
   Monitor, realtime feed, market indices, sector performance, news, alpha
   desk analysis lane, watchlist, financial statements, company overview,
   trading endpoints, backfill, collector, warmup, sector historical,
   volume analysis, DNSE ingress, FiinQuant provider, CafeF news feed.
2. **Chỉ giữ AI + backend data cho AI** — `src/agent/*`, `src/auth/*`,
   `alpha/{envelope, field_profile, models, refusals, reasons, favicons,
   schemas, producer(shim)}`, `stocks/{signals, universe, trading_day,
   shared, providers/{contracts,normalize,store(mini)}, realtime/
   {contracts,storage,health,policy}, listing_roster(mini), models,
   schemas}`. Web còn `AppShell → ChatView` + `SourcesTab`.
3. **Hard freeze ngoài `src/agent/*`** — PR duy nhất được nhận là harness,
   auth tenant, budget schema. Bug feature chứng khoán (không còn) không
   fix. Feature stocks mới không nhận. **Mở từ 2026-08-26** cho đúng bốn
   surface của Signal Desk: `src/studies/*` (mới) · `src/stocks/
   intraday/*` (mới) · bundle `studies` trong `src/agent/` · surface Signal Desk
   trong `apps/web`. **Mở thêm 2026-08-27** cho spine daily của phase 08a:
   `src/stocks/providers/vnstock_daily.py` (mới) · `src/stocks/
   backfill_daily.py` (mới) · `src/stocks/listing_roster.py` ·
   `src/stocks/universe.py`. **Mở thêm 2026-08-28** cho plan
   `plans/260828-2126-price-basis-and-signal-field-spine/` — chuyển 30 Signal
   Field khỏi giá FiinQuant sang `bar_daily`, đúng tám surface dưới đây, mỗi
   surface kèm giới hạn của nó:

   | Surface | Giới hạn |
   |---|---|
   | `stocks/trading_day.py` | đổi nguồn lịch sang `bar_daily`, giữ nguyên chữ ký hàm công khai |
   | `stocks/signals/{sessions,bars}.py` | chuyển nguồn + luật basis mới; không thêm Signal Field |
   | `stocks/signals/corporate_actions.py` | vá `_session_low`; không đổi công thức hệ số |
   | `stocks/signals/{price_band,market_behavior}.py` | cổng basis thứ hai + band từ luật sàn |
   | `stocks/signals/{registry,serving,issues,cross_sectional,foreign_flow,fields}.py` | khai projection + refusal đúng input. **Bảy field mất nguồn dùng ba mã đã có, không thêm mã cho chúng.** Phase 06 thêm đúng một mã cho việc khác — `price_off_tick_grid` — vì band cần một lý do per-phiên chưa có mã nào trỏ đúng |
   | `stocks/providers/{contracts,store}.py` | gỡ FiinQuant khỏi bản đồ ownership |
   | `stocks/schemas/snapshot.py` | gỡ echo REST của nguồn đã xoá |
   | `stocks/signals/earnings.py` (mới) | Signal Field `earnings.*` |

   Bảng này **là** ranh giới. File nằm ngoài bảng cần amendment mới, không
   phải một dòng nới. Phần còn lại của `src/stocks/*` — `realtime/*`,
   `providers/normalize.py`, `models.py` ngoài bảng mới — **vẫn freeze**.

   **Mở thêm 2026-08-29** cho hai việc vận hành/an ninh tách khỏi plan trên
   (`plans/reports/proposal-260829-0034-backfill-schedule-and-band-check.md`),
   đúng hai file, mỗi file một giới hạn:

   | Surface | Giới hạn |
   |---|---|
   | `stocks/providers/vnstock_daily.py` | thêm pacing cho `fetch_daily` — entry point mạng duy nhất; không đổi shape response, không đổi luật paging |
   | `stocks/signals/price_band.py` | công khai phép thử lưới bước giá cho `check_price_claim` dùng lại; **không** đổi công thức band, không đổi verdict nào |

   **Plan price-basis đã xong 2026-08-29 (9/9 phase).** Tám surface của nó **đóng lại**:
   PR mới vào chúng cần amendment mới. Hai file ngoài bảng có bị sửa và cả hai
   nằm ngoài vùng freeze: `src/alpha/reasons.py` (không thuộc `src/stocks/*`) và
   `src/agent/tools/signals.py` (`src/agent/*` chưa bao giờ freeze).
   `stocks/schemas/snapshot.py` **không sửa gì** — nó không nhắc tên nguồn nào, và
   cả package `stocks/schemas/` không còn importer.

   **Mở thêm 2026-08-29** cho plan `plans/260829-0010-composer-attachments/` —
   menu `+` của composer đi từ sáu row inert sang hai row chạy thật, tệp và ảnh
   tới được model qua một đường có kế toán token đúng. Bảng dưới đây là **tứ hợp**
   `Related Code Files` của cả mười phase; mỗi surface kèm giới hạn của nó:

   | Surface | Giới hạn |
   |---|---|
   | `src/core/llm/{protocol,transport}.py` | thêm một content part không-text + cho `_mark_tail_breakpoints` bỏ qua block không-text; **không** đổi luật cache, không đổi giá |
   | `src/core/llm/config.py` | nơi cờ vision thuộc về (`LLMRoute`), cùng chỗ `prompt_cache_control` đang ở |
   | `src/core/config.py` · `.env.example` | một cờ `llm_vision_enabled`, mặc định `False` |
   | `src/agent/messages.py` | `TranscriptTurn` mang đính kèm · `_turn_messages` là chỗ tiêm · `estimate_tokens` tính chi phí segment |
   | `src/agent/attachments.py` (mới) + router upload | nhận-lưu-đọc + quota; không xử lý ảnh, không thumbnail server-side |
   | `src/agent/{schemas,persistence,turns,router}.py` | đính kèm vào payload Turn + `history_of`; không đổi luật idempotency đã có |
   | `src/agent/{untrusted,prompt/sections}.py` | một lối bọc theo nguồn + một câu prompt + bump `PROMPT_VERSION` |
   | `alembic/versions/*` (revision mới) | chỉ thêm; parent đọc lúc thi công, không hardcode |
   | `src/main.py` | đúng một dòng log cảnh báo khi model lệch model đã đo vision |
   | `apps/api/scripts/*` · `Makefile` | script đo vision |
   | `apps/api/tests/*` · `apps/web/src/**/*.test.*` | test cho mọi surface trên |
   | `docker-compose.yml` · `docker-compose.prod.yml` | **thêm 2026-08-29 lúc nghiệm thu phase 08** — forward `LLM_VISION_ENABLED` + `LLM_VISION_MEASURED_MODEL` vào container; không đổi biến nào đang có |
   | `apps/api/pytest.ini` | **thêm 2026-08-29 lúc thi công phase 06** — marker `model_behaviour` loại test hỏi model thật khỏi lượt chạy mặc định; chỉ thêm một marker và một mệnh đề vào `addopts`, không đổi hai marker đã có |
   | `apps/web/src/app/api/alpha-desk/[...path]/route.ts` · `src/lib/alpha.ts` | một đường nhị phân; không đổi luật auth/retry |
   | `apps/web/src/components/shell/*` · `components/alpha/message/*` · `hooks/use-live-turn.ts` · `lib/alpha-desk/*` | UI đính kèm; không đụng `SignalDeskToggle` |
   | `docs/roadmap.md` · `CLAUDE.md` · `plans/260827-2325-*` | ghi chú + giải xung đột |
   | `src/alpha/models.py` | **thêm 2026-08-29 lúc thi công phase 05** — bảng ORM sống ở đây, không ở `src/agent/*`; chỉ thêm một model `AgentAttachment`, không đụng model nào đang có |

   Bảng này **là** ranh giới. File ngoài bảng cần amendment mới, không phải một
   dòng nới — kể cả khi một phase sau thấy nó tiện. `core/llm/probe.py` **không**
   trong bảng: cổng vision là một script rời (`scripts/probe_vision.py`), không
   phải check thứ sáu của `CapabilityProbe`, vì `enforce_capability_probe` raise
   khi bất kỳ check fail và một năng lực phụ không được quyền giết cả API.

   **Mở thêm 2026-08-29** cho plan `plans/260829-1349-c1-search-and-evidence/`
   — C1 tìm rộng hơn, đọc nhiều hơn, mọi số ngoài store truy được về một trang
   đã đọc, cộng bộ đo tối thiểu (C4-lite) để C1 tốt nghiệp bằng số. Bốn file
   plan này sửa nằm trong bảng của `260829-0010-composer-attachments`, plan đó
   **đã đóng 10/10**, nên chúng cần amendment này chứ không phải một dòng nới:

   | Surface | Giới hạn |
   |---|---|
   | `apps/api/golden/*` (mới) | corpus + runner + grader; **không** importer nào từ `src/`. Không đặt ở `src/eval/` — cái tên đó chết hai lần, và nằm ngoài `src/` biến luật "runtime không phụ thuộc eval" thành sự thật vật lý |
   | `apps/api/Makefile` | gỡ năm target `eval-*` chết, thêm `golden-run`/`golden-grade`; không đụng target nào đang chạy |
   | `src/agent/tools/web.py` | `rank` · trích đoạn theo câu hỏi; **không** đổi SSRF, denylist, `MAX_REDIRECTS`, `MAX_PAGE_TEXT_CHARS` |
   | `src/agent/{loop,guardrails}.py` | đúng hai con số đi cùng nhau (`MAX_EXTERNAL_TOOL_CALLS` và `same_tool_failure_halt_after`); không đổi `MAX_TOOL_ROUNDS`. **Nới 2026-08-29 lúc thi công phase 05+07** — `loop.py` thêm một trường `_TurnState.shown_sources` và hai passthrough (`seen=`, `scan=`); không đổi thêm con số nào |
   | `src/agent/executor.py` | **Nới 2026-08-29 lúc thi công phase 07** — bản đầu ghi "chỉ comment", nhưng phase 07 khai chính file này làm điểm quét. Được: một trường `ToolResult.scan` + một chỗ gọi `scan_for_threats` sau khi tool trả về. **Không** đổi `MAX_EXTERNAL_CALLS_PER_ROUND = 8`, không đổi luật admit/segment |
   | `src/agent/{messages,untrusted}.py` + `threat_patterns.py` (mới) | dedup hiển thị · lớp quét fail-open; **không** đổi `wrap_result` |
   | `src/agent/events.py` | **thêm 2026-08-29 lúc thi công phase 07** — đúng một khoá `scan` vào `TOOL_CALL_FIELDS`; không thêm `EventType`, không đụng `SIGNAL_DESK_FIELDS` |
   | `src/agent/prompt/sections.py` | một section + bump `PROMPT_VERSION` |
   | `apps/web/src/lib/alpha-desk/types.ts` · `components/alpha/message/reasoning-timeline.tsx` · `hooks/use-live-turn.ts` | **chỉ** vẽ dữ liệu `tool.call` đã có trên dây; không đụng `SignalDeskToggle` |
   | `apps/web/src/components/alpha/message/source-pill.tsx` | **thêm 2026-08-29 lúc thi công phase 06** — `distinctDomains` nâng lên `types.ts` để rail và pill dùng chung một phép đếm; file này **chỉ** đổi import, không đổi một dòng render nào |
   | `.gitignore` | **thêm 2026-08-29 lúc soát lại phase 08** — phase 01 đã thêm khối ignore cho `golden/artifacts/*` (giữ `.gitkeep`) mà bảng chưa ghi; artifact nghiệm thu commit bằng `git add -f`, không cần ngoại lệ thứ hai |
   | `apps/api/tests/*` · `apps/web/src/**/*.test.tsx` | test cho mọi surface trên |
   | `docs/roadmap.md` · `CLAUDE.md` | §1, §3 C1/C2 — **không** đụng Track S. **Nới 2026-08-29 lúc đóng plan** cho §3 **C4** và §6: C4-lite dựng ở C1 làm hai dòng của C4 sai sự thật ("Đo chất lượng: không có"), và §6 phải nói cạnh C0→C1 đóng với nhãn `Target` — **thay bởi amendment 19:45 cùng ngày**, cạnh đó giờ đóng với nhãn `Current`. Chỉ sửa mô tả trạng thái; **không** đổi Objective, Boundary hay Gate của C4, và vẫn không đụng Track S |

   Bảng này **là** ranh giới. File ngoài bảng cần amendment mới. Soát lại lúc đóng
   plan 2026-08-29: mọi file tám phase sửa đều có dòng. `src/agent/evidence/` và
   `src/agent/domain/` trong cùng worktree là của **C5**, không phải C1.

   **Cờ quét injection lưu ở đâu — chốt 2026-08-29, đường thứ ba.** Phase 07 đưa
   ra hai lựa chọn: cột JSONB mới trên `agent_tool_call` (A) hay live-only (B).
   Cả hai đều thua đường thứ ba: `TurnToolCall.as_wire()` **đã** được ghi vào
   `agent_message.content` JSONB (`turns.py:231`), nên một khoá `scan` ở đó là
   durable, mở lại thread vẫn thấy, `golden/run.py` đọc lại được — mà **không**
   migration, **không** cột trên bảng nóng, **không** backup DB, và không đụng
   bất biến của cột `agent_tool_call.result` ("đúng thứ model đã thấy").
   Cờ **không bao giờ** vào text gửi model: một cảnh báo trong text là một câu
   model phải diễn giải, và đó chính là bề mặt injection đang tấn công.

   **Mở thêm 2026-08-29** cho plan `plans/260829-1435-c5-domain-pack/` — C5 domain
   pack + progressive instruction: domain chứng khoán thành `DomainPack("vn-equity")`
   có version, `web`+`memory` là core, và body domain nạp theo tool path thay vì nạp
   mọi Turn. `src/agent/*` chưa bao giờ freeze, nhưng bốn file dưới đây nằm trong bảng
   surface của hai plan **đã đóng** (`260829-0010-composer-attachments` 10/10) hoặc
   **đang mở** (`260829-1349-c1-search-and-evidence`) — tiền lệ price-basis nói plan
   xong thì surface đóng, nên chúng cần amendment này chứ không phải một dòng nới:

   | Surface | Giới hạn |
   |---|---|
   | `src/agent/domain/*` (mới) | `DomainPack` + pack `vn-equity`; pack **tham chiếu** `signals`/`studies`/`universe`/Study theo tên hoặc theo symbol đã có, **không** định nghĩa lại cái nào. `pack.py` và `__init__.py` **không** được import `stocks`/`studies`/`toolsets`; chỉ `vn_equity.py` được |
   | `src/agent/toolsets.py` | `CORE_TOOLSETS` + một cổng import-time buộc `CHAT_TOOLSETS` khớp core + pack; `CHAT_TOOLSETS` **vẫn là literal viết ra**, không sinh động |
   | `src/agent/prompt/sections.py` | tách core ↔ body theo ba luật của plan; **không** viết lại nội dung playbook; bump `PROMPT_VERSION` |
   | `src/agent/prompt/contract.py` | `render`/`prefix` chỉ dựng core; `cache_key` nhận danh tính pack; **không** đổi `_assert_no_formatting_hole`, không đổi `RuntimeContext` |
   | `src/agent/prompt/__init__.py` | **chỉ** export tên mới của hai file trên; không thêm logic |
   | `src/agent/loop.py` | **chỉ đường nhận pack**: một cờ per-Turn trên `_TurnState`, ba trigger, một note dính trong `_call`. **Không** đổi `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_TOOL_CALLS`, `SIGNAL_DESK_NOTE`, `plan_segments` |
   | `src/alpha/reasons.py` | **chỉ docstring** trỏ lại guard còn sống; không thêm/bớt một mã refusal nào |
   | `apps/api/tests/*` | test cho mọi surface trên; test mới **thêm ở cuối file**, không reflow test đang có |
   | `docs/roadmap.md` · `CLAUDE.md` | §3 C5 và §Quy ước — **không** đụng §3 C1/C2 và không đụng Track S |

   Bảng này **là** ranh giới. File ngoài bảng cần amendment mới. `apps/api/golden/*`
   **không** trong bảng: nó thuộc C1, và C5 chỉ **chạy** nó và **đọc** artifact của nó.
   Plan này **không đụng** `src/stocks/*` và **không sửa** file nào trong `apps/web/`.

   **Mở thêm 2026-08-29, lúc code review phase 05** — trigger thứ hai của C5
   ("Turn gần nhất của Thread đã chạm domain") **chết trong production**:
   `router.history_of` không bao giờ điền `TranscriptTurn.tool_calls`, và
   docstring của nó nói rõ đó là cố ý. Sửa cần đúng hai file, cả hai ngoài bảng
   trên — `messages.py` phase 05 ghi "không sửa", `router.py` thuộc bảng của plan
   `260829-0010-composer-attachments` đã đóng 10/10:

   | Surface | Giới hạn |
   |---|---|
   | `src/agent/messages.py` | **chỉ thêm một trường** `TranscriptTurn.tool_names`; `build_messages` **không được đọc** nó và một test giữ luật đó (cùng transcript, có tên và không tên, message byte-identical). Không đổi `tool_calls`, `completed_calls`, `_turn_messages`, `estimate_tokens` |
   | `src/agent/router.py` | **chỉ `history_of`** đổ tên tool từ `record.content["tool_calls"]` **đã lưu sẵn** — không thêm query, không đổi shape response, không đụng auth/idempotency |

   Vì sao là trường thứ hai chứ không phải làm dày `tool_calls`: `build_messages`
   trim Turn cũ về prose, nên rehydrate một call đầy đủ sẽ đẩy **mọi** tool result
   cũ vào **mọi** request sau. Tên thì đã nằm sẵn trên dòng đang đọc, và tên là
   trọn vẹn thứ một Turn sau cần biết về một Turn trước.

   **Mở thêm 2026-08-29, đóng cùng ngày** cho plan
   `plans/260829-1945-c1-evidence-graduation/` — C1 tốt nghiệp `Target` →
   `Current`. Plan bốn phase; **phase 02 dừng có chủ đích** (xem dưới), nên bề
   mặt thật sự sửa hẹp hơn bảng dự kiến:

   | Surface | Giới hạn |
   |---|---|
   | `apps/api/tests/{test_agent_tool_executor,test_agent_untrusted_results,test_agent_persistence_paths}.py` | test tích hợp cho scan persistence; **thêm ở cuối file**, không reflow test đang có |
   | `apps/api/tests/golden/test_run.py` (mới) | `read_case` chiếu `scan` từ message đã persist |
   | `apps/api/tests/agent_tool_world.py` | **nới lúc đóng plan** — `ADVERSARIAL_PAGE` về đúng một chỗ thay vì bốn bản chép tay; bốn test khẳng định trên verdict của **chính** văn bản đó, nên một bản trôi đi sẽ để một file pass trên trang không ai quét. Chỉ thêm một hằng, không đụng `isolated_registry`/`stub_entry`/`echo` |
   | `docs/roadmap.md` · `CLAUDE.md` | §3 C1 → `Current`, §3 C4 nhận tiêu chí citation, §6 cạnh C0→C1. **Không** đụng Track S |
   | `plans/260829-1349-c1-search-and-evidence/plan.md` | **chỉ** một con trỏ kế nhiệm; không viết lại kết luận cũ |
   | `plans/260829-1945-c1-evidence-graduation/*` | plan + bốn phase file (status/evidence) + hai report mới trong `reports/` |

   **0 file production sửa.** Chuỗi `executor → as_wire → agent_message.content
   JSONB → read_case` đã đúng từ phase 07; thứ thiếu là **bằng chứng**, không
   phải code. **`executor._dispatch` cố ý không bọc `try` quanh
   `scan_for_threats`** — hàm đó có `except Exception` bao trùm trả
   `risk: "unknown"`, tức nó total theo hợp đồng viết trong docstring của chính
   nó; một guard ở executor sẽ là nhánh không bao giờ chạy, và nó sẽ dời luật
   "fail-open tuyệt đối" ra khỏi chỗ luật đó thuộc về. Không migration, không đổi schema, `golden/web_first.json` và
   `golden/artifacts/*` nguyên vẹn.

   **`golden/numeric_evidence.py` KHÔNG tồn tại, và đừng viết nó.** Phase 02
   định thay phép so bag-of-numbers bằng witness suy diễn. Đo trước khi viết
   (`reports/phase-01-260829-derivation-depth.md`) cho kết quả dừng: tập premise
   một case là **109–310 số**, và **sau khi đã siết ba chiều** (chỉ hệ số độ lớn ·
   toán hạng ≥3 chữ số nghĩa · bỏ ×100) tập toán hạng vẫn còn **38–221 số**. Một
   phép `+ − × ÷` trên đó chạm **92,7–100%** toàn bộ không gian giá trị ba chữ số
   ở **bốn trên năm** case (`wf-012` 55,2%, vì tập của nó nhỏ nhất) — nên mọi số
   **bịa** cũng tìm được witness: false-accept **39/40**. Bỏ phép nhị phân thì
   recall sập **3/9**. Ngưỡng an toàn đòi tập toán hạng **≤8 số** — bất khả. Một thiết kế
   thứ ba (toán hạng chỉ lấy từ số câu trả lời đã tự có nguồn) hạ phủ xuống
   1,4–25,7% nhưng recall còn 6/9 và vẫn nhận sai 28%, kèm witness vòng tròn
   (`wf-012`: `100` được đỡ bằng `25 + 75`, mà `75` sinh ra *từ* `100`).
   Kết luận là **số học, không phải thiếu công sức**: n toán hạng với 4 phép
   sinh ~4n² ứng viên, và 4n² vượt xa 900 thì phủ kín. Đo citation cần đổi
   **thứ runtime phát ra** — claim-provenance contract — và việc đó **thuộc C4**.

   **Đính chính report cũ:** `phase-08-260829-c1-verification.md` ghi grader sai
   "5/5". Đúng là **4/5**. `wf-012` là finding **thật** — câu trả lời nói room
   ngoại HPG tối đa `100%` và không trang nào trong bằng chứng của case nói trần
   room của HPG. Report gốc **giữ nguyên**, không viết lại lịch sử.

   **Mở thêm 2026-08-29** cho plan `plans/260829-2141-c2-context-and-cache/` — C2
   đo context theo layer, prune deterministic trước summary, và đưa body pack vào
   prefix ổn định. Bốn file nằm trong bảng surface của plan `260829-1349-c1-search-
   and-evidence` (đã đóng) nên cần amendment này chứ không phải một dòng nới:

   | Surface | Giới hạn |
   |---|---|
   | `src/agent/messages.py` | `ContextComposition` tám layer · `context_text` (bản chiếu model đọc) · rung ageing chủ động · ba block của system message. **Không** đổi `wrap_result`, không đổi bốn rung của thang phục hồi, không đổi `dedup_key` |
   | `src/agent/loop.py` | body vào transcript · `_appended` là **một** danh sách cho cả reservation lẫn message · `cache_identity` trên `CompletionRequest.metadata`. **Không** đổi `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_TOOL_CALLS`, `SYSTEM_NOTE_TOKENS`, ba trigger của C5 |
   | `src/agent/prompt/sections.py` | **chỉ** `PROMPT_VERSION` 3.0.0 → 3.1.0 và comment giải thích; không một chữ prose nào đổi |
   | `apps/api/golden/context_replay.py` (mới) | export trace → corpus, replay corpus → report. **Không** importer nào từ `src/` ở chiều ngược lại; `replay` thuần: không network, không model, không đồng hồ |
   | `apps/api/golden/run.py` | `spend_for` tách fresh / cached read / cache write; `input_tokens` **giữ nguyên tên và nguyên cột** nên artifact cũ vẫn so được |
   | `apps/api/golden/README.md` | mục context replay + bốn counter của `cost`; **không** đụng ngưỡng C1 |
   | `apps/api/scripts/probe_prompt_cache.py` (mới) · `Makefile` | probe cache + ba target `golden-context-export`/`golden-context-replay`/`probe-prompt-cache`; không đụng target đang chạy |
   | `apps/api/tests/*` | test cho mọi surface trên; test mới **thêm ở cuối file** |
   | `docs/roadmap.md` · `CLAUDE.md` | §3 **C2** và §Quy ước — **không** đụng C1/C4/C5 và không đụng Track S |

   Bảng này **là** ranh giới. `golden/grade.py` **không** trong bảng và **không sửa**:
   ngưỡng C1 thuộc C1, và C2 chỉ **đọc** chúng. `src/core/llm/*` cũng không sửa —
   `Usage` đã tách cached/cache-write từ trước và `metadata` vốn không lên wire.

   **Gate "≥20% constructed token" của plan này không đạt được, và đó là số học.**
   Đo trên corpus golden: `system_core` chiếm **53,3%** context và prune không chạm
   được nó — nó là prompt, giống nhau ở mọi lượt gọi, và thứ làm nó rẻ là **cache**.
   `tool_results` là 43,1%, nên cắt 20% tổng đòi cắt **46,4%** của nó; biến *mọi*
   kết quả thành handle ngay sau đúng một lượt đọc chỉ cắt được 41%. Vượt ngưỡng đó
   là collapse một trang **trước khi model đọc nó lần nào**. Mức đã chọn —
   `SELECTION_CALLS = 1` · `RESULT_CALLS = 2` — cho **−13,85%** và mất **0** URL.
   Cùng hình dạng với tiêu chí citation của C1: một ngưỡng viết trước khi có phân bố.

   **Mở thêm 2026-08-29** cho plan
   `plans/260829-2304-signal-desk-analysis-compiler/` — Signal Desk đi từ "chọn
   một Study viết sẵn" sang **analysis compiler**: model soạn kế hoạch tính và
   cấu trúc trình bày trên ba trục độc lập (dữ liệu · phép tính · trình bày),
   engine tính mọi con số, board là artifact render lại được. Bất biến S0 giữ
   nguyên và siết thêm một bậc — **model không bao giờ gõ một con số thị
   trường**, mọi số là tham chiếu `(frame, row, col)` server resolve. Bảng dưới
   đây phủ cả mười phase; mỗi surface kèm giới hạn của nó:

   | Surface | Giới hạn |
   |---|---|
   | `src/studies/{frames_buffer,contracts,widgets}.py` | frame kind/role/provenance mới, `store_frame` tổng quát, catalog thêm 6 widget; **không** đổi luật ownership theo Turn, không xoá version cũ |
   | `src/studies/{composer,grammar,layout,lint,archetypes,auto_compose}.py` (mới) | Board DSL v2 và luật trực quan; thuần hàm, không đọc DB ngoài `frames_buffer` |
   | `src/studies/warmup.py` | **thêm 2026-08-30 lúc code review phase 02** — **đúng một** khối `try/except` dịch `QuotaRefused` thành `StudyRefused(COHORT_WARMING)`. `ingest._fetch_from_vnstock` giờ gọi arbiter, arbiter **raise**, và `run_study` chỉ bắt `StudyRefused` — nên không có khối này thì một Study intraday với Redis chết thành lỗi tool thô đếm vào `same_tool_failure_halt_after`. Không đổi `WARMERS`, không đổi `DEFAULT_SESSIONS`, không thêm requirement |
   | `src/studies/compute/*` (mới) | sandbox + AST validator; **không** import `stocks`, không mạng |
   | `src/studies/templates/*` (mới) + 4 file Study cũ | port thành template; runner cũ xoá sau khi fixture khớp |
   | `src/agent/tools/{query,compute,evidence}.py` (mới) · `tools/{studies,signals,web}.py` | đăng ký tool mới; `render_signal_desk` nhận schema v2; **không** đổi SSRF/denylist/`MAX_PAGE_TEXT_CHARS` của web |
   | `src/agent/tools/__init__.py` | **thêm 2026-08-30 lúc thi công phase 02** — `register_all` gọi thêm registrar mới. Thứ tự gọi phải khớp thứ tự bundle mở ra: hai thứ tự lệch nhau là hai hợp đồng phải khai riêng, và resolved-surface cache key trên một trong hai |
   | `src/agent/toolsets.py` | bundle `signals` thêm `query`,`compare_fields`; `studies` thêm `compute`; `web` thêm `frame_from_evidence`; `CHAT_TOOLSETS` vẫn literal |
   | `src/agent/loop.py` | **đúng một** hook auto-compose cuối Turn trong mode `signal_desk` + cập nhật `SIGNAL_DESK_NOTE`; không đổi ba hằng trần |
   | `src/agent/messages.py` | **chỉ** `signal_desk_of` nhận `autoComposed`; không đụng prune/estimate (C2 sở hữu) |
   | `src/agent/prompt/sections.py` · `domain/vn_equity.py` | section TOOLS + câu Signal Desk core; body PLAYBOOK soạn board; bump `PROMPT_VERSION`, pack `VERSION`. **Chờ C2 phase 05.** *Ngoại lệ hẹp, 2026-08-30 lúc thi công phase 02:* danh mục tool trong section TOOLS được cập nhật ngay khi một tool mới đăng ký, vì một tool đã đăng ký mà prompt không gọi tên là một tool model không với tới — và một test khẳng định đúng điều đó. **Chỉ prose danh mục**, không luật, không playbook; bump minor `PROMPT_VERSION`. Dùng lần hai 2026-08-30 lúc thi công phase 03+04 (`compute`, `frame_from_evidence`; 3.2.0 → 3.3.0, "mười bốn công cụ" → "mười sáu") |
   | `src/stocks/financial/reads.py` | **chỉ import để đọc** từ `tools/query.py`; không đổi hàm đang có. **Nới 2026-08-30 lúc code review phase 02** — bảng gốc ghi "≤ 2 hàm", thực tế **5**: `lines_for_many` · `ratios_for_many` · `periods_for_many` · `ratio_periods_for_many` · `periods_held_by`. Ba cái sau là ba câu hỏi khác nhau mà gộp lại sẽ trả lời sai: kỳ của bảng statement ≠ kỳ của bảng ratio (hai response provider độc lập, rollback theo part), và "mã này nộp quý nào" là thứ duy nhất tách được `quarter_not_filed` khỏi `statement_line_missing` |
   | `src/stocks/financial/{fetch,store}.py` + revision mới | bảng nhãn `financial_statement_item` (item_id → label vi/en), nạp một lần; phase 10 nới `periods` |
   | `src/stocks/signals/bars.py` | **một** nhánh: `market_cap_vnd` suy từ `close × reference.shares` khi bar không có; không đổi basis/band |
   | `src/stocks/signals/registry.py` | đặt giá trị `better` cho field nào có hướng tốt; không đổi công thức field nào |
   | `src/stocks/signals/fields.py` | **thêm 2026-08-30 lúc thi công phase 02** — enum `Direction` + **một** trường tuỳ chọn `SignalField.better` mặc định `None`. Bảng gốc ghi trường này ở `registry.py`, nhưng dataclass sống ở đây; `registry.py` chỉ đặt giá trị. Không đổi chín khai báo bắt buộc, không đổi một `__post_init__` nào đang có |
   | `src/stocks/intraday/ingest.py` · `Makefile` | target `backfill-intraday SCOPE=declared`; không đổi shape bar |
   | `src/stocks/providers/vnstock_data.py` (mới, phase 10) · `core/quota.py` · `requirements.txt` · `.env.example` · `docker-compose*.yml` | adapter Sponsor sau contract; arbiter 4 cửa sổ; **hỏi user trước** khi thêm dep |
   | `src/alpha/models.py` · `alembic/versions/*` (thêm) | `financial_statement_item`; phase 10: `foreign_flow_daily`, `macro_series`; `agent_artifact` **không đổi cột** — spec v2 sống trong `signal_desk_spec` JSONB |
   | `apps/web/src/components/signal-desk/**` · `lib/alpha-desk/types.ts` · `lib/signal-issues.ts` · `contracts/signal-desk-widget-catalog.json` | grid, KPI strip, caption, 6 widget, badge nguồn web; không đụng `SignalDeskToggle` |
   | `contracts/fixtures/artifact-*.json` | **thêm 2026-08-30 lúc thi công phase 02** — **chỉ sinh lại bằng `make contracts`**, không sửa tay. Payload frame đổi khi `Frame`/`Provenance` đổi, và một test giữ fixture bằng đúng thứ Study sinh ra |
   | `apps/api/golden/*` · `apps/api/Makefile` | corpus `signal_desk.json`, grader mới, target `golden-run MODE=signal_desk` |
   | `apps/api/scripts/seed_statement_item_labels.py` (mới) | nạp nhãn một lần từ ba mã đại diện ba template; chỉ ghi bảng nhãn |
   | `src/studies/format.py` (mới) | **thêm 2026-08-30 lúc thi công phase 05** — bảng gốc khai sáu module mới của board và quên module thứ bảy. Thuần hàm đọc một ô thành chuỗi người Việt đọc (dấu thập phân phẩy · `tỷ`/`triệu`/`nghìn tỷ` theo đơn vị · `%` một chữ số lẻ). Một chỗ duy nhất, vì KPI và caption lưu **đã format**: board mở lại sau một tháng vẽ đúng chuỗi đã ghi, không phải chuỗi build hôm nay suy ra. **Không** import `stocks`, không đọc DB |
   | `apps/web/src/app/globals.css` | **thêm 2026-08-30 lúc thi công phase 06** — đúng **hai** token mới (`--widget-benchmark`, `--widget-warning`) cho hai role board thêm, mỗi token một cặp sáng/tối kèm số tương phản đo được. `winner`/`loser` dùng lại token của cặp thị trường và `stale` dùng lại `--widget-neutral`, nên chỉ hai. **Không** đổi một token đang có, không thêm biến ngoài khối widget |
   | `src/agent/evidence/numbers.py` (mới) | **thêm 2026-08-30 lúc thi công phase 04** — phase 04 khai file này trong `Related Code Files` của nó, bảng gốc quên. Thuần hàm đọc số như trang viết (dấu thập phân VN/EN · hệ số `tỷ`/`triệu`/`nghìn tỷ` · chữ số nghĩa); **không** import `stocks`, không đọc DB, không đụng ba module `evidence/` của C5 |
   | `apps/api/tests/*` · `apps/web/src/**/*.test.*` | test mọi surface trên; **thêm ở cuối file**, không reflow |
   | `docs/roadmap.md` · `CLAUDE.md` | §4 S1, §3 C4 (hai mục checklist), §Quy ước — **không** đụng Track S2/S3, không đụng §3 C1/C2/C5 ngoài một dòng tham chiếu |

   Bảng này **là** ranh giới. File ngoài bảng cần amendment mới, không phải một
   dòng nới. Hai điểm đã kiểm lại với code thật lúc thi công phase 01:
   **head alembic là `b5d1c7e04a83`** (một head duy nhất, 35 revision — không
   phải `a3f7e21b8d54` như plan đoán), và **`pandas`/`numpy` đã nằm trong
   `requirements.txt`** (`intraday/ingest.py` đã import pandas), nên câu hỏi mở
   về dependency của phase 03 đã có trả lời và không phải hỏi lại. Bản đang cài,
   đo 2026-08-30: **pandas 2.3.3 · numpy 2.2.6 · Python 3.12.3**.

   **Sandbox `compute` có ba trần, và chỉ hai trần chạy ở mọi nơi — chốt
   2026-08-30, đo tại chỗ.** `RLIMIT_CPU` (5 s) và `RLIMIT_FSIZE` (0) áp được
   khắp nơi; `RLIMIT_AS` (512 MB) **chỉ Linux** — macOS trả `ValueError` cho
   `setrlimit(RLIMIT_AS, …)`. Nên `worker._apply_limits` trả về danh sách trần
   *thật sự* áp được (`['cpu','memory','files','privileges']` trong container ·
   `['cpu','files']` trên máy dev — mục thứ tư thêm 2026-08-30, xem dưới) và
   đồng hồ của tiến trình cha
   (`WALL_SECONDS = CPU_SECONDS + 3`) là sàn ở mọi nền. 512 MB là số **đo**:
   `VmSize` của image sau khi import pandas + numpy là 195 MB. `preexec_fn`
   **không dùng** — handler chạy trong `asyncio.to_thread` của server đa luồng và
   `preexec_fn` giữa `fork` và `exec` ở đó có thể deadlock; con tự đặt trần.

   **Ba cổng import cho `compute`, và một test giữ chúng không mâu thuẫn.**
   `validator.ALLOWED_MODULES` cấm bằng cách đọc code — đó là cổng cho model một
   câu để sửa. `worker._safe_builtins` bọc `__import__` — đó là cổng khi code tới
   được tiến trình bằng đường khác. `worker._close_the_import_gate` (thứ ba, 2026-08-30) bọc
   `builtins.__import__` và `importlib.import_module` **thật**, nên nó giữ cả khi
   code chạy qua một `exec` được tiêm builtins thật. `worker.ALLOWED_MODULES` chép
   lại hằng của validator: biên tiến trình là chỗ duy nhất một hằng chép lại rẻ
   hơn cái import xoá nó đi, và `tests/studies/test_compute_runner.py` khẳng định
   hai bên bằng nhau **và** khẳng định allowlist không giao với
   `IMPORT_DENYLIST` — giao nhau là một refusal model không thể tránh.
   `socket.socket` bị thay bằng một **class**, không phải một hàm — hàm vẫn chặn
   được kết nối nhưng refusal ra thành `TypeError` về kiểu đối số, thứ model
   không đọc được để sửa.

   **Sandbox `compute` từng thoát được, và chỗ vá là tiến trình con chứ không
   phải AST — đo 2026-08-30, tái hiện trong `stockmassive-api:latest`.**
   `pd.io.common.os` **là** `sys.modules['os']`: pandas giữ tham chiếu tới module
   thật và phát nó ra như một attribute thường, nên một phép tính gọi `os.popen`
   chạy lệnh shell và `os.open('/etc/passwd')` mà **không** viết chữ `import` nào
   — validator báo 0 vi phạm, vì không có gì để đọc. Bề mặt attribute của một
   module singleton là vô hạn, nên câu trả lời **không** phải một danh sách tên
   dài hơn. Nó là: trong tiến trình chỉ có **một** đối tượng `os`, nên gỡ các lời
   gọi nguy hiểm khỏi chính nó đóng mọi đường tới nó cùng lúc. Bốn tầng, theo
   năng lực chứ không theo tên module (`worker.ESCAPE_HATCHES`): sinh tiến trình ·
   nạp mã máy · với tới đối tượng ngoài tầm (`sys._getframe`, `gc.get_objects`) ·
   giải tuần tự thành lời gọi (`pickle`). Mở file thì **thu hẹp** chứ không chặn
   (`worker._SOURCE_ONLY` — chỉ `.py/.pyc/.so`), và `builtins.exec`,
   `builtins.compile`, `marshal.loads` **cố ý để nguyên**: cả ba là đường máy
   import nạp một module, và đóng chúng đóng luôn chính pandas — đo được, `np.rec`
   được nạp ở lần `pct_change` đầu tiên của một Turn. Trên hết, con **hạ quyền
   xuống `nobody`** sau khi import xong (`limitsApplied` có `privileges`), nên
   `/proc/1/environ` — nơi `DATABASE_URL` và khoá provider sống — không còn đọc
   được. Đây là **hardening có đo, không phải chứng minh**: ranh giới đầy đủ là
   một hộp OS (uid không phải root ở cấp container, rootfs read-only, seccomp),
   và phần không cần dependency mới đã làm ở đây.

   **Role của một so sánh đi qua `cell_roles`, không phải `point_roles`.** Plan
   phase 03 viết `result.attrs["point_roles"]`; đúng là `cell_roles`. Một bảng
   mã × chỉ tiêu có mã thắng theo **cột**, và `point_roles` sẽ nói cả *hàng*
   thắng — đúng câu mà một so sánh sinh ra để tránh (luật ba mức đã viết ra ở
   `studies/contracts.py` trước phase này). `frames_io` nhận cả ba mức.

   **Reader `reference` sống ở `stocks/signals/bars.py`, không ở `tools/query.py`.**
   Cùng một phép đọc `provider_snapshots capability='reference'` phục vụ hai
   caller: nhánh market cap của `bars.py` và source `reference` của `query`.
   Đặt nó ở `bars.py` là chiều import duy nhất hợp lệ — `src/stocks/*` không
   được import `src/agent/*` (`toolsets.py` gọi đó là "the edge to not add"),
   nên chiều ngược lại là chiều đúng.

   **Mở thêm 2026-08-30, lúc thi công phase 07+08** — Study thành template trên
   chính đường ống của compiler. Bảng gốc của plan này khai *hai* loại bước
   (`QueryStep`, `ComputeStep`) và một `runner.py` viết lại; những gì thật sự
   phải sửa rộng hơn, mỗi surface kèm giới hạn của nó:

   | Surface | Giới hạn |
   |---|---|
   | `src/studies/contracts.py` | `QueryStep` · `ReadStep` · `ComputeStep` · `StudyDefinition` mới (`archetype` · `plan` · `board` · `headline` · `precheck`) · `StoredArtifact.steps`. `compute`/`view`/`frames`/`widgets` **xoá**, và `StudyResult` cùng với chúng — nó là kiểu trả về của `compute`, nên giữ lại một class không ai dựng là mời người sau dựng nó |
   | `src/studies/runner.py` | viết lại thành executor plan; `read` và `warm` **inject**, `as_of` tuỳ chọn. Không import `src/agent/*` |
   | `src/studies/registry.py` | check import-time cho plan + board; `catalog()` thêm `archetype` |
   | `src/studies/composer.py` | nhận `compile_board`/`resolve`/`merged_provenance`/`newest_version`/`source_of` từ `agent/tools/studies.py`. **Một compiler**, vì template và model đi cùng một đường; **không** đổi `infer_widget`/`presentation` |
   | `src/studies/templates/*` (mới) | bốn template + `params.py` dùng chung. `params.py` gom bốn params model **về một chỗ**, vì `_check_the_parameters_agree` là luật vắt qua cả bốn |
   | `src/studies/compute/runner.py` | `max_rows`/`max_columns` thành **tham số**, mặc định là trần của model. Trần *hình dạng* câu trả lời, **không** phải trần literal — validator không có ngoại lệ nào cho template |
   | `src/studies/compute/frames_io.py` | đúng một chữ trong một note (`do câu hỏi nêu ra` → `đã khai báo`), vì một template khai giả định mà câu hỏi không nêu |
   | `src/agent/tools/query.py` | `read_source` + `SourceRead` + `SourceUnavailable` tách khỏi `QueryTools.query`; `_answered` đếm phiên theo trục, không theo hàng. **Không** đổi `SOURCES`, `MAX_WINDOW`, `MAX_SYMBOLS`, `MAX_QUERY_ROWS/CELLS` |
   | `src/agent/tools/studies.py` | `run_study` inject `read=query.read_source`, trả thêm `kpiCount`/`autoComposed`/`frames`; mất năm hàm đã dời sang composer |
   | `src/agent/prompt/sections.py` · `domain/vn_equity.py` · `loop.py` | phase 08 — xem dưới |
   | `contracts/fixtures/artifact-intraday-liquidity.json` · `contracts/signal-desk-widget-catalog.json` | **chỉ sinh lại bằng `make contracts`**. Catalog widget đã **stale từ phase 05/06** (thiếu sáu widget mới) và test cũ không bắt được vì nó chỉ kiểm một chiều |
   | `apps/api/tests/*` | `template_run.py` (mới) + viết lại bốn test Study + `test_registry`/`test_runner`/`test_agent_study_tools` |
   | `apps/web/src/components/signal-desk/signal-desk-panel.test.tsx` | fixture giờ là board v2; **chỉ** test, không đụng component |

   **Bước thứ ba (`ReadStep`) là ngoại lệ hẹp, và nó nằm trên trục ĐỌC.** Ba câu
   trả lời của store không có source `query` nào: lưới bước giá của sàn dưới một
   thang giá, chỉ tiêu lợi nhuận mà **template báo cáo của chính người nộp**
   quyết, và một phép quét rộng hơn số mã model bao giờ cũng được đưa
   (`MAX_SYMBOLS = 10`). Cả ba là **sự thật về hình dạng store**, không phải số
   học. Nên template được đặt tên một reader; nó **không** được đặt tên một máy
   tính. Mọi con số một template suy ra vẫn đi qua `studies/compute` và validator
   của nó, đúng điều kiện model nhận — và `registry` **chạy validator lúc
   import**, nên "không gõ số thị trường" là thuộc tính của bản build chứ không
   phải của sự cẩn thận. Model không với tới `ReadStep` được: đường duy nhất tới
   một template là `run_study(name)` với một cái tên đã đăng ký.

   **Ba con số đo lúc port, và cả ba đảo một câu của plan.** (1) Fixture khớp
   1e-9 cho **mọi** frame còn sống của cả bốn Study, trên store thật. (2) Frame
   `tiles` của cả bốn **bỏ đi**: consumer duy nhất của nó là block `stat_tiles`
   của spec v1, và dải KPI của board v2 *là* thứ thay nó — mỗi ô của `tiles` giờ
   là một `Ref` server tra, nên phép so mạnh hơn chứ không yếu đi. (3) Gate
   "thời gian chạy ≤ hiện tại + 20%" **không đạt được, và đó là số học**: bốn
   Study viết tay chạy 5–50 ms, một lượt gọi sandbox tốn **260 ms** (đo, n=4),
   và một plan có 4–8 bước compute. Đo được: 1,12–2,20 s mỗi template, tức
   23–330×. Trần thật sự là `TURN_COST_MICRO_USD` và `MAX_TOOL_ROUNDS`, và một
   giây rưỡi trong một Turn 30 giây không chạm cái nào. Con số +20% viết trước
   khi có phân bố, cùng hình dạng với hai gate đã đảo trước đó của C1 và C2.

   **`sessionsUsed` từng sai một bậc độ lớn, và nó sai ở hai chỗ.**
   `read_source` đặt `sessions_used = len(frame.rows)`, nên một lượt đọc 15 phút
   của 30 phiên khai **480 phiên**; `merged_provenance` lấy `max` qua mọi frame,
   nên một frame derived 24 hàng khai **24 phiên** cho một thang giá một phiên.
   Sửa hai chỗ: `_answered` đếm giá trị khác nhau của trục `session` (rồi
   `period`, rồi hàng), và phép gộp chỉ lấy `sessionsUsed` từ frame **nguồn
   store**, bỏ qua frame derived — một frame derived khai chiều cao của chính
   nó, và chiều cao không phải số phiên.

   **`method_notes` khai trên từng bước, và nó dẫn đầu dải.** Không lớp nào
   dựng provenance của một bước biết được câu này: `read_source` mô tả một bảng
   và `derived_provenance` mô tả một phép tính, còn "vùng tích luỹ là hai bin kề
   nhau trong hai mươi" là sự thật về *câu hỏi này*. Trần gộp `MAX_MERGED_NOTES
   = 6` áp sau, nên thứ bị cắt là dòng của máy (`mã <digest>`), không phải câu
   của template.

   **Phase 08 — prompt 3.4.0, pack 3.0.0.** Ba chỗ đổi ở core (mục
   `render_signal_desk` mô tả một *board* chứ không phải danh sách khối; đoạn
   chế độ nói "mọi câu hỏi nhận được số đều phải thành board"; **một** câu
   invariant: số trên một bức tranh là tham chiếu tới ô, không phải thứ gõ vào)
   và playbook bảy bước soạn board xuống **body của pack**. Đo: core +228 token
   (136 mục lục + 92 luật) — trên mức +150 plan đoán, và mục lục là loại tăng mà
   `CATALOGUE_GROWTH_SINCE_THE_SPLIT` đã có tên; body **1.064** token, dưới trần
   1.100. Hai gate token của C5 giữ nguyên ngưỡng, chỉ thêm hai hằng có tên.

   **Bảy phát hiện của code review, sáu sửa.** Đáng ghim ba: (1) `run_study`
   **return** refusal từ trong `with self._open()`, và return là lối ra bình
   thường nên session commit — mọi artifact bước đã chạy ở lại, và
   `auto_compose_for_turn` vẽ **mọi** frame một Turn thu được, nên một Study từ
   chối trả lời kết thúc Turn bằng board dựng từ mảnh vụn của chính nó
   (`session.rollback()` trước khi trả). (2) `ranking` của intraday sort cột
   **đã làm tròn** bằng quicksort mặc định của pandas — đo được đảo thứ tự ở
   n=17, và hàng 0 là cả bốn KPI cộng toàn bộ headline; `kind="mergesort"` để
   tie giữ thứ tự đồng hồ, cùng leader mà `idxmax` cho dấu `focus`. (3)
   `auto_compose` sẽ vẽ frame làm việc: scope `market` của screener lưu
   **28.784 dòng / 2,02 MB** (đo, 2,05 s cả lượt), và đó là bảng Study đọc
   *trên đường* tới câu trả lời — `MAX_DRAWABLE_ROWS = 500` (trần câu trả lời
   của chính sandbox) loại nó, và một Turn chỉ có frame như vậy trả `None` thay
   vì board rỗng. Ba cái còn lại: `StudyContext.scratch` cho hai read của một
   plan khỏi lệch snapshot, ô heatmap của phiên không giao dịch về lại `None`,
   và note "giả định đã khai báo" chỉ đếm constant là **số** (cửa `constants`
   cũng là cửa duy nhất để một nhãn tiếng Việt vào sandbox).

   **Ba thứ mất khi port, ghi ra chứ không giấu.** (1) Cổng
   `mixed_price_basis` của `entry_condition_review`: `BAR_COLUMNS` của `query`
   không có `price_basis`, và mọi dòng đang lưu đều `adjusted_at_source` nên
   cổng chưa từng nổ — thêm cột là việc của một amendment sau, không phải một
   dòng nới ở đây. (2) `horizon_sessions` trên 250 vẽ 250, vì `MAX_WINDOW` là
   250; `sessionsUsed` nói ra sự thật đó. (3) KPI của `entry_condition_review`
   không mang `role`: một `role` là chữ viết trước khi có số, nên màu theo dấu
   của một con số chưa tính chỉ có hai lựa chọn — đôi khi nói dối, hoặc không
   nói gì.

   **Mở thêm 2026-08-30, sau hai Turn hỏng đo được trên production** — spine
   daily đứng im ba ngày và một câu trả lời trích giá phiên cũ mà không nêu
   phiên. Nguyên nhân là một **điểm bất động**: `backfill_daily` lấy mốc "đã
   mới" từ `max(trading_day)` của chính series nó ghi, nên mọi mã chạm mốc đó
   đều "current" **với chính nó** và spine không bao giờ vượt được phiên mới
   nhất của mình. VNINDEX rõ nhất — một mình một series, so với chính nó, skip
   mọi lượt chạy sau khi đủ depth. Sáu surface, mỗi cái một giới hạn:

   | Surface | Giới hạn |
   |---|---|
   | `src/stocks/backfill_daily.py` | `latest_expected_session` (ngày trong tuần gần nhất theo đồng hồ ICT) thay `newest_stored_session`; **không** đổi `is_deep_enough` ngoài mốc truyền vào, không đổi `DEFAULT_SESSIONS`, không đổi luật `observed_at` |
   | `src/main.py` | cảnh báo spine cũ thành **hành động**: khi `backfill_daily_scheduled` bật thì nạp bù `index` + `declared` sau khi startup xong. **Không** `market` — 1.523 lời gọi không phải thứ tiêu lúc boot. Không chặn startup, không raise |
   | `docker-compose.yml` · `docker-compose.prod.yml` · `.env.example` | forward `BACKFILL_DAILY_SCHEDULED`; mặc định vẫn `false`, không đổi biến nào đang có |
   | `src/agent/tools/query.py` | `_symbols` trả `SymbolSelection` — phục vụ phần đọc được, nêu tên phần không đọc được (`notCovered`) thay vì từ chối cả lô. **Không** đổi `MAX_SYMBOLS`, `SOURCES`, `MAX_WINDOW` |
   | `src/agent/prompt/sections.py` | hai đoạn ở section HONESTY (as-of là một phần của con số · cấm mô tả sai lượt chạy của chính mình) + `PROMPT_VERSION` 3.5.0. Ở **core**, vì Turn không kích trigger body là Turn dễ trả lời bằng trí nhớ nhất |
   | `apps/web/src/components/signal-desk/{board-section,kpi-strip}.tsx` | ngôn ngữ thị giác của board theo design đã duyệt: card cho từng block, bo 13px, nhãn micro hoa `.09em`, số KPI 1.42rem mono. **Không** thêm token mới vào `globals.css` — chênh lệch với design dưới hai điểm độ sáng |

   Hai con số đo tại chỗ: sau khi sửa, `bar_daily` nhận phiên **2026-08-28**
   (STB đóng cửa 75.500, đúng con số user đối chiếu), 30/30 mã declared, 55.776
   dòng, 0 lỗi. Trước khi sửa mọi lượt chạy đều `attempted=0 skipped=all`.

Nguồn data ngoài duy nhất được phép: **vnstock Bronze giai đoạn dev
(180 req/phút), Diamond khi lên prod (600 req/phút, licence phân phối
≤500 user)**. DNSE, FiinQuant, CafeF **vi phạm điều khoản SaaS** — code đã rip
2026-08-25, và **dữ liệu FiinQuant đã xoá khỏi DB 2026-08-29** (71.773 dòng,
revision `a3f7e21b8d54`). `ProviderSource` giờ chỉ còn một member: `VNSTOCK`.

Rollback: tag `v-with-market-surfaces` trên `origin` (đã push 2026-08-26)
+ backup `backups/pre-rip-out-260825.sql.gz` (7.2M dump full DB).

# Roadmap harness

Authority: **`docs/roadmap.md`** — hai track, mỗi phase có Objective ·
Trước→Sau · checklist · gate. Tóm tắt:

- **Track C — Core harness (mọi user):** C0 nền lane chat (Current, xong
  2026-08-25) · C1 search & tổng hợp có citation (**Current, tốt nghiệp
  2026-08-29** — ba gate đo được đều đạt; tiêu chí *"số ngoài store không citation
  = 0"* **chuyển sang C4** vì đo được là nó bất khả với một grader đọc văn bản trả
  lời. Xem `plans/260829-1945-c1-evidence-graduation/reports/graduation-report.md`)
  · C2 context & cache ·
  C3 tool plane / nudge có trần / idempotency · C4 evaluator plane (Golden
  Question Set, dựng lại sau khi rip eval) · C5 domain pack + progressive
  instruction (Phase 1 cũ) · C6 tenant / permission / entitlement (Phase 2
  cũ) · C7 delegation có điều kiện · C8 domain pack thứ hai (Phase 3 cũ).
- **Track S — Signal Desk (paid):** S0 runtime qua Study (Current, đang đóng)
  · S1 thư viện Study + desk theo mã · S2 thesis + human approval · S3
  proactive scan. Mọi S mở sau gate C4; entitlement gắn ở C6.
- **Backlog:** realtime path (sau C8, chỉ vnstock Diamond).

## Đã chốt 2026-08-26 — Signal Desk qua Study

Lane chat kết xuất **Signal Desk** — surface phân tích động — thay vì chỉ trả
text. Từ vựng chuẩn 2026-08-28: **Signal Desk**, không còn "canvas" trong
code, contract hay tài liệu (cột `agent_artifact.signal_desk_spec`, revision
`f8c2d4a96e17`). Cơ chế:
model chọn một **Study** (recipe phân tích có tên, có version,
deterministic) và điền params; **engine tính, artifact giữ số, registry
vẽ**. Ba luật cứng:

- **Frame** — dãy/ma trận số — **không bao giờ** vào message gửi model, dù
  nó tới từ một template hay từ `query`/`compute` model tự gọi. Model chỉ
  thấy `headline` (~300 token) và các id addressable. Test đọc transcript
  giữ luật này.
- Widget có **name + version**, danh mục ở `contracts/signal-desk-
  widget-catalog.json` (sinh từ `src/studies/widgets.py`, test giữ đồng bộ).
  Viewer gặp version không biết → fallback `data_table`, không crash.
- `as_of` đóng băng lúc tạo artifact; mở lại thread là **render lại
  artifact**, không tính lại.

Plan thi công: `plans/260826-2158-study-artifact-canvas/`. Bảng
`agent_artifact` giữ một lần chạy Study. Ba case đầu: intraday liquidity
profile · condition review · earnings dislocation screener.

# Tham chiếu bắt buộc — `docs/hermes/`

Mọi đề xuất và triển khai vào `src/agent/` phải đọc `docs/hermes/` trước.
- Vào `hermes-synthesis-260821-0030.md` trước (bản hợp nhất 9 vùng), rồi
  mở đúng report của vùng đang làm: `hermes-core-loop` · `hermes-turn-
  lifecycle` · `hermes-route-subagent` · `hermes-context` · `hermes-tools`
  · `hermes-memory` · `hermes-orchestrator-state` · `hermes-mcp-ops-eval`
  · `hermes-web-security`.
- Đây là **research**, không phải mô tả code hiện tại. Kiểm lại với code
  thật trước khi dựa vào một câu đối chiếu.

# Commands

- Dev: `pnpm dev` (db/redis/api trong Docker + web trên host — API 8000,
  web 3000). Web trong container: `pnpm dev:full`.
- Debug Python trên host: `pnpm dev:api:detach` rồi `make dev` tại
  `apps/api`.
- Dừng / logs: `pnpm stop`, `pnpm logs`, `pnpm logs:api`.
- **Nạp spine daily:** `make backfill-daily SCOPE=index|declared|market` tại
  `apps/api`. Chạy `index` trước — VNINDEX định nghĩa Trading Day calendar.
  Tự động: đặt `BACKFILL_DAILY_SCHEDULED=true` để scheduler chạy cả ba scope
  nối tiếp lúc 16:30 giờ VN. **Mặc định TẮT** — `scheduler_enabled` mặc định
  `True`, nên một job đăng ký vô điều kiện sẽ tự gọi provider ngoài (scope
  `market` = 1.523 request) trên mọi máy dựng stack lên. API startup log
  WARNING kèm lệnh cần chạy khi spine stale (`STALE_AFTER_DAYS = 4`).
- Đổi code Python: container mount `src/` + `alembic/`, nên
  `docker compose restart api` là đủ — không build lại.
- Test API: `make test` tại `apps/api` — chạy trên **host**, container
  không mount `tests/`.
- Test một file API: `pytest tests/path/test_x.py -v` · một case:
  `pytest tests/path/test_x.py -k "<tên>"`.
- Test web: `pnpm test` tại `apps/web` · một file:
  `pnpm vitest run src/path/x.test.ts` · một case:
  `pnpm vitest run -t "<tên test>"`.
- Cổng web: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại
  `apps/web`.
- E2E: `pnpm test:e2e` tại `apps/web` — Playwright dựng FastAPI thật
  (`apps/api/tests/e2e/server.py`) + bản production của Next. Tắt
  `pnpm dev` trước.

# Tooling

- pnpm 9, Node 22. Không npm, không yarn.
- **Không** phải pnpm workspace: root lockfile rỗng, `apps/web` có
  `package.json` + lockfile riêng. Cài dep web bằng
  `pnpm --dir apps/web add <pkg>`.
- Python dep ở `apps/api/requirements.txt`; Makefile tự dùng `.venv` nếu
  có.
- Nhiều worktree song song: đặt `API_PORT`/`WEB_PORT` khác nhau và sửa
  `CORS_ORIGINS`.

# Không được đụng

- `apps/api/alembic/versions/**` đã commit — thêm revision mới, không sửa
  file cũ. Bảng dữ liệu thị trường (bar realtime, monitor snapshot, price
  history intraday, watchlist, alpha desk, sector historical...) tạm giữ
  trong DB — revision drop tách ra sang PR sau khi backup đã xác minh
  restore được.
- Không commit secrets, `.env`, dump database, dữ liệu nhạy cảm, file
  sinh tự động. `backups/` là thư mục cho snapshot trước rip-out — không
  commit lên remote (kiểm `.gitignore` trước khi push).
- Không chạy `git push`, không tạo PR khi chưa được yêu cầu trực tiếp.
- Không đổi schema/dữ liệu (migration, drop, bulk update) khi chưa
  backup.

# Quy ước

- **Nhánh:** rip-out lớn dùng branch riêng (hiện tại: `refactor/harness-
  first`). Sau khi nhận PR về `develop`. Feature bình thường vẫn commit
  thẳng lên `develop`; `main` chỉ nhận merge từ `develop`.
- Commit: conventional commits, mô tả thay đổi kỹ thuật, không tham
  chiếu AI.
- Agent (`src/agent/`) trên khung Hermes-style (`registry` · `toolsets` ·
  `definitions` · `executor` · `guardrails` · `budget` · `untrusted`).
  Lane chat chọn bốn bundle `web` + `memory` + `signals` + `studies` =
  **16 tool** (12 → 14 với `query`/`compare_fields`, → 16 với `compute`/
  `frame_from_evidence`, 2026-08-30) — chính prompt cũng tự nói "mười sáu
  công cụ", và một test khẳng định prompt gọi tên **mọi** tool bundle mở ra.
  `toolsets.CHAT_TOOLSETS` là selection duy nhất và phải được **viết
  ra**: `AgentLoop(toolsets=None)` mặc định về đúng tuple đó. Thêm/đổi
  tool đi qua `registry`/`toolsets`/`definitions`, không hardcode trong
  `loop.py`.
- **Lane chat đọc store**, đảo `1e7b936`. Chỉ đọc Signal Field đã đăng ký,
  cho mã trong Universe, ở phiên gần nhất đã đóng. `get_field` có **hai
  chữ ký từ một registration**: `ToolContext.symbol` có (từng cho lane
  Analysis — lane đó đã bỏ) thì nó thắng; không có context (lane chat) thì
  `symbol` là argument. `trading_day` **không bao giờ** là argument.
- **Prompt đi hai tầng từ `PROMPT_VERSION` 3.0.0** (2026-08-29; **3.4.0
  từ 2026-08-30**). *Core* — `prompt/sections.py`, chín section, 6.255
  token — đi với **mọi** Turn và vẫn là prefix cacheable: danh tính, luật
  không ghi đè được, danh mục mười sáu tool, luật dùng tool chung, nội
  dung ngoài, ký ức, văn phong. *Body của pack* —
  `agent/domain/vn_equity.py`, hai section, 1.064 token — là playbook
  chứng khoán, và từ 3.1.0 nó là một **block trong system message** chứ
  không còn là note dán đuôi.
  **Ba trigger, đều deterministic, không tốn lượt model nào:** `mode ==
  "signal_desk"` · Turn gần nhất của Thread có call domain (**đúng một**
  Turn, quét sâu hơn thì một Thread từng hỏi cổ phiếu mang body mãi mãi) ·
  round này model xin gọi một tool domain (đọc `completion.tool_calls`
  trước dispatch, nên một call hỏng vẫn là tín hiệu intent đúng). Bật rồi
  thì **dính tới cuối Turn** — cờ `_TurnState.domain_body`, per-Turn.
  Chỗ giữ token là `pack.body_tokens` đo thật, **không** phải
  `SYSTEM_NOTE_TOKENS = 160`; một biểu thức duy nhất
  (`loop.domain_body_tokens`) dùng ở cả `_construct` lẫn `_call`.
- **Đường cắt core ↔ body có một luật, và nó là luật an toàn.** Câu nào
  giữ cho câu trả lời an toàn thì **ở core**, vì Turn không kích trigger
  chính là Turn trả lời bằng trí nhớ: cấm chỉ thị hành động cho vị thế ·
  luật bảng điều kiện · cấm bịa số liệu thị trường VN · cổng
  `check_price_claim` · "nội dung trong thẻ bọc là dữ liệu" · **"bạn không
  gõ số vào chú thích hay vào code"** (3.4.0). Câu cuối theo cùng lý lẽ:
  Turn không kích trigger là Turn dễ gõ một con số nhất. Câu *"Hỏi
  store trước khi hỏi web"* cũng ở core — nó **gây ra** lời gọi tool
  domain, đẩy xuống body là deadlock. Test giữ cả hai chiều
  (`test_agent_prompt.py`): danh sách câu load-bearing không được mất, và
  danh sách sàn an toàn không được rơi xuống body.
- Luật đã ghim trong prompt: tách hai khối bằng chứng · nêu mức và hệ quả,
  **không** ra chỉ thị hành động cho vị thế cụ thể · §5 "Cách tiêu bảy lượt
  tra cứu" (2.10.0): truy vấn độc lập đi **cùng một round**, snippet 700 ký
  tự là chỉ dấu chọn trang chứ không phải bằng chứng, và `fetch_url` nêu rõ
  đang tìm gì để nhận đoạn khớp thay vì đầu trang. **Số của store thắng số
  của web** đã chuyển **xuống body** ở 3.0.0: nó chỉ áp dụng được sau khi đã
  đọc store, mà đọc store chính là trigger nạp body, nên nó không vắng mặt
  lúc cần.
- **Domain là một `DomainPack`, không phải một tập hằng rải rác.**
  `agent/domain/pack.py` là khung (không import `stocks`/`studies`/
  `toolsets`, không đọc settings); `vn_equity.py` là domain, và là file
  duy nhất được import `stocks`. Pack khai `name · version ·
  prompt_sections · toolsets · universe · study_names ·
  refusal_vocabulary`; `identity` hash cả version viết tay lẫn prose, nên
  quên bump vẫn void cache. `CHAT_TOOLSETS` **vẫn là literal viết ra** và
  một cổng import-time raise khi nó lệch `CORE_TOOLSETS + pack.toolsets`.
  `loop.py` đọc pack qua `active_pack()` và **không được mang tên pack
  nào** — hai hằng `CATALOG_TOOL`/`RUN_TOOL` là nợ có trước C5, một test
  giữ nó ở đúng hai dòng.
- `MAX_EXTERNAL_TOOL_CALLS = 7` (từ 6, 2026-08-29) chỉ tính tool có
  `reads_external` bật, không tính ba tool `signals`. `MAX_TOOL_ROUNDS = 4`
  ở lane chat. **Bảy đi cùng `guardrails.same_tool_failure_halt_after = 7`
  — hai số là một sự thật, đổi cái này phải đổi cái kia, và một test giữ
  đẳng thức** (`tests/test_agent_guardrails.py`). Bảy là phép đo, không
  phải số tròn: mục tiêu 2–3 tìm + 3–4 đọc = 5–7 call, một Turn web-first
  đo được 42.181 µUSD (n=20, golden) so trần `TURN_COST_MICRO_USD =
  500.000`. Giữ **dưới 8** có chủ đích — `MAX_EXTERNAL_CALLS_PER_ROUND = 8`
  chưa từng binding trong production, nới tới 8 là bật một code path chưa
  ai chạy.
- Kết quả tool có bọc `<untrusted_tool_result>` do
  `registry.ToolEntry.reads_external` quyết, mặc định `True`. Tool đọc
  store khai `reads_external=False`.
- **Lớp bảo mật thứ năm là lớp mềm, và mềm là thiết kế.** `wrap_result` là lớp
  cứng, luôn chạy, không đổi. `untrusted.scan_for_threats` (2026-08-29) chỉ **gắn
  cờ**: mọi đường ra khỏi nó là một verdict, kể cả khi pattern nổ hay chạm trần
  0,25 s (→ `risk: "unknown"`, khác `"low"` — "đã nhìn, không thấy gì" và "không
  nhìn" là hai sự thật khác nhau). Quét ở **executor, đúng một lần mỗi kết quả**,
  **không** trên đường render: `shown_result` dựng lại mỗi lượt gọi LLM nên quét ở
  đó sẽ đọc lại một trang 20k ký tự tới năm lần cho một câu trả lời. Hai scope
  (`all` + `context`); scope `strict` của Hermes **loại có lý do** — nó bảo vệ agent
  ghi được filesystem, lane này không có tool nào như vậy. Cờ lưu trong
  `TurnToolCall.as_wire()` → `agent_message.content` JSONB, **không** cột mới,
  **không** migration. **Không bao giờ vào text gửi model** — một cảnh báo trong
  text là một câu model phải diễn giải, và đó chính là bề mặt injection đang tấn
  công. Đo trên corpus golden: **0 `risk: high` / 97 kết quả** trang thị trường
  lành; hiển thị trên rail **chưa bật** vì 0/97 không phân biệt "không kêu bậy"
  với "không kêu".
- **Context đo được theo tám layer, và tổng là hoá đơn.** `ConstructedContext.
  composition` (`ContextComposition`) chia mọi token của một request thành
  `system_core · domain_body · system_dynamic · history · user_intent ·
  attachments · tool_results · study_headlines`. `composition.total` **là**
  `estimated_tokens` theo cấu tạo, không phải một phép đo thứ hai có thể lệch:
  mỗi message tính đúng một lần, text cắt thành đoạn liền nhau phủ kín, làm tròn
  áp lên tiền tố cộng dồn. `loop._appended` là **một** danh sách trả cả message
  lẫn giá của nó, nên reservation và breakdown không thể lệch nhau. Đo trên
  corpus golden: `system_core` **53,3%** · `tool_results` **43,1%** — prune không
  chạm được cái lớn nhất, cache mới chạm được.
- **Model đọc `context_text`, trace giữ `result_text`.** `TurnToolCall.context_text`
  là bản chiếu gửi model; `None` nghĩa là hai bản giống nhau và mọi caller cũ nhận
  đúng chuỗi cũ. Nó **không bao giờ** lên wire (`as_wire` không mang nó), không vào
  `agent_message.content`, không vào SSE. Rung ba của thang trim ghi vào
  `context_text`, không vào `result_text` — bất biến của trace là "đúng thứ tool
  đã trả về".
- **Prune chủ động là trạng thái thang bắt đầu từ đó, không phải một rung của nó.**
  `messages.aged_results` biến kết quả cũ thành trace handle **trước** khi đo:
  `SELECTION_CALLS = 1` (`web_search` — prompt §5 đã nói snippet là chỉ dấu chọn
  trang, không phải bằng chứng) và `RESULT_CALLS = 2` (mọi tool khác). **Tuổi đếm
  từ lượt đọc đầu tiên**, nên `keep=1` nghĩa là *đã đọc một lần*, không bao giờ là
  "collapse trước khi ai đó nhìn" — một test giữ đúng luật này vì bản đầu đã sai
  nó. Đo: **−13,85%** constructed token, **0** URL mất (536/536 còn tới được trong
  text model đọc). Handle nói rõ nó là gì (`TRACE_HANDLE_PREFIX`) và không gợi ý
  một tool lấy lại — deployment này không có tool nào như vậy.
- **System message có ba block, xếp theo tần suất đổi.** `core` (giống nhau mọi
  Turn) → `domain_body` (giống nhau mọi Turn dưới một pack) → giá trị render cho
  Turn. Hai breakpoint chứ không một: core đổi khi sửa prompt, body đổi khi swap
  domain, và một breakpoint trên chuỗi ghép sẽ void core mỗi lần pack nhúc nhích.
  Body **không còn** là note dán đuôi và **không còn được reserve** — nó nằm trong
  transcript và `estimate_tokens` đo nó từ chuỗi thật sự gửi đi.
- **`cache_identity` là tên của cái đầu, không phải nút bấm cache.** Tính một lần
  mỗi Turn từ `cache_key(model, surface.identity_digest, pack.identity)`, đi trên
  `CompletionRequest.metadata` — **local, không lên wire**, vì route chưa được
  chứng minh đọc trường cache nào. Không mang user, thread, ngày, mode hay câu hỏi:
  một test khẳng định hai Turn khác nhau mọi thứ sinh **một** identity.
  `llm_prompt_cache_control_enabled` vẫn `False`; cache tự động của route **đã**
  đọc 50,1% prompt token đo trên 78 lượt gọi golden.
- **Nguồn hiển thị dedup theo phạm vi Turn, không theo call.** `_TurnState.
  shown_sources` + `messages.dedup_key` (bỏ fragment · `www.` · trailing slash ·
  tracking param · scheme). **Chuẩn hoá chỉ để so trùng — link lưu và click vẫn là
  link gốc**, vì bỏ một tham số site nào đó định tuyến theo sẽ biến link sống thành
  404. Phạm vi Turn là phép đo chứ không phải thẩm mỹ: **0/53** call search trả URL
  trùng trong cùng payload, còn **21/223** URL trùng giữa các call — dedup per-call
  là code không bao giờ chạy. Đo trên lượt golden cuối: nguồn/lượt tìm **5,13 →
  3,96** (−22,8%) ở `MAX_RESULTS = 5` không đổi, mà `distinct_domains` giữ nguyên
  19/20. Grader lấy **set** domain nên dedup **không thể** hạ số domain khác nhau.
- **Rung 2 của thang trim giữ danh sách URL của kết quả** (trần
  `COLLAPSED_RESULT_URLS = 5`), bỏ title và snippet. `url` của `fetch_url` và
  `query` của `web_search` **vốn đã sống** trong `arguments` — dựng lại chúng là
  trả tiền hai lần cho một sự thật. Thứ thật sự mất là URL của **kết quả**, và đó
  là thứ một khẳng định trỏ vào.
- **Signal Desk đi hai đường, và từ 2026-08-30 là cùng MỘT đường ống.**
  `run_study` chạy một công thức có tên; `query`/`compute`/`get_series` +
  `render_signal_desk` cho câu hỏi chưa có công thức. Khác nhau ở chỗ ai soạn
  kế hoạch, không ở chỗ nó chạy bằng gì: một **template** (`src/studies/
  templates/*`) là một `plan` các bước + một `board` viết sẵn theo tên bước, và
  nó đọc bằng đúng `query.read_source` model đọc, tính bằng đúng sandbox +
  validator model tính, vẽ bằng đúng `composer.compile_board` model vẽ. Một
  bước = một artifact addressable (`"<artifactId>#<step>"`), nên model chạy
  template xong vẫn trộn lại được một frame của nó vào board của chính mình —
  `run_study` trả `frames` là bản đồ tên-bước → id. Cả hai đường trả model **id
  + tóm tắt**, không bao giờ trả `frames` (theo nghĩa số); loop phát
  `signal_desk.ready` từ payload qua `messages.signal_desk_of`. Frame chỉ vẽ
  được bởi chính Turn tạo ra nó (`studies/frames_buffer.py`).
- **Một board template sai luật là bug, không phải câu trả lời.** Board của
  model sai thì được một lượt sửa rồi tới lưới auto-compose; board của template
  đã viết tay, đã review, nên `runner._draw` **raise** — và lượt chạy phát hiện
  ra nó là một lượt chạy test. Cùng lẽ đó, `registry` chạy validator literal lên
  `ComputeStep.code` **lúc import**: một template gõ một con số thị trường không
  import được.
- **"Chạy" và "trả về số" là hai việc.** `agent_tool_call.status` là `ok`
  cho ba loại: có số · `no_value:<signal issue>` · `cannot_read`.
  Cột `outcome` là chỗ duy nhất phân biệt. Vốn từ ở
  `agent/messages.py::outcome_of`.
- **Sàn percentile là hàm mẫu**: `signals/fields.py::min_sample_for`
  = `max(ceil(0.6 × mẫu), 15)`.
- **Registry có 33 Signal Field** (30 + ba `earnings.*` từ 2026-08-29). Đo thật
  trên store: VCB **25 phục vụ / 8 từ chối**, VNM và MWG **26/7**. Tám refusal của
  VCB đúng như khai: 3 × `market_cap_absent` · 3 × `foreign_flow_not_stored` ·
  1 × `unavailable` (`beta_vs_market_index`, estimator chưa viết) · 1 ×
  `statement_line_missing` (`gross_profit_trend` — VCB là ngân hàng, không khai
  dòng lãi gộp).
- **Mỗi field khai `projection`**, và nó quyết cửa sổ bị enforce theo contract
  nào. `BarProjection.PRICE` gánh luật basis + band; `VOLUME` không. Field không
  làm số học trên giá phải khai `VOLUME`, nếu không nó thừa hưởng refusal của giá.
- **Luật basis, viết ra ở hai chỗ, cùng một câu.** Cửa sổ toàn
  `adjusted_at_source` **được phục vụ** (máy `_factors` tắt); trộn hai basis vẫn
  `mixed_price_basis`. Cổng cửa sổ ở `bars.py::_basis_of`; cổng **per-phiên** ở
  `price_band.py::_basis_of_the_pair`. Cổng thứ hai từng từ chối im lặng mọi phiên
  — nó đặt `INDETERMINATE`, thứ `Bar.limit_locked` đọc là *không khoá*, nên
  `without_limit_locks()` không loại gì và baseline volatility tính trên cửa sổ
  còn nguyên phiên trần. Test phải nhắm vào **hệ quả** (`limit_lock_days`), không
  vào mã refusal.
- **Band quyết theo giá, không theo nhãn.** `price_band.py::_off_tick_grid`: giá
  sàn công bố **luôn** nằm trên lưới bước giá (HOSE 10/50/100 theo mức), nên giá
  lệch lưới là giá đã bị rebase → `price_off_tick_grid`. **Điều kiện cần, không
  đủ** — giá rebase vẫn có thể tình cờ rơi đúng lưới. Đo: HOSE 91,52% phiên quyết
  được · HNX 89,33% · **UPCOM 0% vĩnh viễn** (neo là VWAP phiên trước, `bar_daily`
  không có VWAP). Tập 30 mã declared: **80,71%**.
- **`traded_value` là số suy diễn, khai rõ là suy diễn.** `bar_daily` không có cột
  giá trị giao dịch, nên `signals/sessions.py::_traded_value` suy
  `close × volume` — **một chỗ duy nhất**, vì hai tầng cùng đọc: `Bar` và
  `SessionSnapshot` (`_adtv_standing` → `WindowHealth.adtv` → `adtv_percentile`).
  `volume == 0` → **`None`, không bao giờ `0.0`**: `average_over_sessions` từ chối
  cửa sổ có `None` nhưng cộng thẳng `0.0`, nên trả 0 sẽ tắt câm chính refusal dựng
  ra để bắt việc đó. Sai số so nguồn cũ (60 phiên): median 0,86% · p95 20,4%. Trên
  5 năm thì p95 56,7% — **toàn bộ** là close đã điều chỉnh vs tiền danh nghĩa
  (khối lượng hai nguồn khớp median 0,000% mọi năm), nên đừng dùng nó so tiền giao
  dịch giữa các năm.
- **`min_sessions` là sàn lịch sử, `lookback_sessions` là cửa sổ đọc** —
  `SignalField.window_sessions` giải hai cái.
- **Mã refusal phải trỏ đúng input thiếu.** `_quarterly_ratio` chia ba
  nguyên nhân: `fundamental_not_stored` · `statement_line_missing` ·
  `market_cap_absent`. Thêm mã thì thêm câu ở **cả** `alpha/reasons.py`
  và `apps/web/src/lib/signal-issues.ts`.
- `check_price_claim` kiểm giá nguồn ngoài: bước giá · biên độ · bar
  trong store. Trạng thái thứ tư `unverified` **không phải** "hợp lệ".
  Fail-open, không chặn câu trả lời. **Cả ba nhánh sống** — nhánh BAND từng chết
  vĩnh viễn (cổng cũ đòi phiên neo có basis `RAW`, mà sau khi lịch sang
  `bar_daily` thì không còn dòng `RAW` nào), sửa 2026-08-29 bằng **hai cổng
  giá** thay cổng nhãn: `price_band.off_tick_grid(exchange, anchor)` — giá sàn
  công bố luôn trên lưới bước giá — **và** `_rescaled_since` (ex-date giữa phiên
  neo và phiên đích). Không dùng cổng thứ hai một mình: bảng corporate action phủ
  một phần nhỏ thị trường nên "không có dòng" đọc thành "không có ex-date". Đo
  trên store thật: 30/30 mã declared `within_band` cho giá đúng, `exceeds_band`
  cho giá bịa ±9%/±12%/×10.
- Ngân sách LLM: envelope $45/tháng chia ba lane 10 Analysis / 30 Turn /
  5 emergency. Analysis lane đã bỏ (rip-out) — envelope chưa reweight,
  ledger vẫn ghi. Đặt cả bốn giá trị về `0` cho route thuê bao.
- Web: sản phẩm là **một màn hình duy nhất** ở `/` — shell 2 vùng chính ở
  `src/components/shell/` (sidebar + cột chat). Inspector có đúng hai tab:
  Nguồn và Signal Desk. Chỉ `(auth)` là trang riêng.
- Widget Signal Desk có **name + version**; FE giữ registry ở
  `components/signal-desk/widget-registry.ts` và test khớp nó với
  `contracts/signal-desk-widget-catalog.json`. Không vẽ được → `data_table` kèm ghi
  chú, không bao giờ khối trắng. Panel Signal Desk nạp qua `next/dynamic` để
  recharts không nằm trên đường first paint của lane chat.

# Definition of done

1. `make test` tại `apps/api` pass
2. `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại
   `apps/web` pass
3. Phần nào không chạy được thì nêu rõ, đừng ẩn lỗi
4. Không thêm dependency mới nếu chưa hỏi

## Agent skills

### Issue tracker

Issue sống ở GitHub Issues của `PhamTy2002z/Stock_Massive`, thao tác qua `gh`
CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Năm nhãn canonical, giữ nguyên tên mặc định (`needs-triage`, `needs-info`,
`ready-for-agent`, `ready-for-human`, `wontfix`). See
`docs/agents/triage-labels.md`.

### Domain docs

Single-context: một `CONTEXT.md` + `docs/adr/` ở gốc repo — chưa tồn tại, tạo
lazily khi có thuật ngữ hoặc quyết định thật sự cần chốt. See
`docs/agents/domain.md`.

# Không còn tồn tại

**2026-08-29 (retire FiinQuant — plan `260828-2126-price-basis-and-signal-field-spine`):**
- **71.773 dòng `provider_snapshots` `source='fiinquant'`** đã xoá khỏi DB
  container qua alembic revision `a3f7e21b8d54` (36.528 `market` + 35.245
  `valuation`). Revision có cổng: đếm không khớp `{market: 36528, valuation:
  35245}` thì raise và bỏ transaction; `downgrade` raise `NotImplementedError`.
  Còn lại 34.234 dòng, toàn bộ `vnstock` (fundamental 2.854 · market 31.160 ·
  reference 220). Backup: `backups/pre-retire-fiinquant-260829.sql.gz` (toàn DB)
  + `backups/pre-retire-fiinquant-provider-snapshots-260829.sql.gz` (theo bảng,
  đã restore thử và đếm khớp 106.007/71.773). **Không lấy lại được** — licence
  không cho phân phối lại.
- **`ProviderSource.FIINQUANT`** đã gỡ khỏi enum
  (`stocks/providers/contracts.py`). Giờ `ProviderSource("fiinquant")` **raise** —
  đó là mục đích: một dòng ghi dưới tên đó fail ở biên chứ không đọc lại được.
  Thứ tự bắt buộc: **xoá dòng trước, gỡ enum sau**; đảo lại thì mọi dòng còn sống
  thành không đọc được.
- **Bản đồ ownership còn một nguồn:** `MARKET`, `VALUATION`, `MARKET_INDEX` đều
  `main=VNSTOCK`, **không còn `cover`**. Bỏ `cover` chứ không chỉ đổi `main` —
  `validate_distinct_sources` raise lúc import khi `cover is main`.
- **`MARKET_INDEX` đảo quyết định cũ** (`contracts.py:172-179` cũ): vnstock giờ
  là main. Dòng index mang `adjusted_at_source`, đọc là "không có phép điều chỉnh
  nào cần làm" — an toàn vì nhất trí một basis một source. Lý do đảo ghi tại chỗ,
  giữ nguyên văn lý lẽ cũ.
- **Vẫn giữ, có lý do:** `MarketDataSource.FIINQUANT` trong `realtime/
  {contracts,policy}.py` — enum **song song**, không phải `ProviderSource`, không
  reader sống cho member đó. Gỡ nó kéo theo viết lại `SOURCE_OWNERSHIP` của
  `realtime/policy.py`, tức sửa logic trong module vẫn **freeze**. Ba docstring
  nhắc tên cũ cũng giữ: `providers/normalize.py` (surface freeze),
  `providers/__init__.py` (câu đúng về quá khứ), `providers/contracts.py` (giải
  thích chính việc gỡ).
- **31.160 dòng `vnstock`/`market` (2016-2021) giữ nguyên** — không ai đọc sau khi
  signals sang `bar_daily`, nhưng không vi phạm gì.

**2026-08-26 (Phase 0 cleanup):**
- **Empty stocks shells** (không track, dọn khỏi disk): `apps/api/src/
  stocks/{analytics,company,financial,market,monitor,news,price,trading}`
  + `apps/api/src/stocks/realtime/dnse`. Còn lại trong `stocks/`:
  `providers`, `realtime`, `signals`, `schemas`, `shared`, `models.py`,
  `universe.py`, `trading_day.py`, `listing_roster.py`.
- **Signal module mồ côi:** `stocks/signals/nulls.py` + test kèm.
  11 module `corporate_actions` · `cross_sectional` · `foreign_flow` ·
  `foreign_share_flow` · `fundamentals` · `indicators` ·
  `market_behavior` · `moments` · `reference` · `risk` · `volatility`
  **giữ nguyên** — reverse-import từ registry / serving / test.
- **Config settings mồ côi khỏi `src/core/config.py`:** `fiinquant_*`,
  `dnse_*`, `realtime_ingestion_enabled`, `realtime_queue_size`,
  `realtime_worker_count`, `realtime_shutdown_timeout_seconds`,
  `realtime_boards`, `_complete_realtime_configuration`, `backfill_*`,
  `warmup_window_trading_days`, `alpha_desk_suggestions_enabled`,
  intraday collector / profit census / cohort / collector /
  corporate-action job / market-index / catch-up / Analysis dispatcher /
  sector-historical job settings, `git_sha` (Evidence Manifest). **Giữ:**
  `alpha_desk_enabled` — `core/llm/config.py` + capability enforcement +
  test vẫn đọc.
- **Bảng DB đã drop qua alembic revision mới** (upgrade path;
  downgrade raise `NotImplementedError` — restore từ backup):
  `analysis_tool_call`, `analysis_run`, `watchlist_entries`, `analysis`,
  `cohort_members`, `cohort_versions`, `profit_ranking_census_runs`,
  `symbol_backfills`, `stock_intraday_bars`, `stock_daily_ohlcv`.
  **Giữ:** `realtime_events`, `realtime_checkpoints`, `realtime_spills`,
  `realtime_health`, `realtime_reconciliation_audits` —
  `stocks/realtime/storage.py` và `signals/foreign_share_flow.py` vẫn đọc.
- **Stub Phase 1 domain pack:** `apps/api/plans/260826-1909-phase-1-
  domain-pack/` + `apps/api/src/agent/domain/` (không có importer).
  Hoãn Phase 1 chờ quyết brief Signal Desk (`docs/Text.txt`).

**2026-08-25 (rip-out harness-first):**
- **Web UI:** `view-board`, `view-news`, `view-new`, `watchlist-section`,
  `components/market-monitor/*`, `components/alpha/analysis/*`,
  `news-sources`, `hooks/use-{price-board,market-monitor,market-indices,
  vn30-overview,sector-performance,price-history,news,analysis,watchlist-
  rail}`, `lib/market-monitor/*`, `query-keys.stock*` (tất cả trừ auth +
  threads). Inspector chỉ còn panel Sources.
- **API routers:** `stocks_router`, `jobs_router`, `realtime_router`,
  `watchlist_router`, `analysis_router`, `alpha_desk_router`,
  `loop_ops_router`, `stocks/signals/router`. Endpoint duy nhất còn:
  `auth`, `agent` (alpha desk service router), `message_flag`,
  `favicons`, health.
- **API modules:** `stocks/{monitor,realtime{ingress+coordinator+spine
  +projections+dnse+aggregation+bar_projection+metric_projection+metrics
  +service+normalization+router+reconciliation*},price,market,news,
  analytics,financial,company,trading}`, `stocks/{backfill,collector*,
  intraday_collector,corporate_action_collector,warmup,session_window,
  series_view,census,cohort,snapshot_router,jobs*,listing_roster(full),
  market_index,service,router}`, `alpha/{analysis_loop,analysis_reads,
  analysis_router,analysis_run,dispatcher,generation,jobs,loop_ops_router,
  naming,nightly,on_demand,producer(full),production,router,watchlist}`,
  `stocks/providers/{cafef_article,cafef_rss,fiinquant,store(full),
  vnstock_provider}`, `stocks/signals/{router,volume_spike,position_
  sizing}`, `src/eval/*`.
- **Tests:** ~140 test file cho code đã xoá.
- Vẫn giữ 30 mã Universe declared, không còn cohort seating.

**2026-08-22 (đã ghi trước đó):**
- Eval Battery / Eval Gate / Eval Report: `src/eval/*` (đã rip lại lần
  này), biến `EVAL_*`, bảng `eval_run`, lane ngân sách eval. Chữ `eval`
  còn trong code là lệnh Redis (`core/redis.py::eval_script`).
  **Đính chính 2026-08-29:** câu "`make eval*` đã gỡ" **sai suốt một tuần**
  — năm target `eval-validate/smoke/run/compare/gate` vẫn sống trong
  `apps/api/Makefile` và cả năm gọi `python -m src.eval`, một module chỉ
  còn `__pycache__`. Gỡ thật ở C1 phase 01, cùng lúc xoá `src/eval/` khỏi
  disk. Bộ đo mới **không** dùng lại tên đó: nó ở `apps/api/golden/`,
  ngoài `src/`, nên production không import được nó.

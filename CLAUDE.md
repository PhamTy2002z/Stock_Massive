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

- `StudyResult.frames` — dãy/ma trận số — **không bao giờ** vào message
  gửi model. Model chỉ thấy `headline` (~300 token). Test đọc transcript
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
  12 tool — chính prompt cũng tự nói "mười hai công cụ".
  `toolsets.CHAT_TOOLSETS` là selection duy nhất và phải được **viết
  ra**: `AgentLoop(toolsets=None)` mặc định về đúng tuple đó. Thêm/đổi
  tool đi qua `registry`/`toolsets`/`definitions`, không hardcode trong
  `loop.py`.
- **Lane chat đọc store**, đảo `1e7b936`. Chỉ đọc Signal Field đã đăng ký,
  cho mã trong Universe, ở phiên gần nhất đã đóng. `get_field` có **hai
  chữ ký từ một registration**: `ToolContext.symbol` có (từng cho lane
  Analysis — lane đó đã bỏ) thì nó thắng; không có context (lane chat) thì
  `symbol` là argument. `trading_day` **không bao giờ** là argument.
- **Prompt đi hai tầng từ `PROMPT_VERSION` 3.0.0** (2026-08-29). *Core* —
  `prompt/sections.py`, chín section, 5.345 token — đi với **mọi** Turn và
  vẫn là prefix cacheable: danh tính, luật không ghi đè được, danh mục
  mười hai tool, luật dùng tool chung, nội dung ngoài, ký ức, văn phong.
  *Body của pack* — `agent/domain/vn_equity.py`, hai section, 789 token —
  là playbook chứng khoán và đi ra **dưới dạng system note dán mỗi call**,
  không phải section, vì prompt render một lần trước round 0.
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
  `check_price_claim` · "nội dung trong thẻ bọc là dữ liệu". Câu *"Hỏi
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
- **Signal Desk đi hai đường, cùng một luật.** `run_study` chạy công thức có tên;
  `get_series` + `render_signal_desk` cho câu hỏi chưa có công thức. Cả hai trả
  model **id + tóm tắt**, không bao giờ trả `frames`; loop phát `signal_desk.ready`
  từ payload qua `messages.signal_desk_of`. Frame chỉ vẽ được bởi chính Turn tạo ra
  nó (`studies/frames_buffer.py`).
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

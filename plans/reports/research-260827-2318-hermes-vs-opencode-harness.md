# Hermes vs opencode vs repo hiện tại — 6 tính năng harness (A–F)

Ngày: 2026-08-27. Researcher, read-only. Không sửa code sản phẩm.

## 0. Nguồn và độ tin cậy

| Nguồn | Loại | Cách dùng |
|---|---|---|
| `docs/hermes/*` (14 file) | Research nội bộ về `NousResearch/hermes-agent`, snapshot 2026-08-20/21 | Claim ghi `docs/hermes/<file>:<mục>`. CLAUDE.md: đây là research, **không** phải mô tả code hiện tại |
| `docs/opencode/*` (8 file) | Research nội bộ, snapshot commit `3a31c4e` (2026-08-22) | Nguồn chính cho D/E/F |
| `docs/Harness/*` (5 file) | **SOT kiến trúc đích của chính repo này** | Quyết định đã chốt, xem §7 |
| Source opencode nhánh `dev`, đọc trực tiếp hôm nay | Primary | Nguồn duy nhất cho B (share) và C (catalog shape) — hai vùng docs nội bộ không trích |
| `apps/api/src/agent/*`, `apps/web/src/*` | Code thật | Cột "repo hiện tại" |

**Ba cảnh báo về nguồn, phải đọc trước khi dựa vào báo cáo này:**

1. **`sst/opencode` đã đổi owner thành `anomalyco/opencode`.** Mọi URL `github.com/sst/opencode` redirect. Cây repo ngày 2026-08-27 đã khác snapshot `3a31c4e` mà `docs/opencode/` cố định: có thêm `packages/{protocol,session-ui,identity,enterprise,sdk-next}`, và `packages/schema/` giờ là owner của event/session/model schema (trước nằm trong `packages/opencode/src/session/`). Khi báo cáo này trích source, nó trích **nhánh `dev` hôm nay**, không phải `3a31c4e` — hai bên có thể lệch.
2. **`docs/Harness/README.md` đã stale ở phần link.** Nó trỏ `docs/harness-roadmap.md`, `docs/system-roadmap.md` và `apps/api/src/eval/cli.py` — cả ba **không còn tồn tại** (`docs/` chỉ còn `Harness/ hermes/ opencode/ research/ idea.md text.md`; `src/eval/` chỉ còn `__pycache__`; `apps/api/eval/` còn data nhưng không có runner). Nội dung authority về kiến trúc trong `target-architecture.md` vẫn dùng được; phần measurement authority và roadmap thì không.
3. `docs/Harness/` được viết 2026-08-23/25, **trước** pivot harness-first (2026-08-25) và trước quyết định canvas dynamic (2026-08-26). Nó vẫn nói về `alpha/analysis_loop.py` (đã rip).

---

## 1. A — Session/thread model

### Bảng so sánh

| Chiều | Hermes | opencode | Repo hiện tại |
|---|---|---|---|
| Title tự sinh | **2 tầng.** Stage 1 derived: dòng đầu message user đã lột scaffolding (`<command-*>`, `<system-reminder>`, compaction-handoff), cắt 48 ký tự tại word-boundary, inline, đồng bộ, 0 chi phí, không thể fail. Stage 2 upgrade: background daemon thread, model rẻ, `thinking` tắt, JSON schema strict `{"title": "..."}`, guard title >12 từ bị từ chối. Precedence `derived < llm < user` enforce ở **storage layer** (`set_auto_title` transaction), không ở call site. Lý do tách 2 tầng: đo được p50 151s / p90 1212s nếu chờ assistant trả lời xong — quá chậm cho UI cần tên ngay (`docs/hermes/hermes-turn-lifecycle-260820-2352.md`:§2.10) | Một agent nội bộ tên `title` (cùng họ với `compaction`, `summary`), prompt ở [`agent/prompt/title.txt`](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/agent/prompt/title.txt): "output ONLY a thread title", ≤50 ký tự, một dòng, **phải cùng ngôn ngữ với message user**, cấm tên tool trong title, cấm "DO NOT SAY YOU CANNOT GENERATE A TITLE". Không có tầng derived. `title: Schema.String` là **non-nullable** trong [`SessionV2.Info`](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/session.ts) | **Không có.** `AgentThread.title` nullable, chỉ được ghi bởi `PATCH /threads/{id}` (rename từ menu sidebar) — `apps/api/src/agent/router.py:262-288`. `docs/hermes/hermes-turn-lifecycle-260820-2352.md`:§4.4 xác nhận: *"Dự án chưa có title generator"* |
| Metadata | Session lineage 4 loại (branch/reset/compression/ephemeral) qua SQL heuristic; `last_activity_at`, `last_activity_description`, `last_activity_provenance` | `SessionV2.Info`: `id, parentID?, projectID, agent?, model?, cost, tokens{input,output,reasoning,cache{read,write}}, time{created,updated,archived?}, title, location, subpath?, revert?`. **Cost/token tổng nằm trên session row**, không phải chỉ trên turn | `agent_thread`: `id, user_id, title?, symbols[] (ARRAY(String(20)), GIN index), pinned_at?, created_at, updated_at` + `ix_agent_thread_user_updated (user_id, updated_at DESC)` — `apps/api/src/alpha/models.py:35-61`. **`symbols[]` là tag/ticker mà brief hỏi — đã có sẵn.** `pinned_at` là timestamp không phải boolean, có comment giải thích: boolean sẽ sort mọi thread pinned theo `updated_at` và đẩy cái pin đầu tiên xuống cuối |
| Nhóm theo recency | không (CLI) | `GET /session?scope=project&path=&roots=&start=&search=&limit=` — `roots` lọc chỉ session gốc (bỏ child), `start` là anchor thời gian, có `Session.ListAnchor {id, time, direction: previous|next}` cho cursor 2 chiều | Backend trả pinned-group trước, mỗi group theo last-touched; FE **partition chứ không re-sort**: `apps/web/src/components/shell/sidebar.tsx:162-178`. Chưa nhóm theo "Hôm nay / 7 ngày / Cũ hơn" |
| Soft-delete + undo | Compaction in-place **soft-archive** message thay vì xoá thẳng; curator có `.archive/` phục hồi qua `hermes curator restore`; *"rollback itself is undoable"* (`docs/hermes/hermes-memory-260820-2352.md`:191,197). Export/import có bất đối xứng chủ đích: export giữ field "đang sống", import **reset** `last_activity_*` vì phục hồi nhãn "đang hoạt động" trên máy không có agent nào chạy là **giả tạo activity** làm watchdog đọc sai (#76354, `docs/hermes/hermes-orchestrator-state-260820-2352.md`:178,210) | **`time.archived` timestamp trên chính session row**, set/clear qua **cùng một** `PATCH /session/:sessionID` (`UpdatePayload.time.archived`, [groups/session.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/server/routes/instance/httpapi/groups/session.ts#L49-L58) → `session.setArchived`, [handlers/session.ts:200](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/server/routes/instance/httpapi/handlers/session.ts#L200)). `DELETE /session/:sessionID` là hard delete, tách hẳn. Client archive = 1 PATCH rồi bỏ khỏi list cục bộ ([home-session-archive.ts](https://github.com/anomalyco/opencode/blob/dev/packages/app/src/pages/home-session-archive.ts)) | **Không có.** `DELETE /threads/{id}` là hard delete cascade, docstring viết thẳng: *"It is not reversible and there is no archive: the menu asks the user to confirm"* (`apps/api/src/agent/router.py:291-311`) |

### Khuyến nghị A — bám opencode cho archive, bám Hermes cho title

Xếp hạng:

1. **Soft-delete: bám opencode.** Thêm `archived_at` nullable vào `agent_thread`, set/clear qua **PATCH đã có** (`UpdateThreadRequest` đã dùng `model_fields_set` để phân biệt "không gửi" với "gửi null" — cơ chế cần cho undo đã sẵn). `DELETE` giữ nguyên là hard delete. Lý do chọn opencode chứ không Hermes: Hermes soft-archive nằm ở tầng *message/memory* cho mục đích compaction và curator, không phải tầng session cho mục đích UX undo; port nó vào là port sai tầng. Cơ chế opencode nhỏ hơn nhiều (1 cột + 1 nhánh trong PATCH đã tồn tại) và list query chỉ cần thêm `WHERE archived_at IS NULL`.
2. **Title: bám Hermes 2 tầng, không bám opencode 1 tầng.** Con số p50 151s / p90 1212s (`hermes-turn-lifecycle`:§2.10) là bằng chứng đo được rằng title chỉ-LLM để UI trắng tên quá lâu. opencode chấp nhận được vì TUI local; một web client có sidebar thì không. Lấy **prompt** của opencode (ràng buộc "cùng ngôn ngữ với user" là thứ Hermes không có và repo **cần** — lane chat là tiếng Việt) ghép với **kiến trúc 2 tầng** của Hermes. Precedence `derived < llm < user` phải enforce trong `persistence.py` bằng check-and-set trong một transaction, không ở call site — đây là điểm Hermes nói rõ và là chỗ dễ làm sai nhất.
3. **Nhóm recency: giữ nguyên nguyên tắc của repo, thêm group thứ ba.** FE "partition chứ không re-sort" đã đúng và tốt hơn opencode (opencode để client tự sort). Chỉ mở rộng partition từ 2 group (pinned/rest) thành pinned + các bucket ngày. Không cần cursor `ListAnchor` 2 chiều của opencode ở quy mô hiện tại.

**Rủi ro adoption:** thấp cho cả ba. Điểm cần cẩn thận duy nhất: stage 2 title tiêu một lời gọi model — `docs/hermes/hermes-synthesis-260821-0030.md`:§Câu hỏi chưa giải quyết #5 đã đặt đúng câu hỏi này cho nudge ("trần theo số lần hay theo tiền?") và envelope $45/tháng chưa reweight sau khi bỏ Analysis lane. Đặt trần theo tiền, và stage 2 phải fire-and-forget: fail thì thread giữ tên stage 1, không bao giờ hỏng.

**Không port:** session lineage 4 loại và export/import của Hermes — `docs/hermes/hermes-orchestrator-state-260820-2352.md`:241-242 đã kết luận là over-engineering ngược YAGNI cho model "freeze, never resume" + Postgres multi-tenant.

---

## 2. B — Share thread qua public link

Đây là mục **không** có trong `docs/hermes/` lẫn `docs/opencode/`. Toàn bộ dưới đây đọc trực tiếp từ source nhánh `dev`.

### opencode làm thế nào

**Ai giữ dữ liệu:** server local giữ truth; **một service ngoài giữ bản mirror**. Mặc định `https://opncd.ai`; nếu account có `active_org_id` thì đổi sang console URL của org với `Authorization: Bearer <token>` + `x-org-id`. Hai họ endpoint tách biệt: `/api/share/*` (legacy, không auth) và `/api/shares/*` (console, có auth) — [share-next.ts:84-100, 195-215](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/share/share-next.ts).

**Credential model:** bảng local `session_share {session_id PK, id, secret, url}` ([core/share/sql.ts](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/share/sql.ts)). `create` POST `{sessionID}` → nhận `{id, url, secret}`. **`secret` chỉ gate ghi/xoá** (gửi trong body của `sync` và `remove`), không gate đọc. Link công khai đọc được bởi bất kỳ ai — docs nói thẳng: *"Shared conversations are publicly accessible to anyone with the link"* ([share.mdx](https://github.com/anomalyco/opencode/blob/dev/packages/web/src/content/docs/share.mdx)).

**Snapshot hay live sync: LIVE, không snapshot.** `create` chạy `full(sessionID)` đẩy toàn bộ (session info + mọi message + mọi part + `session_diff` + models đã dùng), rồi từ đó **subscribe event bus** và đẩy delta liên tục. Bốn event được watch, cộng một event xoá:

| Event | Đẩy lên share |
|---|---|
| `Session.Event.Updated` | `{type:"session"}` |
| `MessageV2.Event.Updated` | `{type:"message"}`; nếu `role === "user"` thì **kèm** `{type:"model"}` (resolve `provider.getModel`) |
| `MessageV2.Event.PartUpdated` | `{type:"part"}` |
| `Session.Event.Diff` | `{type:"session_diff"}` |
| `Session.Event.Deleted` | gọi `remove()` — **xoá share tự động khi session bị xoá** |

**Coalescing (chi tiết đáng port nhất):** queue là `Map<SessionID, Map<key, Data>>` với `key(item)` = `"session"` / `"message/{id}"` / `"part/{messageID}/{id}"` / `"session_diff"` / `"model"`, flush sau `Effect.delay(1000)`. Nghĩa là **last-write-wins theo key, debounce 1 giây**: một part đang stream delta liên tục chỉ tốn một POST mỗi giây với giá trị mới nhất, không phải một POST mỗi delta. Flush fail chỉ `logWarning`, không phá turn.

**Revoke/unshare:** `DELETE /api/share/{shareID}` với `{secret}` trong body, rồi xoá row local, xoá cache + queue. Docs: *"remove the share link and delete the data related to the conversation"*. Không có TTL, không có expiry — *"Shared conversations remain accessible until you explicitly unshare them"*.

**Ba chế độ + hai kill switch:** config `share: "manual" | "auto" | "disabled"`. `disabled` → `share()` throw ngay ở [share/session.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/share/session.ts). Env `OPENCODE_DISABLE_SHARE=true|1` là kill switch tầng thấp hơn: mọi hàm trong `share-next.ts` return sớm. `auto` chỉ áp cho session gốc — `if (result.parentID) return result`: **child session không bao giờ tự share**. Docs khuyên commit `"share": "disabled"` vào `opencode.json` của project để enforce cho cả team.

### Bảng so sánh

| Chiều | Hermes | opencode | Repo hiện tại |
|---|---|---|---|
| Public link | không có | có, `opncd.ai/s/<share-id>`, không auth để đọc | không có |
| Cơ chế | `trace_upload.py` export transcript đầy đủ lên HuggingFace Hub, **private-by-default, redact bắt buộc**, không có `--no-redact` bỏ qua được kiểm tra thất bại (raise `TraceRedactionError`); `hermes_state_portability.py` export/import JSONL để backup (`docs/hermes/hermes-mcp-ops-eval-260820-2352.md`:74; `hermes-orchestrator-state-260820-2352.md`:178) | live sync push tới service ngoài | — |
| Redaction trước khi ra ngoài | **có, fail-CLOSED.** `redact_for_export()` 2 lớp: secret trước (regex Bearer/`sk-`/`gh_`/`xox-`, redactor lỗi → trả `[redaction-unavailable]`, **không bao giờ** export raw), rồi PII (email/phone/UUID). Cộng cap 500 ký tự ở `_span_attrs` làm defense-in-depth (`docs/hermes/hermes-mcp-ops-eval-260820-2352.md`:58) | **không có bất kỳ lớp nào.** `structuredClone(info)` rồi POST | — |
| Xoá | `import_sessions` reset field "đang sống"; curator `.archive/` restore được | DELETE + secret; auto-remove khi session deleted | — |

### Khuyến nghị B — bám opencode cho *kiến trúc link*, bám Hermes cho *cổng dữ liệu ra ngoài*. Ba thay đổi bắt buộc.

Xếp hạng, và đây là mục duy nhất tôi khuyến nghị **không** copy nguyên hình dạng nguồn:

1. **Giữ dữ liệu trong repo, không đẩy sang service ngoài.** opencode phải push vì server của nó chạy trên máy user, không có URL công khai. FastAPI của repo **đã** là server có URL — thêm một hop mirror là thêm một bản copy dữ liệu tài chính của user ở nơi thứ hai, không đổi lấy gì. Cụ thể: bảng `agent_thread_share {thread_id PK → agent_thread.id CASCADE, token (unique, random ≥128-bit), created_at, revoked_at?}` + route công khai `GET /public/threads/{token}` không đi qua `CurrentUser`. Cấu trúc bảng lấy của opencode (khoá theo `session_id`, không phải bảng nhiều-dòng-một-session → share lại là idempotent `onConflictDoUpdate`), bỏ cột `secret` vì không có service ngoài nào cần credential ghi.
2. **Snapshot, không live sync.** Đây là chỗ repo có lợi thế kiến trúc mà opencode không có: `as_of` đã đóng băng lúc tạo artifact và *"mở lại thread là render lại artifact, không tính lại"* (CLAUDE.md §Đã chốt 2026-08-26). Một share live sync sẽ tiếp tục đẩy các Turn mới vào link đã gửi cho người khác — người dùng share một câu trả lời rồi hỏi tiếp câu riêng tư, và câu đó tự động công khai. Đó là lỗi bảo mật, không phải tính năng. Share **đóng băng tại `message_id` cuối cùng lúc bấm share**; muốn cập nhật thì bấm lại (ghi lại `token` mới hoặc dời con trỏ — quyết định của product, xem câu hỏi mở #2).
3. **Cổng redaction fail-closed trước khi trả public payload — bám Hermes.** Đây là lớp opencode **hoàn toàn không có** và là khoảng trống lớn nhất nếu copy nó. Repo có ba loại nội dung không được ra link công khai mà opencode không có tương đương: (a) `RuntimeContext.user_name` — CLAUDE.md ghi đây là *"the only user-supplied string that reaches the system prompt"* và nó nằm trong transcript; (b) tool result bọc `<untrusted_tool_result>` với nội dung web nguyên văn; (c) `StudyResult.frames`. Với (c) luật đã có sẵn và phải giữ: frames không vào message, share chỉ render lại artifact qua widget registry. Với (a)/(b): một hàm chiếu duy nhất `public_view(thread) -> PublicThread` **whitelist** field, theo đúng khuôn `TOOL_CALL_FIELDS` mà `events.py` đã dùng (allowlist, không blocklist) — và fail-closed: chiếu lỗi thì 500, không bao giờ trả payload chưa chiếu.

Cộng ba thứ nhỏ lấy trực tiếp từ opencode vì chúng đúng và rẻ:
- **Kill switch hai tầng**: một setting (`share_enabled`) + khả năng tắt cứng. opencode có cả config lẫn env vì config có thể bị sửa; giữ nguyên ý đó.
- **Không share thread có parent** — repo chưa có child thread, nhưng viết luật này ngay lúc thêm cột thì rẻ hơn sửa sau.
- **Revoke làm mất hiệu lực ngay** (`revoked_at`, không xoá row — giữ lại để trả lời "link này từng tồn tại"). Và cascade: thread bị hard delete → share biến mất (opencode làm qua `Session.Event.Deleted` → `remove()`; ở Postgres thì `ON DELETE CASCADE` là đủ, không cần event).

**Rủi ro adoption:** trung bình. Không phải rủi ro kỹ thuật mà là rủi ro phạm vi: route công khai đầu tiên của repo. Nó phải nằm ngoài `CurrentUser` nhưng vẫn trong rate limit, và không được nhận vào `symbols[]`/search index. Ngoài ra `docs/opencode/opencode-architecture.md`:§Điểm mạnh và giới hạn cảnh báo đúng chỗ: *"Server standalone chỉ an toàn khi cấu hình auth và network boundary đúng"*.

---

## 3. C — Model/provider selector thật

| Chiều | Hermes | opencode | Repo hiện tại |
|---|---|---|---|
| Catalog | `model_metadata.py`, **3607 dòng**, đa provider (OpenRouter, models.dev, Ollama). `docs/hermes/hermes-route-subagent-260820-2352.md`:562 kết luận **không port**: *"Stock_Massive chỉ có 2 model tên cố định qua Settings … không cần trùng lặp 1 catalog đa-provider"*. Và models.dev **sai context length cho một số model/custom → cần override** (#84482, #8731, `docs/hermes/hermes-context-260820-2352.md`:192) | Catalog dựng từ Models.dev rồi **merge** plugin + config + env credentials + stored auth + custom models + discovery, lọc `enabled/disabled/experimental/deprecated` (`docs/opencode/research-260823-opencode-primary-sources.md`:§10). Event `models-dev.refreshed` báo catalog đã đổi | 2 hằng: `llm_model_batch = "gpt-5.6-luna"`, `llm_model_session = "gpt-5.6-terra"` (`apps/api/src/core/config.py:80-81`). Không có selector, không có catalog, không expose ra UI |
| Shape một model | — | [`ModelV2.Info`](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/model.ts): `id, providerID, family?, name, api (tagged union aisdk\|native), capabilities{tools:bool, input[], output[]}, request{headers,body,variant?}, variants[], time{released}, cost[], status: "alpha"\|"beta"\|"deprecated"\|"active", enabled: bool, limit{context, input?, output}` | — |
| Cost/limit | `insights.py`: 3 bài học đáng port — breakdown per-model phải **cộng cả usage phụ** (vision/compression/**title**) nếu không tổng bị thiếu (#23270/#58592/#9979); model đổi giữa session qua `/model` phải phân bổ token/cost theo **từng** model đã dùng, không dồn cho model đầu (#51607); chi phí dưới 1 cent hiển thị `~$0.00` là **dishonest**, phải format 4 chữ số thập phân (#77223/#79220) — `docs/hermes/hermes-mcp-ops-eval-260820-2352.md`:198 | `cost` là **array** `Cost[]`, mỗi phần tử có `tier: {type:"context", size:int}?` → hỗ trợ giá bậc thang theo độ dài context. `limit.context` tách khỏi `limit.output`. Session row giữ `cost` + `tokens{input,output,reasoning,cache{read,write}}` tổng | Ledger LLM có ghi; envelope $45/tháng chia 3 lane (CLAUDE.md). Không hiển thị cost cho user |
| Per-session override | `/model` đổi giữa session | `Session.Info.model?: Model.Ref` + event durable `session.next.model.switched {messageID, model}` + `UserMessage.model` trên **từng message**. Nghĩa là: session giữ lựa chọn hiện tại, message giữ model thật đã chạy. Cộng `AgentSwitched` cho agent | không có |
| Expose cho UI | — | `GET /provider` → `Provider.ListResult`, client normalize thành `{all: Map, connected: [], default: {}}` ([provider-catalog.ts](https://github.com/anomalyco/opencode/blob/dev/packages/app/src/hooks/provider-catalog.ts)) + `GET /provider/auth` cho auth methods + OAuth authorize/callback | — |

### Khuyến nghị C — bám opencode cho *shape*, bám Hermes cho *phạm vi* và *cách tính tiền*

Xếp hạng:

1. **Không dựng provider catalog.** Cả hai nguồn nội bộ đồng thuận và tôi không tìm được lý do đảo: `hermes-route-subagent`:562 nói không port model_metadata vì repo có 2 model cố định + đã có `probe.py` tự kiểm khả năng model lúc boot; `docs/Harness/target-architecture.md`:278 chốt *"Không cần hỗ trợ mọi provider. Hai adapter production/test hoặc hai route"*. Repo chạy một route LLM cố định qua proxy (memory: ccs codex / gpt-5.6-luna trên cổng 8317). Một selector đa provider ở đây là selector cho một phần tử.
2. **Lấy đúng `ModelV2.Info` làm shape cho một danh sách nhỏ, tĩnh, do repo sở hữu.** Nếu cần cho user chọn giữa "nhanh/rẻ" và "kỹ/đắt": hằng số trong `core/llm/`, không phải catalog fetch từ ngoài — vì bài học #84482 nói chính models.dev cho context length **sai** và phải override. Ba field bắt buộc lấy từ opencode: `limit{context, output}` tách nhau, `cost[]` là array chứ không phải scalar (repo sẽ cần bậc thang khi prompt cache vào giá), `status`+`enabled` tách nhau (một model `deprecated` vẫn có thể còn `enabled` cho thread cũ).
3. **Per-session override: bám opencode hai-tầng.** `agent_thread.model` nullable = lựa chọn hiện tại; `agent_turn` (hoặc `agent_message`) ghi model **thật đã chạy**. Đây không phải trang trí: bài học #51607 của Hermes nói thẳng rằng nếu chỉ giữ ở session thì cost bị dồn hết cho model đầu tiên. Repo đã có ledger nên chỉ cần cột.
4. **Hiển thị cost: bám Hermes, không tự nghĩ.** Ba luật (cộng usage phụ **kể cả title generator ở mục A**, phân bổ per-model, 4 chữ số thập phân) là ba lớp lỗi đã xảy ra thật ở một hệ có người dùng. Chi phí thi công gần 0, chi phí sai thì mất tin cậy. Riêng luật "cộng cả usage phụ" phải ghi vào cùng PR với title generator, không để sau — nếu không stage-2 title là một lời gọi model **không** vào ledger.

**Rủi ro adoption:** thấp. Rủi ro thật là scope creep: mục C dễ phình từ "cho user chọn 2 model" thành "provider abstraction". `target-architecture.md`:266 đã đặt hàng rào — model gateway là seam duy nhất hiểu provider wire format.

---

## 4. D — Event bus / SSE vocabulary

**Đây là mục repo đang mạnh hơn cả hai nguồn tham chiếu.** Nói rõ để không ai port ngược.

| Chiều | Hermes | opencode | Repo hiện tại |
|---|---|---|---|
| Cơ chế | **Không có event bus, không có SSE nội bộ.** 20+ callback trực tiếp trên `AIAgent` (`tool_progress_callback`, `stream_delta_callback`, `notice_callback`, `reasoning_callback`, `tour_callback`, `step_callback`…) — `docs/hermes/hermes-orchestrator-state-260820-2352.md`:23. Lý do tồn tại: Hermes chạy sync trong nhiều host process (CLI/gateway/TUI) không có event loop chung. Cùng file:243 kết luận **không port**: *"Ta đã có SSE + checkpoint model — kiến trúc publish/subscribe rõ ràng hơn"*. Riêng observer schema `hermes.observer.v1` phát lifecycle session/turn/API/tool/approval/subagent, payload đắt chỉ dựng khi hook đăng ký (`docs/hermes/research-260823-1649-hermes-agent-architecture-sota.md`:§Streaming và event) | `GET /event` SSE. Xem chi tiết dưới | `GET /turns/{turn_id}/events` SSE, `apps/api/src/agent/{events,sse}.py` |
| Danh sách event | — | Manifest hợp thành từ ~30 nhóm ([event-manifest.ts](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/event-manifest.ts)): ModelsDev, Integration, Catalog, Session, FileSystem, Reference, Permission, Plugin, ProjectDirectories, FileSystemWatcher, Pty, Question, SessionTodo, Lsp, Mcp, Tui, Vcs, Workspace, Worktree, Server… Riêng session ([session-event.ts](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/session-event.ts)) có 31 định nghĩa | **8 type v2**: `turn.snapshot`, `content.delta`, `tool.call`, `canvas.ready`, `turn.completed`, `turn.incomplete`, `turn.failed`, `turn.cancelled` (`events.py::EventType`) |
| Đặt tên | `hermes.observer.v1` | `session.next.<domain>.<verb quá khứ>` — `session.next.tool.input.delta`, `session.next.step.ended`, `session.next.compaction.started`, `permission.v2.asked`, `models-dev.refreshed`, `server.connected`. **Version nằm trong tên namespace** (`.next.`, `.v2.`) | `<đối tượng>.<biến cố>`, `ENVELOPE_VERSION = 2` là một field trong envelope, không trong tên type |
| Durable vs live | — | **Đây là phát hiện quan trọng nhất của mục D.** Mỗi definition có thể khai `durable: {aggregate: "sessionID", version: n}`. Các `*.delta` (`text.delta`, `reasoning.delta`, `tool.input.delta`, `compaction.delta`) **cố tình KHÔNG durable**, comment ngay trên chúng: *"Stream fragments are live-only; Text.Ended is the replayable full-value boundary."* `DurableDefinitions` (28) ⊂ `Definitions` (32). `Event.latest()` chọn version cao nhất per type; `versionedType(type, version)` là khoá của durable log; hai definition cùng type khác version cùng tồn tại được (`Step.Ended`/`Step.Failed` đã ở `version: 2`) | Tách theo trục khác nhưng cùng tinh thần: `content.delta` streaming, `turn.snapshot` restate toàn bộ. `events.py` docstring: *"the concatenation of every content.delta carrying kind:'answer' and the text on the snapshot the same string"* |
| Subscribe / replay khi reconnect | — | **Không có replay.** [handlers/event.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/server/routes/instance/httpapi/handlers/event.ts): `id: undefined` trên **mọi** SSE frame, mọi frame dùng `event: "message"`, type thật nằm trong JSON `{id, type, properties}`. Không đọc `Last-Event-ID`. Frame đầu là `server.connected`; heartbeat là **event thật** `server.heartbeat` mỗi 10s; `server.instance.disposed` kết thúc stream. Reconnect = client gọi lại REST rồi resubscribe. Listener register **eager** trước khi body fiber chạy, có comment: *"events published after this point cannot be lost while the HTTP body fiber is starting"* | **Có replay, và chặt hơn.** `seq` đi vào SSE `id` để browser tự gửi lại `Last-Event-ID`; `subscribe()` capture snapshot + register queue trong **một block đồng bộ** → không có cửa sổ nào event nằm ngoài cả snapshot lẫn stream; snapshot **không tiêu seq**; subscriber không apply backpressure được (queue bounded 256, đầy thì drop *subscriber đó*, không làm chậm Turn); heartbeat là **SSE comment** `": heartbeat\n\n"` — không có `id` nên không reset `Last-Event-ID` của browser, `EventSource` discard không dispatch (`sse.py`:1-35, `events.py`:1-46) |
| Idle / abort | — | heartbeat 10s; `X-Accel-Buffering: no`, `Cache-Control: no-cache, no-transform` | heartbeat 15s (*"proxy có idle timeout 60s thấy traffic 4 lần trước khi nó đóng"*); terminal event đóng subscriber → response tự complete; Turn đã xong trước khi connection tới = một snapshot + close ngay |

### Khuyến nghị D — giữ nguyên cơ chế của repo. Lấy đúng hai thứ từ opencode.

Xếp hạng:

1. **Không đổi transport, không đổi replay model.** Repo dùng `id`+`Last-Event-ID`+snapshot-atomic; opencode không có replay và bù bằng refetch REST. Với một Turn dài chạy trên mạng di động, refetch-toàn-bộ mỗi lần rớt là đúng thứ replay được thiết kế để tránh. Heartbeat-as-comment của repo cũng đúng hơn heartbeat-as-event: `server.heartbeat` của opencode chiếm một event id và một dòng trong mọi log/reducer client. Ba câu docstring trong `sse.py` và `events.py` giải thích lý do tốt hơn tôi diễn giải được — đừng sửa chúng.
2. **Lấy luật durable-vs-live tường minh.** Repo đã *làm* đúng (delta streaming, snapshot restate) nhưng chưa *khai* nó ở tầng dữ liệu. Khi thêm event mới, luật nên thành thuộc tính của định nghĩa event chứ không phải kiến thức trong đầu người viết: mọi `*.delta` là live-only, và **mỗi delta phải có một event "ended"/snapshot mang giá trị đầy đủ làm biên replay**. Đây chính là lớp lỗi mà `canvas.ready` sẽ gặp nếu sau này có `canvas.delta`.
3. **Lấy quy ước version-trong-tên cho *đổi nghĩa*, giữ `ENVELOPE_VERSION` cho *đổi phong bì*.** `events.py` đã ghi luật đúng ("bump khi hình dạng envelope đổi, không bao giờ khi payload thêm key") và `canvas.ready` là ví dụ chuẩn của mở rộng additive. Cái còn thiếu là đường đi cho trường hợp thứ ba: một event **đổi nghĩa** cùng tên. opencode giải bằng `durable.version` per-definition + `Event.latest()`, và đã dùng thật (`Step.Ended` version 2). Repo không cần cả máy móc đó, chỉ cần luật: đổi nghĩa thì đổi tên type, không bump envelope.
4. **Không port event bus toàn cục.** opencode có `/event` là một stream cho **cả instance** (mọi session, filesystem, lsp, mcp, pty…) vì TUI cần biết mọi thứ. Repo có một stream **per Turn** — nhỏ hơn, và đúng với `docs/Harness/target-architecture.md`:333 (*"Product events là projection versioned cho client và reconnect"*). Cái đáng học từ manifest opencode là **kỷ luật một chỗ liệt kê tất cả**, không phải phạm vi.

**Rủi ro adoption:** rất thấp — cả bốn đều là luật viết ra, không phải code mới.

---

## 5. E — Server/client split

| Chiều | Hermes | opencode | Repo hiện tại |
|---|---|---|---|
| Nguyên tắc | Không có split: một process, `AIAgent` + 20+ callback, host process (CLI/gateway/TUI) tự bind. `mcp serve` expose **conversations** qua 9 tool MCP đọc **trực tiếp SQLite** (`SessionDB`, `state.db`), không qua REST vào runtime (`docs/hermes/hermes-mcp-ops-eval-260820-2352.md`:48) — tức là bypass chính runtime của nó | **Server là lõi, TUI chỉ là client.** Cùng một OpenAPI 3.1 contract phục vụ TUI, IDE, SDK, web, automation; SDK sinh từ chính spec đó. `docs/opencode/opencode-architecture.md`:§Kết luận ngắn: *"đây là boundary sản phẩm tốt hơn việc nhúng agent loop trực tiếp vào giao diện"*. 6 lớp có owner rõ: transport / project runtime / durable conversation / agent runtime / capability / model abstraction | FastAPI + SSE đã là server; Next.js App Router là client. Endpoint còn lại: `auth`, `agent`, `message_flag`, `favicons`, health (CLAUDE.md §Không còn tồn tại) |
| Client mỏng đến đâu | — | Client giữ **projection/reducer** khá dày: `context/global-sync/event-reducer.ts`, `session-cache.ts`, `session-load.ts`, `session-trim.ts`, `server-session-v2-reducer.ts`, và một package riêng `session-ui`. Đây là hệ quả trực tiếp của việc **không có replay**: client phải tự dựng lại state | `apps/web/src/hooks/use-threads.ts` docstring: *"Threads và messages là TanStack Query resources; Turn in flight thì không. Nothing here is polled"* — invalidate ở terminal event, không polling. Canvas nạp qua `next/dynamic` để recharts không nằm trên first paint |

### Khuyến nghị E — repo đã ở đúng chỗ. Một luật cần viết ra, một cái bẫy cần tránh.

1. **`docs/Harness/target-architecture.md`:366 đã chốt: OpenCode server/session separation = "Adapt", không "Adopt"** — lý do ghi thẳng: *"FastAPI/SSE đã là server; lấy durable typed state và shared contract"*. Không có việc gì phải làm ở tầng kiến trúc.
2. **Luật cần viết ra: server sở hữu state, client không suy diễn state từ event.** Repo đã tuân thủ (snapshot là nguồn duy nhất để reconcile, `text` trên snapshot bằng concat các delta). Cái bẫy là làm ngược: khi thêm A (archived), B (share), C (model per-thread), rất dễ để FE tự tính `archived = !visible`, hoặc share URL do FE ghép từ token. Nhìn `packages/app/src/context/global-sync/*` của opencode để thấy chi phí của việc đó — 6 module reducer/cache/trim/load ở client. Repo tránh được vì có replay; đừng đánh mất lợi thế đó bằng cách để FE giữ state phái sinh.
3. **Không sinh SDK từ OpenAPI ở quy mô này.** opencode cần vì có ≥4 client độc lập (TUI Go, IDE, desktop, web). Repo có **một** client. `apps/web/src/lib/alpha-desk/{api,types}.ts` viết tay là ít máy móc hơn và không thêm bước build. Chỉ đáng đảo nếu xuất hiện client thứ hai (mobile, hoặc B2B API cho tenant).
4. **Cái đáng học thật, cho Phase 2 B2B:** `project/instance-runtime.ts` cô lập service state theo directory/worktree (`docs/opencode/opencode-architecture.md`:§Sáu lớp). Khi repo làm multi-tenant workspace (CLAUDE.md Phase 2), câu hỏi "service state nào scoped theo tenant, cái nào global" là cùng một câu hỏi. Ghi chú lại, chưa làm.

---

## 6. F — Permission/approval + abort

| Chiều | Hermes | opencode | Repo hiện tại |
|---|---|---|---|
| Model quyền | `write_approval.py` cho ghi memory/skill, 3 trạng thái `allow/blocked/stage`, mặc định `false` (ghi tự do). Lý do nêu ngay trong docstring: self-improvement loop **tự quyết** ghi gì vào kho bền. `docs/hermes/hermes-memory-260820-2352.md`:304-325,368 nhấn: **approval gate tách khỏi enable/disable** — *"write_approval chỉ là gate phê duyệt, không phải kill switch"* | [`PermissionV2`](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/permission.ts): `Rule {action, resource, effect: allow\|deny\|ask}`, ruleset là array, **match cuối thắng**, không match → `ask`; `deny` throw; `ask` publish event rồi chờ. `Reply = once \| always \| reject`. `always` chỉ sống trong runtime state hiện tại. Default agent `* = allow`, `doom_loop = ask`, path ngoài workspace = ask, dotenv nhạy cảm hơn (`docs/opencode/research-260823-opencode-primary-sources.md`:§5.1) | **Không có khái niệm approval.** `grep -rn "approval\|approve" apps/api/src/agent/` → 0 kết quả. `guardrails.py` là ladder `allow → warn → block → halt` nhưng theo trục **lặp lại**, do backend tự quyết, không hỏi user |
| Có phải sandbox | — | **Không.** `docs/opencode/research-260823-opencode-primary-sources.md`:§5.2 gọi đây là *"khoảng cách SOTA lớn nhất"*: parser tĩnh không thể là boundary cho shell tổng quát (script, interpreter, symlink, subprocess, dynamic path, network nằm ngoài hình dạng command); *"Permission giúp consent/UX, nhưng blast radius vẫn là quyền host"* | Không áp dụng — không có tool nào tạo side effect ngoài đọc store + web fetch |
| Bẫy đã biết | **Ba CVE/issue cùng một gốc**: `GHSA-qg5c-hvr5-hjgr`/#15216, #33057/#30882, `GHSA-96vc-wcxf-jjff`. Worker thread không kế thừa threading-local approval callback → *"lệnh nguy hiểm tự động auto-approve sai chế độ"*; cờ interactive-mode làm process-global khiến session A "mượn" trạng thái approve của session B; mất callback thì phải **fail-closed**. Cộng #79719: **thời gian chờ người phải đo tại nguồn và loại khỏi deadline batch** — nếu đo bằng "đang chiếm authorization gate" thì một hook treo hoặc client chết sẽ vô hiệu hoá deadline (`docs/hermes/hermes-tools-260820-2352.md`:180,184,191; `hermes-route-subagent`:418-419) | Plugin sửa được arguments trước khi tool chạy — *"sức mạnh và cũng là trust boundary"* (`docs/opencode/opencode-architecture.md`) | — |
| Abort | Interrupt giữa stream. Bẫy: abort giữa stream mà không `stream.close()` trên **đúng thread sở hữu** để lại connection "checked out" vĩnh viễn khỏi httpx pool → mỗi interrupt rò một connection tới khi pool cạn (`docs/hermes/hermes-orchestrator-state-260820-2352.md`:103). Cộng: nén phải **atomic** — user message tới giữa lúc gọi LLM phụ không được abort nó, nếu không mất cả handoff thật (#23975, `hermes-context`:47) | `POST /session/:sessionID/abort` → `promptSvc.cancel(sessionID)` → `return true`, không có gì khác ([handlers/session.ts:232-235](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/server/routes/instance/httpapi/handlers/session.ts#L232)). Runner V2 tự khai **cancellation settlement chưa parity** (`docs/opencode/opencode-architecture.md`:§Hai thế hệ) | `POST /turns/{turn_id}/cancel`, **idempotent, dispatch nothing**: lần cancel thứ hai trả cùng đáp án, không stamp lại, không đổi được terminal reason đã ghi. Tool read-only đang bay **được phép chạy xong** (ADR-0008), trace giữ, kết quả không feed vào round sau. Docstring nói thẳng *"Retry is not this endpoint"*. `TurnService._execute` gom **mọi** exit path qua đúng 2 cửa `_finish`/`_finish_bare` |

### Khuyến nghị F — abort giữ nguyên (repo tốt hơn cả hai). Approval: chưa cần, nhưng chốt trước hình dạng.

Xếp hạng:

1. **Abort: không đổi gì.** `docs/hermes/hermes-synthesis-260821-0030.md`:§2 phát hiện #11 nói rõ repo **tốt hơn Hermes** ở chính điểm này, kèm trích dẫn Hermes tự thừa nhận: *"Some abnormal early-return paths … do not currently emit this hook."* opencode thì tự khai cancellation settlement chưa parity. Ba thuộc tính của repo — idempotent, hai cửa exit duy nhất, read-only tool đang bay được chạy xong — là ba thứ cả hai nguồn đều không có đủ. Giữ.
2. **Approval: chưa xây, vì chưa có tool nào cần nó.** Approval tồn tại để gate **side effect**. Tool của repo đọc store + fetch web; `run_study` tính rồi ghi artifact của chính user. Không có gì để phê duyệt. Xây một permission plane bây giờ là dựng hàng rào trước khi có đường — đúng lớp sai mà `hermes-synthesis`:§6 tự phê: *"Ta làm ngược: 20 ADR và một validator 1.302 dòng dựng trước khi có người dùng."*
3. **Nhưng chốt trước hình dạng, vì nó rẻ khi chốt và đắt khi sửa.** Khi nào cần: (a) tool ghi ra ngoài phạm vi user; (b) một vòng tự-học ghi vào `agent_knowledge` — `hermes-memory`:407 nói đúng chỗ này (*"chỉ cần khi có auto-write"*); (c) B2B tenant cần policy per-workspace. Lúc đó bám **hình dạng của opencode** (`{action, resource, effect}`, match cuối thắng, không match → `ask`; `Reply = once|always|reject`) vì nó là data chứ không phải code, test được, và cấu hình được per-tenant — trong khi Hermes là boolean 3-trạng-thái cho một use case. **Nhưng bám hai luật của Hermes:** (i) approval gate ≠ kill switch, hai cơ chế riêng; (ii) mất kênh hỏi user thì **fail-closed** (`GHSA-qg5c-hvr5-hjgr`), không auto-approve. Và default `* = allow` của opencode thì **không** lấy — `docs/opencode/opencode-architecture.md` liệt kê chính nó ở mục "Giới hạn".
4. **Một bài học áp dụng được ngay, không cần approval:** #79719 — thời gian chờ bên ngoài phải đo tại nguồn và **loại khỏi** deadline. Repo chưa có chờ-người, nhưng có chờ-vnstock (180 req/phút Bronze). Nếu deadline của Turn đang tính cả thời gian rate-limit sleep thì đó là cùng lớp lỗi. Đáng kiểm.

---

## 7. `docs/Harness/` đã chốt sẵn mục nào

Câu hỏi coordinator đặt trực tiếp. Trả lời:

| Mục | Trạng thái trong `docs/Harness/` | Ghi chú |
|---|---|---|
| A session/thread model | **Chưa quyết.** `target-architecture.md`:78 chỉ nói "Session state … **Current**, cần typed task/part depth hơn" — nói về part/task, không nói metadata/title/soft-delete | A là quyết định mới |
| B share | **Không xuất hiện.** Không có dòng nào về share/public link trong cả 5 file | B là quyết định mới, và là mục có threat surface cao nhất. `investment-intelligence-contract.md` chưa nói gì về việc dữ liệu ra khỏi biên user |
| C model selector | **Đã chốt phần phạm vi.** `target-architecture.md`:278: *"Không cần hỗ trợ mọi provider. Hai adapter production/test hoặc hai route"*; :266 model gateway là seam duy nhất hiểu provider wire format. Cost/limit hiển thị cho user: chưa quyết | Khuyến nghị C §1 chỉ đang thi hành quyết định đã có |
| D event vocabulary | **Đã chốt nguyên tắc.** `target-architecture.md`:329-341: bốn surface tách nhau (durable state / product events / operational telemetry / evaluation trajectory), *"Product events là projection versioned cho client và reconnect"*, mọi event phải liên kết được root task/parent task/model attempt/tool call/evidence IDs **mà không cần lưu chain-of-thought**, và *"Thought UI không phải audit proof"*. Danh sách event cụ thể: chưa | Luật "versioned projection" ủng hộ khuyến nghị D §3 |
| E server/client split | **Đã chốt.** :366 OpenCode server/session separation = **Adapt**; 10 dependency rule ở :347-357, trong đó #1 *"Product surface phụ thuộc runtime contract, không phụ thuộc provider/tool"* | Không có việc mới |
| F permission/abort | **Một nửa.** :126 typed lifecycle có `cancelled` là terminal state; :137 *"Cancellation truyền xuống model/tool/child và terminal state luôn được ghi"*; :295 *"monotonic authorization: child không tăng data/action permission"*. Approval hỏi-user: không xuất hiện. `quality-safety-and-operations.md` sở hữu quyền dừng | :295 là ràng buộc phải giữ nếu sau này có child thread |

Cộng hai dòng trong bảng Adopt/Adapt/Reject liên quan trực tiếp: **"OpenCode typed tool lifecycle = Adopt"** (*"Cần cho replay, orphan settlement và UI consistency"*) và **"OpenCode host shell/plugin/MCP breadth = Reject"**.

---

## 8. Tổng hợp khuyến nghị

| Mục | Bám cái nào | Việc chính | Chi phí | Rủi ro |
|---|---|---|---|---|
| A | opencode (archive) + Hermes (title 2 tầng) + prompt của opencode | `archived_at` qua PATCH đã có; title stage-1 derived đồng bộ + stage-2 LLM background, precedence enforce trong transaction | nhỏ | thấp |
| B | **Không bám ai nguyên hình.** Bảng + kill switch + luật no-child-share của opencode; redaction fail-closed của Hermes; snapshot của chính repo | share nội bộ (không service ngoài), snapshot không live sync, `public_view()` whitelist fail-closed | trung bình | **cao** — route công khai đầu tiên |
| C | opencode cho shape `ModelV2.Info`; Hermes cho phạm vi + 3 luật cost | danh sách model tĩnh do repo sở hữu; `thread.model` + model-thật-per-turn; 4 chữ số thập phân, cộng usage phụ | nhỏ | thấp (bẫy: scope creep) |
| D | **Repo. Không đổi transport.** Lấy 2 luật từ opencode | khai durable-vs-live tường minh cho mọi event mới; đổi nghĩa → đổi tên type | rất nhỏ | rất thấp |
| E | Đã đúng (`target-architecture.md`:366 chốt "Adapt") | viết ra luật "FE không giữ state phái sinh"; không sinh SDK | 0 | rất thấp |
| F | Abort: repo. Approval: hoãn, chốt hình dạng opencode + 2 luật Hermes | không xây approval; kiểm deadline có tính thời gian rate-limit hay không | 0 (+ 1 kiểm) | thấp |

**Thứ tự thi công đề xuất:** A → C → D (ba mục rẻ, không giao nhau, mỗi mục một cột/một luật) → B cuối, và B nên là plan riêng có mục threat model, không ghép vào plan A.

---

## 9. Điều báo cáo này KHÔNG phủ

1. **Không đọc source Hermes.** Cột Hermes 100% từ `docs/hermes/`, đúng như brief. Chính bộ tài liệu đó tự cảnh báo hai lần: docstring của Hermes *"không phải chân lý"* (một docstring nói "10% savings" trong khi hành vi thật là quyết định nhị phân), và vùng orchestrator đếm 300 issue number nhưng chỉ gán bài học cho ~13 (`hermes-synthesis`:§6). Con số cụ thể (p50 151s, 48 ký tự, 12 từ) chưa được xác minh lại trên source.
2. **Không đối chiếu `docs/opencode/` với nhánh `dev` hôm nay một cách hệ thống.** Đã thấy dịch chuyển lớn (`packages/schema` là owner mới). Các claim của `docs/opencode/` về `session/prompt.ts`, `processor.ts`, `tools.ts` chưa được kiểm lại — README của nó dặn đúng việc phải làm khi đổi version.
3. **Không đọc phía server nhận của share.** `opncd.ai` và `packages/enterprise/src/{core/share.ts,routes/share/[shareID].tsx}` chưa đọc. Nghĩa là: retention thật, có index công khai hay không, và hành vi sau khi DELETE — chưa xác minh ngoài lời docs.
4. **Chưa chạy test nào.** Mọi claim về repo là đọc code, không phải hành vi quan sát được.
5. **Không thiết kế schema/migration.** Đây là research; cột và bảng nêu ra là hình dạng đề xuất, không phải plan thi công. CLAUDE.md yêu cầu backup trước mọi đổi schema và `agent_thread` nằm **ngoài** bốn surface được unfreeze — B và A cần mở freeze, đó là quyết định của người dùng.
6. **Không đánh giá pháp lý mục B.** Link công khai chứa phân tích chứng khoán VN có thể là "cung cấp thông tin đầu tư" ra công chúng. Memory đã ghi: licence vnstock cấm thương mại ở mọi tier và claim "≤500 user" trong CLAUDE.md không xác minh được. Share công khai làm câu hỏi licence nặng hơn, không nhẹ hơn.

## Câu hỏi chưa giải quyết

1. **Mục B có nằm trong threat model đã chấp nhận?** `docs/Harness/` không có một dòng nào về việc dữ liệu ra khỏi biên user. Đây là câu hỏi product/pháp lý, không phải kỹ thuật, và nên trả lời **trước** khi lên plan.
2. **Share snapshot: bấm lại thì token cũ chết hay cùng token dời con trỏ?** Token chết = link đã gửi bị vỡ. Token sống = người nhận thấy nội dung đổi dưới chân họ. opencode không phải trả lời vì nó live sync.
3. **Ai được share, và share cái gì khi thread có artifact?** Artifact giữ `as_of` đóng băng và render qua widget registry — link công khai có nạp được widget registry của FE không, hay share chỉ có text? Ảnh hưởng trực tiếp tới giá trị của tính năng.
4. **Stage-2 title: trần theo số lần hay theo tiền?** Trùng đúng câu hỏi mở #5 của `hermes-synthesis`. Envelope $45/tháng chưa reweight sau khi bỏ Analysis lane, nên "còn dư" hiện là phỏng đoán.
5. **`agent_thread` đang freeze.** CLAUDE.md unfreeze đúng bốn surface canvas + bốn file spine daily. A/B/C đều đụng `alpha/models.py`. Cần quyết định mở freeze trước khi có plan.
6. **Deadline của Turn có đang tính thời gian rate-limit sleep của vnstock?** Nếu có, đó là #79719 dưới tên khác. Kiểm rẻ, chưa kiểm.
7. **Mục C có phải nhu cầu thật?** Repo có một route LLM cố định. "Model selector thật" cho một phần tử là UI trống. Nếu động lực là *hiển thị cost/limit* thì đó là mục khác và rẻ hơn nhiều — không cần selector.

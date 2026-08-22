# Hermes Agent — Ký ức, Skill, Vòng tự cải thiện: đọc code và bài học cho Stock_Massive

Nguồn: clone sparse `NousResearch/hermes-agent` (MIT) tại
`/private/tmp/claude-501/.../scratchpad/hermes-agent`, HEAD `f43eabe`. Đọc trực tiếp
`agent/*.py`, `tools/*.py`, 2 file doc raw (`background-systems.md`,
`session-storage.md`). Không sửa code Hermes, không chạy test.

---

## 1. Kiến trúc ký ức/skill của Hermes — tổng quan

Hermes tách hệ thống prompt thành 3 tầng (`agent/system_prompt.py:340-899`,
docstring `build_system_prompt_parts`):

```
stable    — identity, tool guidance, coding prefix... byte-stable mọi Turn
context   — context files (AGENTS.md/CLAUDE.md của workdir)
volatile  — skills index, memory snapshot, USER.md, external-memory block,
            timestamp — "most likely to change is rendered LAST" để giữ prefix
            cache của backend implicit-longest-prefix
```

`build_system_prompt()` chỉ chạy 1 lần/session, cache vào
`agent._cached_system_prompt`; chỉ rebuild khi có event context-compaction
(`invalidate_system_prompt`, `agent/system_prompt.py:931-940`).

Bốn kho lưu trữ độc lập, mỗi kho một cơ chế ghi/đọc khác nhau:

| Kho | File/DB | Ai ghi | Vào prompt thế nào |
|---|---|---|---|
| MEMORY.md / USER.md | `~/.hermes/memories/*.md` | tool `memory` (foreground hoặc background_review) | **snapshot đông cứng** lúc `load_from_disk()`, tầng volatile |
| Session history | `~/.hermes/state.db` (SQLite, FTS5) | mọi turn tự động | **không vào prompt** — chỉ trả về qua tool `session_search` khi model gọi |
| Skills | `~/.hermes/skills/**/SKILL.md` | user, hoặc curator/background_review (chỉ skill `created_by: agent`) | **index (tên+desc≤60 ký tự)** vào tầng volatile; nội dung đầy đủ chỉ nạp khi model gọi `skill_view` |
| Curator state | `.curator_state`, `.usage.json`, `.curator_backups/*.tar.gz` | curator (chạy khi idle) | không vào prompt — vận hành ngoài luồng |

Điểm thiết kế xuyên suốt cả 4: **ghi xong không đổi ngay prompt đang cache**
(memory), **không tốn LLM để đọc lại** (session_search), **chỉ tự sửa cái nó tự
tạo ra** (curator/skill_provenance), và **mọi write tự động đều có cổng phê
duyệt tùy chọn** (`write_approval.py`).

---

## 2. Từng cơ chế

### 2.1. MEMORY.md / USER.md — ai ghi, giới hạn, vì sao snapshot

`tools/memory_tool.py`. Hai file riêng, class `MemoryStore`
(`memory_tool.py:148-165`):

```python
def __init__(self, memory_char_limit: int = 2200, user_char_limit: int = 1375):
```

- **MEMORY.md** (2200 ký tự) — "agent's personal notes" (môi trường, quy ước
  project, tool quirk). **USER.md** (1375 ký tự) — hồ sơ người dùng (sở thích,
  cách làm việc mong đợi). Giới hạn tính bằng **ký tự, không phải token** — lý
  do nêu rõ trong docstring đầu file: "model-independent". Cấu hình được qua
  `memory.memory_char_limit` / `memory.user_char_limit`
  (`memory_tool.py:900-913`).
- **Ai ghi**: một tool `memory(action=add|replace|remove)` duy nhất, gọi từ
  agent thường (foreground) HOẶC từ fork `background_review` (mục 2.5) — không
  phân biệt API, chỉ phân biệt qua ContextVar provenance (`skill_provenance.py`).
- **replace/remove dùng khớp chuỗi con ngắn duy nhất**, không phải ID hay full
  text — giảm token khi model muốn sửa 1 câu.
- **Vì sao snapshot vào prompt thay vì RAG mỗi turn**: docstring lớp
  `MemoryStore` (`memory_tool.py:148-157`) nói thẳng — hai state song song,
  `_system_prompt_snapshot` (đông cứng lúc `load_from_disk()`) và
  `memory_entries/user_entries` (live, phản hồi tool). RAG-mỗi-turn nghĩa là
  một lệnh gọi/embedding lookup mỗi turn — tốn tiền và **phá cache prefix**
  (nội dung câu trả lời tool đổi mỗi lần); snapshot 1 lần thì cả session dùng
  lại đúng prefix đó. Đây chính là lý do dùng file `.md` nhỏ (≤2200/1375 ký
  tự) đọc-1-lần thay vì một vector store truy vấn động.
- **Chống prompt injection tại thời điểm snapshot**: mỗi entry được quét qua
  `tools/threat_patterns.py` (scope "strict") lúc `load_from_disk()`
  (`_sanitize_entries_for_snapshot`, dòng 243-278); nếu khớp mẫu, snapshot
  thay bằng `"[BLOCKED: ... Removed from system prompt; use memory(action=remove)...]"`
  — nhưng **live state vẫn giữ bản gốc** để user tự xem/xoá, không âm thầm
  drop (tránh giấu cuộc tấn công khỏi user).

### 2.2. Vì sao ghi giữa session KHÔNG mutate prompt đã dựng

`format_for_system_prompt()` (`memory_tool.py:682-693`):

> "This returns the state captured at load_from_disk() time, NOT the live
> state. Mid-session writes do not affect this. This keeps the system prompt
> stable across all turns, preserving the prefix cache."

Hệ quả cache: `build_system_prompt()` chỉ chạy 1 lần/session
(`system_prompt.py:903-911`) — nếu memory-write giữa session đổi luôn prompt
thì mọi turn sau cache-miss ở implicit-prefix backend (và làm mất tính
byte-stable ở backend có `cache_control` tường minh). **Path duy nhất
rebuild lại + `load_from_disk()` lại** là sau context-compaction:

```python
def invalidate_system_prompt(agent):
    agent._cached_system_prompt = None
    ...
    if agent._memory_store:
        agent._memory_store.load_from_disk()   # system_prompt.py:931-940
```

`agent/conversation_compression.py:186-205` còn có
`_builtin_memory_prompt_snapshot` để so sánh cache cũ với snapshot mới, quyết
định có được giữ prompt cache khi compaction chỉ retain (không rebuild toàn
bộ). Ngoài compaction, còn 1 nhánh khác được ghi chú (`system_prompt.py:955`,
issue `#72626`): failover cache-on provider giữa turn cũng phải rebuild tầng
stable — chứng minh việc tách stable/volatile là để né chính xác loại lỗi
này.

### 2.3. `session_search` — FTS5, 4 mode, adaptive/bookend, chi phí

`tools/session_search_tool.py:1-31` (docstring đầu file), backed bởi
`hermes_state_search.py` (mixin của `SessionDB`, `hermes_state.py`).

**Index FTS5** (theo `session-storage.md`): 3 virtual table trên
`messages(content, tool_name, tool_calls)` — bản chuẩn `messages_fts`, bản
`messages_fts_trigram` (substring/CJK), bản `messages_fts_cjk`
(`cjk_unicode61` tokenizer). External-content FTS5, đồng bộ qua trigger
INSERT/UPDATE/DELETE, có rebuild theo watermark (`fts_rebuild_high_water`)
để không double-index khi rebuild nền.

**4 mode, suy ra từ tham số, không có field `mode` tường minh**:

1. `discover` — có `query`: chạy FTS5, dedupe theo *session lineage*
   (`parent_session_id` chain), demote hàng cron xuống dưới hàng interactive
   trước khi dedupe (issue `#19434` — corpus cron nhiều làm mất hết session
   của user khỏi top-N).
2. `scroll` — có `session_id` + `around_message_id`: cửa sổ ±N quanh anchor,
   không FTS5, không bookend; muốn cuộn tiếp thì re-anchor vào đầu/cuối cửa sổ
   vừa trả.
3. `read` — chỉ `session_id`: trả nguyên session hoặc head/tail cho session
   lớn.
4. `browse` — không tham số: liệt kê session gần đây theo thời gian.

**"Adaptive detail"** (mặc định `detail="adaptive"`, chỉ áp dụng cho
`discover`): kết quả **hạng nhất** được hydrate đầy `result_detail="full"` (cửa
sổ ±5 + bookend); các kết quả **hạng thấp hơn** chỉ giữ đúng message khớp +
metadata (`result_detail="compact"`) — trade-off token/độ chính xác, xem
`_discover()` (`session_search_tool.py:876-878`):
```python
result_detail = "full" if detail == "full" or not results else "compact"
```
`detail="full"` ép hydrate đầy **mọi** kết quả.

**Bookend** (`hermes_state_search.py:975-1071`, `get_anchored_view`):
`bookend=3` (mặc định trong discover) nghĩa là kèm 3 message đầu và 3 message
cuối của session, ngoài cửa sổ quanh anchor — mục đích nêu rõ trong docstring:
"Bookends let an FTS5 hit anywhere in a long session yield the goal / outcome
even when the window misses it" — hit ở giữa session dài không tự nhiên trôi
mất phần mở đầu/kết luận.

**Chi phí LLM = 0**: khẳng định 3 lần trong file (`session_search_tool.py:12,
27, 1132`) — "Zero LLM cost" / "No LLM calls anywhere — every shape returns
actual messages from the DB." Toàn bộ 4 mode chỉ là SQL/FTS5 + Python định
dạng lại JSON.

**Lịch sử** (docstring dòng 29-32): PR `#20238` (JabberELF) khởi tạo dual-mode
fast/summary (có nhánh LLM tóm tắt); PR `#26419` (yoniebans) thêm anchored
drill-down + bookend + sort. Bản hiện tại **hợp nhất, bỏ hẳn nhánh LLM
summary** — tức đã từng có version tốn LLM và bị thay bằng bản 0-cost.

### 2.4. Curator — trigger, snapshot/rollback, phạm vi sửa

`agent/curator.py` (2034 dòng) + `agent/curator_backup.py` (758 dòng).

**Trigger = inactivity, không cron** — docstring đầu file
(`curator.py:1-19`): `maybe_run_curator()` chỉ chạy khi agent idle VÀ lần
chạy trước cách đây > `interval_hours` (mặc định 7 ngày,
`DEFAULT_INTERVAL_HOURS = 24*7`). Gate cụ thể (`should_run_now`,
`curator.py:233-280`):
- `curator.enabled` phải True, không `paused`.
- **Lần đầu chưa từng chạy → KHÔNG chạy ngay** — chỉ seed `last_run_at=now`
  và defer 1 interval đầy đủ, để tránh curator tự mutate skill library ngay
  sau lần `hermes update` đầu tiên (dry-run tường minh có thể chạy sớm hơn).
- `maybe_run_curator(idle_for_seconds=...)` còn kiểm `min_idle_hours` (mặc
  định 2h) — chỉ gọi khi caller đo được agent thật sự idle.

**Snapshot/rollback trước khi mutate** — `run_curator_review()`
(`curator.py:1511-1576`):
```python
snap = curator_backup.snapshot_skills(reason="pre-curator-run")
```
best-effort (lỗi snapshot chỉ log debug, không chặn — lý do: một lỗi đĩa
tạm thời không nên vô hiệu hoá curator vĩnh viễn). `curator_backup.py`
đóng gói `~/.hermes/skills/` (trừ `.curator_backups/`, `.hub/`) thành
`tar.gz` + `manifest.json` dưới `.curator_backups/<utc-iso>/`, kèm
**bản sao `cron/jobs.json`** vì consolidation có thể viết lại tên skill mà
cron job đang tham chiếu (`cron.jobs.rewrite_skill_refs()`) — rollback phải
phục cả 2 cùng lúc để cron không trỏ vào umbrella skill đã bị hoàn tác.
Rollback (`curator_backup.py:572`) tự **snapshot cả bản hiện tại trước khi
ghi đè** — "rollback itself is undoable".

**Phạm vi sửa** — chỉ skill có `created_by: "agent"`
(`tools/skill_usage.is_agent_created`, xác nhận trong `skill_usage.py:427`).
Không đụng: bundled skill, hub-installed skill, `skills.external_dirs`,
skill pinned (`hermes curator pin`). **Không bao giờ xoá — chỉ archive**
(`.archive/`, phục hồi được qua `hermes curator restore`) — nguyên tắc ghi
thẳng trong docstring class-level: "Never auto-deletes — only archives.
Archive is recoverable."

**Chi phí**: sweep xác định (`apply_automatic_transitions`, thuần Python,
không LLM) chạy miễn phí mỗi lần curator kích hoạt. Pass "consolidate"
(fork aux-model gộp skill trùng lặp thành umbrella) **tắt theo mặc định**
(`DEFAULT_CONSOLIDATE = False`) — chỉ bật qua `curator.consolidate: true`
hoặc `hermes curator run --consolidate`; khi tắt, **không có lệnh gọi LLM
nào** trong cả pass.

### 2.5. `background_review` — fork sau turn, hỏi gì, có chặn turn không

`agent/background_review.py` (1376 dòng), gọi từ
`agent/turn_finalizer.py:772-802` — **sau khi response đã trả cho user**,
trong daemon thread (`propagate_context_to_thread(target), daemon=True,
name="bg-review"`, `run_agent.py:1912`).

**KHÔNG chạy sau mọi turn** — trigger là bộ đếm nudge, không phải mỗi turn:
```python
agent._memory_nudge_interval = 10   # agent_init.py:1802/1817
agent._skill_nudge_interval  = 10   # agent_init.py:1918/1921
```
`turn_finalizer.py:772-776` chỉ set `_should_review_skills=True` khi
`_iters_since_skill >= _skill_nudge_interval` (tương tự cho memory qua
`_should_review_memory`, `turn_finalizer.py:133`). Comment tại
`agent_init.py:673` giải thích lý do interval, không phải mỗi turn:
mỗi lần fork tốn **~30K token** (một agent con phải load lại system prompt +
replay conversation).

**Không chặn turn chính** — spawn ở daemon thread sau khi
`final_response` đã có, gate rõ:
```python
if (final_response and not interrupted
        and not getattr(agent, "skip_background_review", False)
        and (_should_review_memory or _should_review_skills)):
    agent._spawn_background_review(...)
```
`skip_background_review=True` cho cron sessions (không có "human in the
loop" để hưởng lợi từ review, và mỗi event tốn ~30K token).

**Hỏi gì**: 3 prompt cố định — `_MEMORY_REVIEW_PROMPT`, `_SKILL_REVIEW_PROMPT`,
`_COMBINED_REVIEW_PROMPT` (`background_review.py:246-450`). Prompt skill dài,
chi tiết đến mức liệt kê **thứ tự ưu tiên hành động** (patch skill đang dùng
> patch umbrella có sẵn > thêm support file > tạo skill mới), **danh sách
skill được bảo vệ** (bundled/hub/pinned/user-owned — "being in play does not
make one yours to edit"), và **danh sách KHÔNG được lưu** (lỗi do môi trường
thiếu cấu hình, phủ định về công cụ "X không hoạt động", lỗi tạm thời đã tự
hết, tường trình một-lần, và đặc biệt: **không viết lại các lần thử thất bại
thành "quy trình đáng tin"** khi phiên kết thúc mà chưa tìm ra cách nào chạy
được).

**Ghi ở đâu**: cùng `memory` tool + `skill_manage` tool như agent chính,
nhưng bị **whitelist tool runtime** giới hạn chỉ còn `memory` + `skills`
toolset (`background_review.py:1149-1163`, dùng
`set_thread_tool_whitelist`) — mọi tool khác bị deny ngay tại dispatch, kể cả
nếu model cố gọi. Provenance được đánh dấu qua ContextVar
(`tools/skill_provenance.py`) `set_current_write_origin("background_review")`
để `skill_manage create` biết gọi `mark_agent_created`.

**Cache**: fork dùng đúng model/provider/base_url/credential của agent
chính → cache prefix ấm (replay full conversation, đọc rẻ). Nếu route review
sang model khác (`auxiliary.background_review.{provider,model}`), cache chắc
chắn lạnh trên model đó → thay vì replay full transcript (ghi lạnh mọi
token), code replay một **digest rút gọn** — chính sách 1 câu:
"Same model -> full replay; different model -> digest."

### 2.6. Skill — định dạng, linter vs validator, index vào prompt, telemetry

**Định dạng SKILL.md**: fence YAML `---...---` ở đầu file, parse bởi
`parse_frontmatter()` (`agent/skill_utils.py:175-221`, dùng `yaml.safe_load`
với fallback key:value nếu YAML lỗi). Có xử lý BOM UTF-8 đầu file (Windows
editor) — thiếu xử lý này thì cả frontmatter (name, description, platforms
gating...) biến mất im lặng.

**Validator (hard blocker, tools/skill_manager_tool.py:566-616,
`_validate_frontmatter`)**: fence phải đóng, phải là YAML mapping, phải có
`name` + `description`, `description` ≤ `MAX_DESCRIPTION_LENGTH=1024`, và
**chỉ khi tạo skill mới** (`new_skill=True`) description phải ≤
`SKILL_PROMPT_DESC_LIMIT=60` ký tự — vì index trong prompt cắt cứng ở 60 ký
tự, quá giới hạn thì "silently cut and never routes". Body sau frontmatter
không được rỗng. Ngoài ra `_validate_content_size` chặn
`MAX_SKILL_CONTENT_CHARS = 100_000` (~36K token).

**Linter (advisory, tools/skill_linter.py:1-25)**: nói rõ ngay đầu file nó là
"softer, broader companion" của validator — validator là non-negotiable
blocker khi tạo/sửa, linter chỉ **advisory**, encode các quy ước
CONTRIBUTING.md "HARDLINE" (không dùng `grep/cat/sed/find` trong prose mà
phải nói tên native tool, phải có author/license/metadata, `name` khớp tên
thư mục, link `references/` không được lủng lẳng, không dùng từ marketing,
`platforms:` gating đúng chỗ). "The create-path surfaces them as guidance,
never as a hard reject."

**Index vào prompt (tier nào)**: **tầng volatile**, đặt SAU cùng, có lý do
kỹ thuật rõ (`system_prompt.py:803-818`): nếu để index skill ở tầng stable,
mỗi lần thêm/sửa skill sẽ làm hỏng cache của toàn bộ stable prefix; đặt ở
volatile — ngay trước memory/timestamp — thì chỉ phần cuối bị invalidate.

**Telemetry (`tools/skill_usage.py`)**: sidecar JSON
`~/.hermes/skills/.usage.json`, **không nhúng vào frontmatter** (tách vận
hành khỏi nội dung do người dùng viết, tránh xung đột merge với bundled/hub
skill). Đếm `use_count` (bump khi `skill_view`), `view_count`,
`patch_count`, `last_activity_at`. Curator đọc `latest_activity_at()` để
quyết định chuyển trạng thái `active → stale (>stale_after_days) → archived
(>archive_after_days)`, trừ skill `pinned`. Mọi bump là best-effort (lỗi chỉ
log DEBUG, không làm hỏng tool call chính).

### 2.7. `write_approval` — vì sao cần cổng phê duyệt

`tools/write_approval.py:1-40`. Lý do nêu ngay: 2 kho ghi bền
(memory nhỏ ~200 ký tự, skill có thể 10-100KB) đến từ **2 nguồn khác nhau**:
`foreground` (user đang ngồi xem) và `background_review` (fork tự quyết định
lưu gì **không có ai giám sát trực tiếp**) — "the source of the 'wrong
assumptions' users complained about" (dòng 15). Đây trực tiếp trả lời "vì
sao ghi memory/skill cần cổng phê duyệt": vì self-improvement loop TỰ QUYẾT
ĐỊNH những gì đáng nhớ, và người dùng cần một cách để **không tin tưởng mù
quáng** vào phán đoán đó.

- Mặc định `write_approval: false` (ghi tự do — hành vi cũ). Bật `true` →
  memory foreground CLI **prompt inline**; mọi trường hợp khác (skill vì
  quá to để đọc lướt giữa loop, background-origin vì daemon thread không
  block được lên prompt tương tác, gateway vì không có kênh inline) đều
  **stage** vào `<HERMES_HOME>/pending/{memory,skills}/<id>.json`, chờ user
  duyệt qua CLI/gateway/dashboard.
- `evaluate_gate()` trả về đúng 1 trong 3: `allow` / `blocked` (user từ chối
  prompt inline) / `stage`.
- **Cố tình không có trạng thái "khoá toàn bộ ghi"** — muốn tắt hẳn 1
  subsystem thì dùng flag riêng của nó (`memory.memory_enabled: false`),
  write_approval chỉ là gate phê duyệt, không phải kill switch.

### 2.8. Bảng issue/PR trong docstring (trong các file đọc)

| # | File:dòng | Bài học rút ra |
|---|---|---|
| `#26045` | `memory_tool.py:110,760` | Không bao giờ ghi đè full file nếu chưa chắc đã đọc được nội dung mới nhất — "drift" (nội dung không round-trip qua parser) hoặc entry to hơn char-limit → refuse write, backup `.bak.<ts>`, để user tự hoà giải. Mất dữ liệu im lặng là lỗi tệ hơn refuse. |
| `#42405` | `memory_tool.py:162-201,705` | Vòng lặp "add thất bại vì đầy → model tự sửa → retry" phải có **giới hạn 3 lần/turn**, quá thì trả kết quả *terminal* để model dừng và trả lời user — lỗi ghi ký ức không bao giờ được chặn câu trả lời chính. |
| `#43412` / `#49466` | `memory_tool.py:1036,1119` | Thông báo lỗi khi `old_text` không khớp entry nào phải đủ chi tiết để model tự sửa ngay trong turn, tránh "dead-end error". |
| `#10878`/PR `#10888` | `memory_tool.py:772` | Bug matching/dedup từng làm 1 entry bị lặp vĩnh viễn — dedupe phải ổn định qua các lần load. |
| `#19434` | `session_search_tool.py:53,289,788` | Corpus tự động (cron) khối lượng lớn phải bị **demote, không exclude**, khỏi kết quả tìm kiếm — nếu không, lịch sử hội thoại thật của user bị cron "chôn". |
| `#85756` | `session_search_tool.py:494,833` | Sau `/new`/reset, lineage cũ phải **vẫn tìm được** nếu nó chưa thật sự nạp vào live context — nếu ẩn theo lineage một cách ngây thơ, "gateway recall goes blind after every /new". |
| `#72626` | `system_prompt.py:955` | Failover cache-on provider giữa turn cũng phải rebuild tầng stable — path rebuild không chỉ có 1 chỗ (compaction), phải cover mọi đường agent nhận lại 1 stored prompt. |
| `#54937` (layer 2) | `background_review.py:1150` | Hard-code toolset `["memory","skills"]` cho review fork từng vô hiệu hoá cờ `memory_enabled: false` của profile — luôn kiểm tra lại cờ cấu hình khi build whitelist, đừng hard-code danh sách tool. |
| `#87250` | `background_review.py:105,766,1197` | Phải snapshot usage/token của fork **trước** khi unregister/close, đặt trong `finally` — nếu không, 1 fork raise exception giữa chừng vẫn tiêu token nhưng không được tính vào billing của session cha. |
| `#14944` | `background_review.py:497,1233` | Không re-surface review work đã xử lý như việc mới — cần đánh dấu đã xử lý để tránh double-processing. |
| PR `#20238` (JabberELF), PR `#26419` (yoniebans) | `session_search_tool.py:29-31` | `session_search` từng có nhánh tóm tắt bằng LLM; bản hợp nhất hiện tại **bỏ hẳn nhánh đó** để giữ đúng "0 LLM cost" — một tính năng "tiện" (LLM tóm tắt) có thể bị rút lại khi nó phá vỡ một bất biến kiến trúc quan trọng hơn (chi phí xác định). |

---

## 3. Bài học (tổng hợp, tách khỏi chi tiết Hermes)

1. **Đông cứng ("frozen snapshot") là kỹ thuật, không phải thiếu sót**: bất
   cứ nội dung nào lặp lại mỗi turn trong system prompt (memory, skill index)
   nên chỉ đọc lại khi có sự kiện rebuild prompt rõ ràng (ở đây là
   compaction), không phải mỗi lần ghi — vì mục tiêu số 1 là giữ prefix cache
   cho provider tính phí theo cache-hit.
2. **Tách "ghi bền" khỏi "vào prompt ngay"**: một tool ghi xong vẫn phải trả
   `success=True` dựa trên *live state*, còn thứ vào prompt là *snapshot* —
   hai đường dữ liệu tách biệt tránh việc user tưởng model "quên" cái vừa lưu.
3. **0-cost retrieval là một tính năng cần bảo vệ, không phải mặc định**:
   `session_search` từng có nhánh LLM và bị loại bỏ khi hợp nhất — vì chi phí
   không xác định (mỗi lần gọi tốn 1 lần LLM) tệ hơn độ chính xác cận trên
   mà LLM-tóm-tắt mang lại.
4. **Provenance là điều kiện tiên quyết cho autonomy có giới hạn**: curator
   / background_review chỉ được phép sửa cái *chính nó tạo ra*
   (`is_agent_created`), việc này chỉ khả thi vì có 1 ContextVar đơn giản
   (`skill_provenance.py`, 78 dòng) đánh dấu nguồn gốc mọi write — không cần
   heuristic phức tạp.
5. **Never delete, only archive, always snapshot-before-mutate**: mọi hành
   động tự động có khả năng phá dữ liệu (curator consolidate) phải đi kèm
   tar.gz trước khi chạy + giới hạn hành động phá hoại tối đa là "archive"
   (phục hồi được), không phải "delete".
6. **Approval gate tách khỏi enable/disable**: `write_approval` không phải
   kill-switch — nó là "hãy cho tôi xem trước khi tin", một trục hoàn toàn
   khác với "tắt tính năng". Hai khái niệm không nên gộp vào 1 cờ.
7. **Autonomous write luôn có giá (token) và phải có ngân sách rõ**: fork
   review không chạy mỗi turn mà theo nudge-interval (10 turn) chính vì chi
   phí ~30K token/lần đã được đo và ghi thành hằng số trong code, không phải
   cảm tính.
8. **Giới hạn theo ký tự (không phải token) cho nội dung nhỏ, tự viết**: khi
   nội dung do model tự tóm tắt/viết (không phải dữ liệu bên ngoài), giới
   hạn ký tự (model-independent) đơn giản và đủ dùng hơn đếm token.

---

## 4. Port được gì — map cụ thể sang Stock_Massive

**Quan trọng nhất, đọc trước khi port bất cứ gì**: `contract.py` (đọc trực
tiếp, `apps/api/src/agent/prompt/contract.py:9-24`) tuyên bố một bất biến mà
toàn bộ mô hình MEMORY.md/USER.md của Hermes VI PHẠM theo thiết kế:

> "Nothing but five typed values can reach the prompt... There is no string
> field, so there is no hole a figure, a Watchlist entry, a tool result or
> user prose could be poured into."

Hermes injects đúng loại nội dung này (free-text do user/model viết) vào
prompt, chỉ giảm nhẹ rủi ro bằng quét mẫu tấn công lúc snapshot
(`_sanitize_entries_for_snapshot`). Stock_Massive đã chọn triết lý ngược lại
— và **`_assert_no_formatting_hole`** khiến việc thêm 1 block memory tự do vào
`render()` là một thay đổi Contract cần review + Capability Probe, không thể
làm "tiện tay". Vì vậy khuyến nghị port theo hướng **giữ contract đóng**, đưa
ký ức vào qua **tool gọi tường minh** — đúng con đường Stock_Massive đã đi
với `apps/api/src/agent/tools/knowledge.py` — chứ không đưa vào theo hướng
snapshot-vào-prompt của Hermes.

| Cơ chế Hermes | Port thế nào | File đích |
|---|---|---|
| `session_search` (0-LLM-cost, FTS5, adaptive/bookend) | **Port tinh thần, không port cơ chế**: thêm 1 method kiểu `AgentPersistence.search_messages(user_id, query, ...)` dùng Postgres FTS/`tsv` đã có sẵn kiểu dùng trong `knowledge.py:126-160` (`websearch_to_tsquery`, `immutable_unaccent`), áp lên `agent_message` join `agent_thread.user_id`; trả về kèm N message trước/sau (bookend) như `get_anchored_view`. Đây là retrieval xác định, 0 LLM — khớp thẳng triết lý hiện có của knowledge.py. | `apps/api/src/agent/persistence.py` (method mới), có thể expose qua 1 tool mới `search_my_threads` tương tự `KnowledgeTools` |
| `remember_fact`/`recall_facts` — **đã tồn tại**, chính là bản Stock_Massive của MEMORY.md + session_search hợp nhất thành 1 tool tường minh, có `source_url`/`as_of`/`claim_class="external_claim"` — kỷ luật hơn Hermes (Hermes không gắn nguồn cho MEMORY.md). | Mở rộng, không viết lại: thêm 1 loại tool tương tự cho **hồ sơ người dùng** (khẩu vị rủi ro, mã hay hỏi, watchlist) — gọi là `remember_preference`/`recall_preferences`, cùng khuôn `claim_class` nhưng có thể đặt `claim_class="user_preference"` để phân biệt với external claim. | `apps/api/src/agent/tools/knowledge.py` (mở rộng) hoặc file mới `preferences.py` cùng thư mục |
| Char-limit theo ký tự (2200/1375), không theo token | Áp dụng cho MAX_BODY_CHARS-kiểu field mới nếu thêm bảng preference — đã có tiền lệ đúng (`MAX_TITLE_CHARS=240`, `MAX_BODY_CHARS=4000` trong `knowledge.py:21-22`) | giữ nguyên convention hiện có |
| `write_origin` ContextVar (`skill_provenance.py`) | Nếu **sau này** có bất kỳ job nền nào tự ghi `agent_knowledge` (hiện KHÔNG có), thêm cột `write_origin` (`foreground`/`background`) vào `AgentKnowledge` để tách rõ ai ghi — tiền đề bắt buộc trước khi cho phép bất kỳ auto-write nào. | bảng `agent_knowledge` (cột mới, migration Alembic) — **chỉ khi** có nhu cầu auto-write thật, hiện tại YAGNI |
| `write_approval` gate | Cùng lý do trên: chỉ cần khi có auto-write. Thiết kế 3-trạng-thái (`allow/blocked/stage`) là mẫu tốt để tái dùng nếu/khi Stock_Massive thêm 1 vòng tự-học nào cho `agent_knowledge`. | mới, hoãn tới khi cần |
| Curator snapshot-before-mutate + archive-never-delete | Nguyên tắc chung áp dụng ngay cho **bất kỳ** thao tác xoá dữ liệu agent nào (ví dụ `delete_thread` ở `persistence.py:570-585`) — xem xét đổi "xoá cứng" thành "archived=true" nếu chưa có (bảng `agent_thread` — theo `session-storage.md` Hermes có cột `archived`/`pinned` y hệt nhu cầu này). | `apps/api/src/agent/persistence.py:_delete_thread` — xem lại có nên archive thay vì hard-delete |
| Bảng cần thêm nếu port sâu | 1) cột `archived: bool` trên `agent_thread` (nếu chưa có, cần đọc model để xác nhận — không có trong watch list task); 2) bảng `agent_knowledge_usage` (sidecar kiểu `.usage.json`) **chỉ nếu** thêm lifecycle active/stale cho facts — hiện tại `recall_facts` đã giới hạn 5 kết quả gần nhất theo rank, chưa cần lifecycle. | migration mới, không tạo trước khi có nhu cầu cụ thể |

---

## 5. Không port gì + vì sao

- **MEMORY.md/USER.md dạng snapshot-vào-system-prompt**: xung đột trực tiếp
  với bất biến "no formatting hole" của `contract.py`. Đưa văn bản tự do
  (do model hoặc user viết) vào prompt là chính xác cái lỗ mà thiết kế hiện
  tại cố tình bịt.
- **Skill system (SKILL.md, linter/validator, skill index tier)**: không có
  khái niệm tương đương trong Stock_Massive — tool catalog là hợp đồng cố
  định, có version (`tool_catalog_version`), không phải thư viện tự-viết-lại
  được. Thêm "skill" nghĩa là cho phép nội dung do agent tự sinh trở thành
  một phần điều khiển hành vi — lại đúng cái lỗ contract.py cấm.
- **`background_review` (fork agent sau mỗi N turn để tự quyết định lưu
  gì)**: đây là một "second call" mà không có gì đo được độ chính xác của nó,
  đúng cái `contract.py` docstring nói thẳng ADR-0015 từ chối ("V1 adds no
  router model"). Một fork tự viết vào `agent_knowledge` mà không ai chấm là
  đúng loại rủi ro tài liệu dự án đang chủ động tránh.
- **Curator consolidation (fork LLM gộp/rename skill)**: không có gì để gộp
  vì không có skill system — moot.
- **Threat-pattern scanning tại thời điểm snapshot**: chỉ cần thiết khi có
  free-text tự động vào prompt; vì khuyến nghị không làm vậy (mục 4), cơ chế
  này không có chỗ áp dụng ngay — nhưng **ghi nhớ lại nếu tương lai có tầng
  volatile mới** thì đây là mẫu chống injection cần xem lại.
- **`learning_graph.py`/`learning_mutations.py` (đồ thị "journey" cho
  desktop GUI)**: đặc thù UI riêng của Hermes desktop app, không liên quan
  kiến trúc ký ức lõi, không port.

---

## 6. Câu hỏi chưa giải quyết

1. **Thread có thuộc nhiều user không?** Đã xác nhận trong
   `persistence.py:108-119,342-364`: `AgentThread.user_id` là **single
   owner** — mọi query (`list_threads`, `read_thread`, `update_thread`,
   `delete_thread`) đều `WHERE AgentThread.user_id == user_id`.
   `AgentMessage` **không có** `user_id` riêng và có comment tường minh
   (`persistence.py:404-413`): *"agent_message has no user_id and should not
   grow one"* — join qua `AgentThread` để lấy owner. => **Hiện tại KHÔNG có
   multi-user thread**, khác hẳn Hermes gateway group-chat (nhiều platform
   user cùng 1 `session_id`). Câu hỏi mở: roadmap có tính năng chia sẻ thread
   (ví dụ cố vấn xem cùng khách hàng) không? Nếu có, toàn bộ khuyến nghị "1
   user_id = 1 profile" ở mục 4 cần thiết kế lại.
2. **`agent_knowledge.user_id` cho phép NULL** — điều kiện query trong
   `knowledge.py:145` là `knowledge.user_id = :user_id OR knowledge.user_id
   IS NULL`, nghĩa là có khái niệm "fact toàn cục" mọi user đều recall được.
   Chưa rõ: ai được phép ghi fact `user_id=NULL` (route nào gọi
   `remember_fact` không set `symbol`/`user_id`?), và có rủi ro leak thông
   tin cụ thể của 1 user sang user khác qua field global này không?
3. **Nếu thêm tool "ghi hồ sơ người dùng"** (risk_appetite, watchlist) — có
   cần cổng phê duyệt kiểu `write_approval` ngay từ đầu, hay để mặc định ghi
   tự do như Hermes (`write_approval: false` default)? Đối tượng dùng là nhà
   đầu tư nhỏ lẻ — ghi sai khẩu vị rủi ro có thể ảnh hưởng tới cách agent đưa
   khuyến nghị; cần quyết định của product owner, không tự suy ra được từ
   code.
4. **Giới hạn kích thước cho 1 "profile" mới** (nếu thêm) — Hermes chọn 1375
   ký tự cho USER.md dựa trên ngân sách token của họ; Stock_Massive chưa có
   số tương đương — cần benchmark thực tế theo token budget của Contract V1
   hiện tại (237 dòng static text) trước khi chốt.
5. **`recall_facts` hiện giới hạn `MAX_FACTS=5`, `MAX_RECALLED_BODY_CHARS=900`**
   — chưa rõ đã đủ cho nhu cầu "kết luận phân tích cũ" hay cần adaptive-detail
   kiểu Hermes (kết quả top đầy đủ, kết quả sau rút gọn) khi số lượng fact
   một user tích lũy tăng lên — cần dữ liệu thực tế mới đánh giá được.

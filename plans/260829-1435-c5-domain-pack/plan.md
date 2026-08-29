---
title: "C5 Domain Pack And Progressive Instruction"
description: "Prompt chỉ mang playbook cần cho câu hỏi: domain chứng khoán thành một DomainPack có version, web+memory là core, và body domain nạp theo tool path thay vì nạp mọi Turn."
status: completed
priority: P1
effort: "6 phase · ~26h"
tags: [harness, prompt, domain-pack, toolsets, context, contract]
created: 2026-08-29
relatedTo: [260829-1349-c1-search-and-evidence]
---

# Plan: C5 — Domain pack + progressive instruction

Roadmap authority: `docs/roadmap.md` §3 / **C5** (`docs/roadmap.md:215-238`). Trong
đồ thị phụ thuộc §6 (`docs/roadmap.md:436-450`), C5 là **gốc của nhánh thứ hai**:
`C5 ─▶ C6` và `C5 ─▶ C8`, và C4 cần C5 vì "pack quyết định Golden Set". Nó không
nằm sau C1 — hai nhánh chạy song song, và §6 nói thẳng hai nhóm owner file không
giao nhau. Mục [Luật phối hợp hai worktree](#luật-phối-hợp-hai-worktree) dưới đây
đo lại câu đó và tìm thấy **bốn file giao nhau**, nên nó không còn đúng nguyên văn.

Nguồn học: OpenCode *progressive instruction loading*
(`docs/opencode/opencode-lessons-for-stock-massive.md:75-84`) — tách catalog nhỏ
khỏi body chi tiết, nạp body khi intent hoặc tool path cần; acceptance signal của
chính nó là *"giảm input tokens mà Golden Question Set không giảm
grounding/completeness; không dựa vào subjective prompt review"*.

## Hợp đồng mở phase (chốt với user 2026-08-29)

- **Outcome.** Prompt chỉ mang playbook cần cho câu hỏi. Domain chứng khoán thành
  `DomainPack("vn-equity", version)` khai `prompt_sections · toolsets · universe ·
  study_names`; `web` + `memory` là core. Đổi pack không sửa `loop.py`. Catalog
  ngắn luôn nạp, body nạp theo intent/tool path.
- **Constraints.** `CHAT_TOOLSETS` vẫn là tuple **viết ra**, sinh từ pack,
  `AgentLoop(toolsets=None)` mặc định đúng · `render()` vẫn typed,
  `_assert_no_formatting_hole` pass · ký ức vẫn qua tool, không free-text vào
  system prompt · refusal vocabulary theo pack đồng bộ hai bên · **không
  migration, không đụng `src/stocks/*`, không đụng bundle nội bộ `signals`/
  `studies`** ngoài việc pack tham chiếu chúng theo tên.
- **Non-goals.** Domain thứ hai (C8) · tenant/entitlement (C6) · prune/cache (C2)
  · sửa nội dung playbook chứng khoán · sửa `loop.py` ngoài đường nhận pack.
- **Acceptance.** (1) test: đổi pack không sửa `loop.py`, contract test giữ
  `CHAT_TOOLSETS` đồng bộ; (2) input token/Turn giảm đo trên artifact
  `apps/api/golden/` của C1 phase 02 mà Golden Set không giảm; (3) năm cổng xanh.

## Mười dữ kiện đo lại

Đo trên code và trên đĩa 2026-08-29, **trước** khi viết một dòng plan nào. Bốn
trong mười cái đổi hình dạng của phase.

| # | Roadmap / CLAUDE.md viết | Đo lại |
|---|---|---|
| 1 | *"Lane chat chọn ba bundle `web` + `memory` + `signals` = 8 tool"* (`CLAUDE.md:242`) | **Bốn bundle, 12 tool.** `CHAT_TOOLSETS = ("web", "memory", "signals", "studies")` (`toolsets.py:98`), pin lại ở `tests/test_agent_capability_contract.py:210`, và chính prompt nói *"Bạn có mười hai công cụ"* (`prompt/sections.py:169`). |
| 2 | *"`signals`+`studies` hardcode là chứng khoán"* | Đúng, nhưng hardcode nằm ở **một dòng literal** (`toolsets.py:98`) chứ không rải khắp loop. `loop.py:862` chỉ đọc lại literal đó. Việc là dựng declaration, không phải gỡ hardcode rải rác. |
| 3 | *"stub `src/agent/domain/` đã có"* | **Không còn trên đĩa.** `ls src/agent/` không có `domain`. Dựng lại từ đầu. |
| 4 | C6 *"`ToolContext.tenant_id`"* | `grep -rni tenant src/` = **0**. C6 chưa bắt đầu; không kéo tenant vào bất kỳ chữ ký nào của C5. |
| 5 | *"catalog ngắn luôn nạp, body nạp theo intent/tool path"* | Prompt được `render()` **một lần cho cả Turn**, ở `loop.py:929`, **trước** vòng round bắt đầu ở `loop.py:931`. Nên "nạp theo tool path" không thể là "render lại prompt ở round sau" nếu không đụng vào biên cache. Cơ chế đã có sẵn cho đúng việc này: **system note dán thêm mỗi call** (`loop.py:1252-1263`), đúng mẫu `SIGNAL_DESK_NOTE` (`loop.py:313-338`). |
| 6 | C2 *"`cache_control` chưa bật"* | Đúng: `LLMRoute.prompt_cache_control = False` (`core/llm/config.py:151`), lấy từ `Settings.llm_prompt_cache_control_enabled = False` (`core/config.py:129`). Và `cache_key()` (`prompt/contract.py:162`) **không có caller runtime nào** — chỉ `tests/test_agent_prompt.py:155-166` gọi. Kinh tế cache **chưa binding hôm nay**; nó là của C2. |
| 7 | `reasons.py` *"một mã không có câu sẽ fail `tests/test_envelope.py`"* (`alpha/reasons.py:13-14`) | **File test đó không còn** (rip-out). Guard phía Python đã chết; docstring vẫn viện dẫn nó. Guard phía web **còn sống và mạnh hơn**: `apps/web/src/lib/signal-issues.test.ts:20-36` đọc thẳng file enum Python qua đường `../api/src/stocks/signals/issues.py`. |
| 8 | — | Đo tập mã refusal 2026-08-29: enum `SignalIssue` **42 member** (`stocks/signals/issues.py:19`), `alpha/reasons.py` phủ **42/42**, `apps/web/src/lib/signal-issues.ts` phủ **42/42**. Đang khớp — nhưng chỉ một chiều có test giữ. |
| 9 | *"C1 chạy ở worktree khác"* | `git worktree list` trả **đúng một cây**. `apps/api/golden/` và `apps/api/tests/golden/` đang **untracked trong chính cây này**, tạo lúc 14:41 hôm nay, và `Makefile` đã mang `golden-run` (`:85`) + `golden-grade` (`:90`). Hai nhánh song song hiện là ước định, chưa là sự thật vật lý. |
| 10 | *"đo trên artifact C1 phase 02"* | `apps/api/golden/artifacts/` **rỗng** (chỉ `.gitkeep`). Corpus `web_first.json` có **20 case, 4 family** — `fact_as_of`, `multi_source_synthesis`, `conflicting_or_missing`, `adversarial` — **không có family nào hỏi store**. Nó đo được phần *tiết kiệm*, gần như không đo được *hồi quy chất lượng* của lượt chạm store. |

## Số học: tiết kiệm được bao nhiêu, và ở đâu

Đo bằng chính `messages.estimate_tokens` trên từng section (`prompt/sections.py`):

| Section | Token ước lượng | Phân loại |
|---|---|---|
| `mission` | 189 | core |
| `invariants` | 1.031 | **core toàn bộ** — xem Luật 1 |
| `honesty` | 700 | tách: ~350 core / ~350 body |
| `tools` | 1.978 | tách: ~1.400 core / ~580 body |
| `untrusted` | 876 | **core toàn bộ** — xem Luật 1 |
| `memory` | 300 | core |
| `style` | 273 | core |
| `context` | 151 | core |
| **Tổng** | **5.498** | body dự kiến **800–950** |

Một Turn thật đo ở C1 là **9.337 input token** (`260829-1349/phase-04`), nên system
prompt là **~59% input của một Turn**. Body 800–950 token là **~9–10% input mỗi
call** cho lượt không chạm domain, và một lượt tốn tới 5 call.

**Nói thẳng độ lớn ngay đây để gate không đặt trên ảo tưởng:** C5 một mình tiết
kiệm một chữ số phần trăm. Giá trị lớn hơn của nó là **cấu trúc**: khi có pack thứ
hai (C8), số tiết kiệm là *toàn bộ body của pack không được chọn*, và không có C5
thì C8 không có chỗ bám. Gate của phase 06 viết theo con số đo được, không theo
con số mong muốn.

## Kiến trúc: hai tầng, ba trigger, một note dính

```
       ┌─ core sections ─────────────────────────────┐  luôn nạp, byte-identical
       │ mission · invariants · honesty(core) ·      │  → prefix() không đổi
       │ tools(catalog + luật dùng chung) ·          │  → biên cache không đổi
       │ untrusted · memory · style · context        │
       └─────────────────────────────────────────────┘
                          │
                          │  trigger nào bật thì dán, và dính tới cuối Turn
                          ▼
       ┌─ pack body: vn-equity ──────────────────────┐  system note mỗi call
       │ cơ chế store · Signal Field · Universe ·    │  (mẫu SIGNAL_DESK_NOTE)
       │ refusal · ranh giới get_field ↔ run_study  │
       └─────────────────────────────────────────────┘
```

**Ba trigger, tất cả deterministic, tất cả miễn phí — không có bộ phân loại
intent, không có lượt model nào thêm:**

| Trigger | Đọc ở đâu | Vì sao |
|---|---|---|
| `TurnMode == "signal_desk"` | `request.mode` (`loop.py:614`) | Mode là *lời hứa* Turn sẽ ra một desk (`loop.py:305-311`) — tool domain là chắc chắn, nạp từ round 1 |
| Lịch sử Thread có call domain | `request.history` (`loop.py:601`), `TranscriptTurn.tool_calls` | Câu hỏi tiếp ("còn VNM thì sao?") là chỗ hồi quy dễ xảy ra nhất, và nó đọc được không tốn gì |
| Round này model gọi một tool domain | `completion.tool_calls` ngay trước `loop.py:1058` | Chính lời gọi là tín hiệu intent, và body kịp cho phần *cần* nó: phần diễn giải kết quả |

Trigger thứ ba không tốn thêm round: body đi cùng call của round mà Turn đã trả
tiền rồi. Một bộ phân loại intent trước lượt LLM đầu **bị loại**: nó thêm một
failure mode (phân loại sai) để đổi lấy đúng một round đầu của những lượt đã chắc
chắn chạm domain — mà hai trigger đầu đã phủ phần lớn số đó.

### Ba luật cứng

**Luật 1 — Sàn an toàn không bao giờ nạp muộn.** `invariants` giữ **nguyên vẹn ở
core**, kể cả bốn đoạn nói bằng từ vựng thị trường (`prompt/sections.py:87-115`:
không ra chỉ thị hành động cho vị thế, luật bảng điều kiện). Câu chống bịa số
(`:145-153`) và cổng `check_price_claim` (`:318-329`) cũng **ở lại core**. Lý do
là failure mode: nếu một luật an toàn nằm trong body, thì mọi Turn không kích
trigger là một Turn chạy **không có** luật đó — và đó chính là các Turn trả lời
bằng trí nhớ, tức nhóm rủi ro cao nhất. Cắt token của sàn an toàn là cắt sai chỗ.

**Luật 2 — C5 hoãn *prose*, không hoãn *tool schema*.** Tập tool của một Turn được
resolve **một lần** ở `loop.py:908` qua `definitions.resolve_tool_surface`, và
identity của nó vào cache key của registry (`definitions.py:132-176`). Đổi tập
tool giữa Turn là đổi một contract của C3, không phải của C5. Catalog trong prompt
vẫn kể đủ mười hai tool.

**Luật 3 — Câu kích hoạt phải nằm trong catalog.** Câu *"Hỏi store trước khi hỏi
web, khi câu hỏi là về một mã"* (`prompt/sections.py:225-227`) là thứ **gây ra**
lời gọi tool domain. Đẩy nó xuống body tạo một deadlock: model không được bảo hãy
hỏi store → không gọi tool store → body không bao giờ nạp. Nó ở lại core, cùng với
danh mục tên tool và luật dùng chung (gộp lượt `:261-266`, không biết thì tra
`:241-244`, một câu trước khi tra `:278-281`).

### Ba câu hỏi hợp đồng, trả lời trước khi viết code

**1. Quyết định nạp body ở đâu, trước lượt LLM đầu hay sau tool call đầu?**
**Cả hai, và không lượt model nào thêm.** Trước lượt đầu: hai trigger đọc được từ
`request` (mode, history) — quyết ở `loop.py` ngay sau `render()` (`:929`), tức
trước round 0. Trong lượt: trigger thứ ba đọc `completion.tool_calls` trước khi
dispatch (`loop.py:1058`), và body có mặt từ call kế tiếp. Không có phân loại
intent bằng model, không có lượt "hỏi model xem đây là câu gì".

**2. `TurnMode="signal_desk"` có kéo section nào riêng không?** **Không.** Nó là
trigger nạp *chính body của pack*, không phải một section thứ hai. `SIGNAL_DESK_NOTE`
(`loop.py:334-338`) giữ nguyên và không gộp vào body: nó nói *Turn nào* đang ở
mode, còn body nói *luật của domain*. Trộn hai thứ đó là làm một note đúng cho một
Turn thành một luật đúng cho mọi Turn.

**3. `PROMPT_VERSION` có per-pack không?** **Không. Một prompt version, mỗi pack
một version riêng.** `PROMPT_VERSION` (`prompt/sections.py:29`) và `PROMPT_HASH`
(`contract.py:140`) là danh tính của **prose core** — thứ vào biên cache và vào
`cache_key` (`:162-172`). `DomainPack.version` là danh tính của body. Hệ quả phải
làm: `cache_key` nhận thêm **một tham số danh tính pack**, vì hai Turn cùng model,
cùng tool signature, khác pack **không** dùng chung được một prefix. Rẻ để làm
đúng hôm nay: `cache_key` chưa có caller runtime nào (dữ kiện 6).

### Cơ chế đã cân nhắc và bị loại

| Phương án | Vì sao loại |
|---|---|
| Render body **vào trong** system message (sau core, trước dòng runtime) | Làm được và giữ được `prefix()`, nhưng phải đổi chữ ký `render()`, phá thế precompute `_STATIC_TEXT` (`contract.py:120`), và đưa một quyết định runtime vào module cố ý không có runtime value nào (`sections.py:1-19`). Ghi lại ở đây như **đường di trú đã quyết trước** cho C2: khi `prompt_cache_control` bật, note ở đuôi trả giá đầy đủ mỗi call, và chỗ đúng của body là block thứ hai ngay sau core — C2 sở hữu quyết định đó, không phải C5 |
| Phân loại intent bằng keyword/regex trước lượt đầu | Thêm một failure mode (phân loại sai) đổi lấy một round; hai trigger rẻ đã phủ phần lớn |
| Phân loại intent bằng một lượt model rẻ | Vi phạm ràng buộc "không thêm lượt model"; và là C7, không phải C5 |
| Hoãn cả tool schema theo intent | Vi phạm Luật 2 |
| `agent/domain` giữ pack đang active bằng biến module | Chấp nhận **hôm nay** vì đúng một pack tồn tại, nhưng phải ghi giới hạn tại chỗ: C6 chọn pack theo tenant, tức lựa chọn phải chuyển vào Turn. Không dựng sẵn cơ chế cho việc chưa có (YAGNI), chỉ ghi biên |

## Ranh giới freeze — plan này CẦN amendment

`src/agent/*` chưa bao giờ freeze. Nhưng hai file plan này sửa nằm trong bảng
surface của `260829-0010-composer-attachments` (đã đóng 10/10) và của
`260829-1349-c1-search-and-evidence` (đang mở) — tiền lệ price-basis là *plan xong
thì surface đóng; file ngoài bảng cần amendment mới, không phải một dòng nới*.

Plan này **không đụng** `src/stocks/*` và **không sửa** file nào trong `apps/web/`.

**Bảng amendment C5 — phase 01 ghi vào `CLAUDE.md` trước dòng code đầu tiên:**

| Surface | Giới hạn |
|---|---|
| `src/agent/domain/*` (mới) | `DomainPack` + pack `vn-equity`; pack **tham chiếu** `signals`/`studies`/`universe`/Study theo tên hoặc theo symbol đã có, **không** định nghĩa lại cái nào |
| `src/agent/toolsets.py` | `CORE_TOOLSETS` + một cổng import-time buộc `CHAT_TOOLSETS` khớp core + pack; `CHAT_TOOLSETS` **vẫn là literal viết ra**, không sinh động |
| `src/agent/prompt/sections.py` | tách core ↔ body theo Luật 1–3; **không** viết lại nội dung playbook; bump `PROMPT_VERSION` |
| `src/agent/prompt/contract.py` | `render`/`prefix` chỉ dựng core; `cache_key` nhận danh tính pack; **không** đổi `_assert_no_formatting_hole`, không đổi `RuntimeContext` |
| `src/agent/loop.py` | **chỉ đường nhận pack**: một cờ per-Turn trên `_TurnState`, ba trigger, một note dính trong `_call`. **Không** đổi `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_TOOL_CALLS`, `SIGNAL_DESK_NOTE`, `plan_segments` |
| `src/alpha/reasons.py` | **chỉ docstring** trỏ lại guard còn sống; không thêm/bớt một mã refusal nào |
| `apps/api/tests/*` | test cho mọi surface trên; test mới **thêm ở cuối file**, không reflow test đang có |
| `docs/roadmap.md` · `CLAUDE.md` | §3 C5 và §Quy ước — **không** đụng §3 C1/C2 và không đụng Track S |

Bảng này **là** ranh giới. File ngoài bảng cần amendment mới, kể cả khi một phase
sau thấy nó tiện. `apps/api/golden/*` **không** trong bảng: nó thuộc C1, và C5
chỉ **chạy** nó và **đọc** artifact của nó.

## Luật phối hợp hai worktree

§6 roadmap nói C1–C3 và C5–C6 "không giao nhau về file". Đo lại: **giao nhau bốn
file** — `src/agent/prompt/sections.py`, `src/agent/loop.py`,
`apps/api/tests/test_agent_prompt.py`, `apps/api/tests/test_agent_loop.py` (cộng
`CLAUDE.md` và `docs/roadmap.md`). Sáu luật:

1. **`prompt/sections.py` thuộc C5.** C1 phase 04 chỉ *chèn thêm một section*
   (`260829-1349/phase-04`, Related Code Files). Khi C5 tách core ↔ body xong,
   C1 phase 04 **rebase** section đó vào cấu trúc mới — nó là luật dùng chung
   (gọi tool song song), nên chỗ của nó là **core**, không phải body.
2. **`PROMPT_VERSION` bump một lần ở nhánh merge sau.** Hai nhánh không được ghi
   **cùng một số**. Số đã chia trước: **C1 → `2.10.0`** (một section thêm), **C5
   → `3.0.0`** (prompt thành hai tầng — không so sánh được với 2.x, đúng luật major
   number đã ghi ở `sections.py:25-28`). Nhánh merge sau *nói lại* số cuối cùng
   thay vì giữ số của mình: C1 sau C5 thành `3.1.0`; C5 sau C1 giữ `3.0.0`.
   `tests/test_agent_prompt.py:79` (`assert PROMPT_VERSION == "2.9.0"`) là **một
   dòng cả hai nhánh cùng sửa** — xung đột chắc chắn, giải bằng luật này, và
   docstring của test nhận thêm đoạn của cả hai.
3. **`loop.py` giao nhau nhưng khác hunk.** C1 phase 04 sửa hằng số ở đầu file
   (`loop.py:293`); C5 sửa `_run`/`_call` (`:929-1290`). Merge sạch nếu không ai
   reflow. Không nhánh nào được đổi hằng số của nhánh kia.
4. **Thứ tự phase C5 đã xếp để giảm chồng:** pack model + `toolsets` (không đụng
   `sections.py`) → refusal vocabulary → **tách section muộn** → nạp theo tool
   path → đo. Phase đo **chờ** artifact C1 phase 02; chưa có thì gate ghi
   *"chờ đo"* và code vẫn merge được nhờ contract test + transcript test.
5. **`apps/api/golden/*` chỉ đọc.** C5 không sửa corpus, runner, grader,
   `Makefile`. Nếu C5 cần một family câu hỏi store-first, đó là **yêu cầu gửi
   C1/C4**, không phải một commit của C5 (xem Câu hỏi chưa giải quyết #1).
6. **Test mới thêm ở cuối file.** Cả hai nhánh sửa `test_agent_prompt.py` và
   `test_agent_loop.py`; thêm ở cuối là cách rẻ nhất để git merge không phải đoán.

## Phases

| # | Phase | Vùng | Dep | Trạng thái |
|---|---|---|---|---|
| 01 | [Ranh giới, amendment, và số đo gốc của prompt](./phase-01-boundary-and-prompt-baseline.md) | docs | — | done |
| 02 | [`DomainPack` và `CHAT_TOOLSETS` sinh từ pack](./phase-02-domain-pack-and-toolset-selection.md) | api | 01 | done |
| 03 | [Refusal vocabulary theo pack, hai chiều có guard](./phase-03-refusal-vocabulary-per-pack.md) | api | 02 | done |
| 04 | [Tách section core khỏi body của pack](./phase-04-split-core-sections-from-pack-body.md) | api | 02 | done |
| 05 | [Nạp body theo tool path, dính tới cuối Turn](./phase-05-load-body-on-tool-path.md) | api | 04 | done |
| 06 | [Nghiệm thu bằng số và đóng phase](./phase-06-measure-and-graduate.md) | api + docs | 03, 05 | done |

Phase 03 độc lập với 04–05 sau khi 02 xong → chạy song song được **trong cùng
worktree** vì không giao file (03 chạm `alpha/reasons.py` + test; 04 chạm
`prompt/*`).

## Success Criteria

- [x] **Gate** — đổi pack (thêm một pack thứ hai trong test, đổi `ACTIVE_PACK`)
      không sửa một dòng nào của `loop.py`: test chứng minh bằng cách bật pack
      giả và quan sát `CHAT_TOOLSETS`, tool surface và body đổi theo
- [x] **Gate** — contract test giữ `CHAT_TOOLSETS` đồng bộ với `CORE_TOOLSETS +
      pack.toolsets`, và cổng import-time raise khi lệch
- [x] **Gate** — `render()` vẫn chỉ nhận `RuntimeContext`;
      `_assert_no_formatting_hole` pass trên **cả** core lẫn body của pack
- [x] **Gate** — prefix vẫn byte-identical giữa hai Turn không liên quan
      (`test_agent_prompt.py:38-46` xanh nguyên văn)
- [x] **Gate** — không luật an toàn nào rơi xuống body: test liệt kê từng câu
      thuộc sàn an toàn và khẳng định nó ở trong `prefix()`
- [x] **Gate** — không câu prose nào **mất** trong lúc tách: test khẳng định mọi
      câu đang được test hiện tại pin vẫn có mặt ở core hoặc body
- [x] **Gate** — transcript test: lượt không chạm domain **không bao giờ** thấy
      body; lượt chạm domain thấy body từ call kế tiếp; lượt `signal_desk` và
      lượt tiếp nối một Thread đã chạm domain thấy body từ call đầu. Test tiếp
      nối dựng history **qua `history_of()`** trên `MessageRecord` thật — bản đầu
      dựng bằng tay và xanh trên một trigger chết trong production, xem
      `plans/reports/cook-260829-1717-c5-phases-04-05-06.md` §Code review H1
- [x] **Gate** — mọi mã `SignalIssue` có câu ở `alpha/reasons.py` (guard Python
      sống lại) và ở `apps/web/src/lib/signal-issues.ts` (guard web đang sống)
- [x] **Gate** — token của core prompt giảm **648** (6.097 → 5.449), đo bằng
      `messages.estimate_tokens`, deterministic, không tốn tiền. Gốc là 6.097 chứ
      không phải 5.498 — xem ghi chú nghiệm thu của phase 01
- [x] **Tín hiệu** — đo được **không tốn thêm đồng nào**: lượt C1
      `web-first-v1-final.json` chạy dưới `PROMPT_VERSION 3.0.0`, tức C5 đã sống.
      78 call / 20 case, 47 call core-only + 31 call core+body → net **−438
      token/call = 7,0%** input (bản đang ship: −376 = 6,0%). Suy ra từ cấu trúc
      call của **một** lượt, nên **không có confound C1**
- [~] **Tín hiệu** — grader C1: **3 finding mới đỏ, 1 xanh lại**, cả ba cái mới
      đi cùng đọc ít trang hơn. Nhóm không chạm domain `fetch_url` −15%, nhóm
      chạm domain ±0 — hướng khớp giả thuyết "đoạn prose đẩy đọc web đã xuống
      body", nhưng **n=20 không phân xử nổi**: −5 fetch do đúng hai case kéo, và
      hai lượt lệch nhau cả C5 lẫn C1 phase 05-08. Replay không cô lập được biến
      này. Phản ứng đã ghim ở `docs/roadmap.md` §C5, chưa kích hoạt
- [x] Bảng amendment C5 trong `CLAUDE.md` khớp tứ hợp file thật của sáu phase
- [x] Năm cổng xanh: `make test` + `make lint` (apps/api) · `pnpm type-check` /
      `lint` / `test` / `build` (apps/web)

## Câu hỏi chưa giải quyết

1. **Corpus không có câu hỏi store-first — nửa sai, đo lại 2026-08-29.**
   Đúng về đề bài, **sai về hành vi**: 11/20 case gọi tool domain
   (`list_fields`, `check_price_claim`, `get_field`, `run_study`). Nên corpus
   **có** đo lượt chạm domain, chỉ là tình cờ chứ không theo kỳ vọng. Giao C4,
   đã ghi vào checklist của nó. Nguyên văn câu hỏi cũ: `web_first.json` có 20
   case, 4 family, không family nào hỏi store — nên nó đo tiết kiệm tốt và đo hồi quy chất lượng
   của lượt chạm domain **gần như không được**. C5 bù bằng transcript test
   deterministic, nhưng đó là kiểm *cơ chế*, không phải kiểm *chất lượng câu trả
   lời*. Cần quyết: thêm ~5 case store-first vào corpus (owner C1/C4, không phải
   C5), hay chấp nhận nợ và ghi rõ?
2. **Một câu ghim trong `CLAUDE.md` chuyển xuống body.** *(User chốt
   2026-08-29: xuống body. `CLAUDE.md` §Quy ước đã viết lại.)* *"Số của store thắng số
   của web"* (`prompt/sections.py:141-143`, ghim ở `CLAUDE.md:252`) đi vào body
   theo lập luận: luật này chỉ **áp dụng được** sau khi đã đọc store, và đọc store
   chính là trigger nạp body — nên nó không bao giờ vắng mặt lúc cần. Lựa chọn
   khác là giữ ở core, nhưng viết lại nó cho trung tính là **sửa prose**, thứ
   phase 04 cấm. Cần user xác nhận vì nó động vào một câu đã ghim.
3. **Version của pack lấy ở đâu.** *(Chốt phase 02: cả hai — chuỗi viết tay
   `DomainPack.version` cho người đọc, hash trong `identity` cho cache.)* `DomainPack.version` là chuỗi viết tay như
   `PROMPT_VERSION`, hay hash của body như `contract_hash`? Đề xuất: **cả hai** —
   chuỗi viết tay để người đọc thấy, hash để một lần sửa prose quên bump vẫn void
   được cache. Chi phí là một hàm nhỏ; chốt ở phase 02.
4. **Bao giờ `agent/domain` được phép import `src/stocks/*`.** *(Giao C8
   2026-08-29, đã ghi vào checklist của nó.)* Hôm nay pack
   `vn-equity` phải import `build_universe` (`stocks/universe.py:208`) để khai
   `universe` bằng chính callable mà tool đang dùng (`agent/tools/signals.py:667`).
   C8 nói *"pack thứ hai không import `stocks/*`; lint chặn import chéo"*. Nghĩa
   là luật lint phải là **per-pack**, không phải per-package — cần quyết trước khi
   C8 mở, không phải trong C5.

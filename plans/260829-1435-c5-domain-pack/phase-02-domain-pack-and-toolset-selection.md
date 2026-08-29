---
phase: 2
title: "DomainPack và CHAT_TOOLSETS sinh từ pack"
status: done
priority: P1
effort: "5h"
dependencies: [1]
---

# Phase 2: `DomainPack` và `CHAT_TOOLSETS` sinh từ pack

## Overview

Dựng declaration: một `DomainPack` khai `name · version · toolsets ·
prompt_sections · universe · study_names · refusal_vocabulary`, và pack
`vn-equity` điền nó bằng đúng những thứ đã tồn tại — không định nghĩa lại tool
nào, không định nghĩa lại Study nào, không chép một mã chứng khoán nào.

Phase này **không đụng `prompt/sections.py`** (đó là phase 04) và **không đụng
`loop.py`** (đó là phase 05). Nó là phase rẻ nhất và là phase mà mọi phase sau
bám vào.

## Requirements

- Functional: `DomainPack` là dataclass frozen, không đọc settings, không mở
  session, không có side effect ngoài import.
- Functional: pack `vn-equity` khai `toolsets = ("signals", "studies")`,
  `study_names` khớp `studies.REGISTRY`, `universe` là **chính callable** tool
  đang dùng.
- Functional: `CORE_TOOLSETS = ("web", "memory")` ở `toolsets.py`.
- Functional: `CHAT_TOOLSETS` **vẫn là tuple literal viết ra**, và một cổng
  import-time raise khi nó lệch khỏi `CORE_TOOLSETS + pack.toolsets`.
- Functional: đổi pack không sửa `loop.py` — chứng minh bằng test dùng pack giả.
- Non-functional: **không** import vòng. `agent/domain` → `agent/toolsets` là
  chiều **cấm**; `toolsets` → `domain` là chiều cho phép.
- Non-functional: `prompt_sections` khai được nhưng **để rỗng** ở phase này;
  phase 04 điền. Một pack rỗng body phải chạy đúng như hôm nay.

## Architecture

### Hình dạng của `DomainPack`

```
src/agent/domain/
  __init__.py     ACTIVE_PACK, PACKS, active_pack()
  pack.py         DomainPack (dataclass frozen) + validate
  vn_equity.py    PACK = DomainPack(name="vn-equity", ...)
```

| Trường | Kiểu | Nguồn thật hôm nay |
|---|---|---|
| `name` | `str` | `"vn-equity"` |
| `version` | `str` | viết tay, kèm hash body — xem dưới |
| `toolsets` | `tuple[str, ...]` | `("signals", "studies")` — hai bundle domain ở `toolsets.py:56-81` |
| `prompt_sections` | `tuple[PromptSection, ...]` | **rỗng ở phase này**, phase 04 điền |
| `universe` | `Callable[[Session], Universe]` | `stocks.universe.build_universe` (`stocks/universe.py:208`) — chính hàm `agent/tools/signals.py:667` gọi |
| `study_names` | `tuple[str, ...]` | `("earnings_dislocation_screener", "entry_condition_review", "intraday_liquidity_profile", "volume_at_price")` — hằng `NAME` ở `studies/*.py:60,89,103,77` |
| `refusal_vocabulary` | `frozenset[str]` | mọi `SignalIssue` value (`stocks/signals/issues.py:19`) — phase 03 gắn guard |

**`universe` giữ callable, không giữ danh sách mã.** Danh sách mã đến từ
`Settings.universe_symbols` (`core/config.py:60`) qua `build_universe(session)`,
tức nó phụ thuộc cấu hình và DB. Một pack chép 30 mã vào code là một pack nói dối
ngay lần đầu ai đó đổi biến môi trường. Giữ callable còn cho contract test một
phép so danh tính rẻ: `PACK.universe is build_universe`.

**`agent/domain/vn_equity.py` được phép import `src/stocks/*`** — nó là module
*của* domain đó, và `agent/tools/signals.py:80` đã import đúng hàm ấy. Cái phải
sạch là `pack.py` (khung) và `__init__.py`: hai file này **không** được import
`stocks` hay `studies`. Luật lint per-pack của C8 bám vào đúng ranh giới này
(xem Câu hỏi chưa giải quyết #4 của `plan.md`).

### Version của pack: một chuỗi người đọc, một hash máy đọc

Cùng lý lẽ với `contract_hash` (`prompt/contract.py:123-137`): *"một version
somebody sẽ quên bump"*. Nên `DomainPack` có `version: str` viết tay và một
property `identity` = `sha256(name | version | body_text | tên các toolset |
study_names)`. Ở phase này `body_text` rỗng, nên `identity` vẫn ổn định và vẫn
đúng khi phase 04 điền body.

`identity` là thứ phase 04 đưa vào `cache_key` (`prompt/contract.py:162`). Hôm
nay `cache_key` **chưa có caller runtime nào** (chỉ `tests/test_agent_prompt.py:
155-166` gọi), nên thêm tham số là thay đổi rẻ nhất nó sẽ bao giờ có.

### `CHAT_TOOLSETS` vẫn viết ra, và không thể trôi khỏi pack

`toolsets.py:85-98` giải thích vì sao selection phải **viết ra**: mặc định "mọi
bundle đã đăng ký" sẽ trao một bundle mới cho mọi Turn mà không dòng nào đổi.
Luật đó không được đánh đổi lấy tiện lợi. Nên:

```
CORE_TOOLSETS: tuple[str, ...] = ("web", "memory")
CHAT_TOOLSETS: tuple[str, ...] = ("web", "memory", "signals", "studies")   # vẫn literal
```

cộng một cổng import-time thứ hai, cạnh `_check_the_chat_selection_holds()`
(`toolsets.py:229-247`), raise khi `CHAT_TOOLSETS != CORE_TOOLSETS +
active_pack().toolsets`. Hai tính chất cùng giữ được: người đọc thấy tuple thật,
và tuple không thể lệch khỏi pack quá một lần chạy import.

Hệ quả **quan trọng**: `loop.py:862` (`CHAT_TOOLSETS if toolsets is None else
toolsets`) **không phải sửa gì**. Acceptance *"đổi pack không sửa `loop.py`"* đạt
được bằng cấu trúc, không bằng một dòng chuyển tiếp.

Chiều import: `toolsets.py` → `agent.domain`. Nên `agent/domain/*` **không được**
import `toolsets`; pack khai tên bundle bằng chuỗi, và việc kiểm tên đó có thật
là của `toolsets.py` (nó đã có `UnknownToolsetError`, `:101-108`).

### Pack đang active là trạng thái mức process — ghi biên ngay bây giờ

Đúng một pack tồn tại, nên `ACTIVE_PACK` là biến module. Kiểm tra lifetime trước
khi thêm state: `ToolContext` dựng **mỗi Turn** (`loop.py:919-924`), `AgentLoop`
dựng mỗi Turn qua `loop_factory` (`service.py:120-131`) — nghĩa là nếu về sau pack
phải khác nhau giữa hai người dùng, chỗ đúng là `TurnRequest`/`ToolContext`, chứ
**không** phải biến module. C6 chọn pack theo tenant sẽ phải chuyển. Không dựng
sẵn cơ chế đó hôm nay (YAGNI), nhưng **viết câu này thành comment tại
`domain/__init__.py`** để C6 không phải phát hiện lại.

## Related Code Files

- Create: `apps/api/src/agent/domain/__init__.py` — `PACKS`, `ACTIVE_PACK`,
  `active_pack()`, comment biên về lifetime
- Create: `apps/api/src/agent/domain/pack.py` — `DomainPack` + validate, **không**
  import `stocks`/`studies`/`toolsets`
- Create: `apps/api/src/agent/domain/vn_equity.py` — `PACK`, import
  `stocks.universe.build_universe` (`stocks/universe.py:208`) và
  `studies.REGISTRY` (`studies/registry.py:31`)
- Modify: `apps/api/src/agent/toolsets.py` — `CORE_TOOLSETS` (mới, cạnh
  `CORE_TOOLS` `:37`), cổng import-time thứ hai cạnh `:229-247`, `__all__` `:250`
- Create: `apps/api/tests/test_agent_domain_pack.py` — contract test của pack
- Modify: `apps/api/tests/test_agent_capability_contract.py` — mở rộng
  `test_lane_selection_and_order_are_explicit_and_do_not_share_authority`
  (`:209-224`) sang quan hệ pack ↔ `CHAT_TOOLSETS`; **thêm assert, không sửa
  assert cũ**

## Implementation Steps

1. Viết `pack.py`: dataclass frozen, `__post_init__` từ chối `name` rỗng,
   `toolsets` rỗng, và `study_names` trùng lặp. Không đọc settings, không mở
   session — pack là declaration, và một declaration đọc môi trường là một
   declaration không test được.
2. Viết `vn_equity.py`. `study_names` **đọc từ** `studies.REGISTRY` hay viết tay?
   Viết tay, rồi **contract test** so với registry: viết tay là thứ người review
   PR đọc được, và test là thứ giữ nó khỏi trôi. Một pack sinh động từ registry
   sẽ tự đúng cả khi ai đó thêm nhầm một Study.
3. Viết `__init__.py`: `PACKS: dict[str, DomainPack]`, `ACTIVE_PACK = "vn-equity"`,
   `active_pack()`. Kèm comment biên lifetime.
4. Thêm `CORE_TOOLSETS` và cổng import-time vào `toolsets.py`. Thông điệp lỗi phải
   nêu **cả hai** vế lệch, theo mẫu `UnknownToolsetError` (`:104-107`).
5. Contract test:
   - `PACK.toolsets` mọi tên đều có trong `TOOLSETS`;
   - `CHAT_TOOLSETS == CORE_TOOLSETS + PACK.toolsets`;
   - `resolve_toolset(CHAT_TOOLSETS)` trả đúng 12 tool đang có;
   - `PACK.study_names == tuple(sorted(studies.REGISTRY))`;
   - `PACK.universe is build_universe`;
   - `PACK.identity` đổi khi `version` đổi.
6. Test *"đổi pack không sửa `loop.py`"*: monkeypatch `ACTIVE_PACK` sang một pack
   giả khai một bundle khác (mẫu đã có: `tests/test_agent_loop.py:1018-1029` thêm
   bundle `admin` rồi dọn), rồi khẳng định tool surface của loop đổi theo mà
   `loop.py` không có dòng nào biết tên pack.
7. `make test` + `make lint`.

## Success Criteria

- [x] `DomainPack` frozen, không đọc settings, không mở session; test chứng minh
      bằng cách import module trong tiến trình không có DB
- [x] `CHAT_TOOLSETS` vẫn là literal đọc được bằng mắt tại `toolsets.py`
- [x] Cổng import-time raise khi literal lệch khỏi `CORE_TOOLSETS + pack.toolsets`
      — test chứng minh bằng cách sửa một vế rồi reload module
- [x] `resolve_toolset(CHAT_TOOLSETS)` vẫn trả đúng 12 tool; assert cũ ở
      `test_agent_capability_contract.py:210-224` **xanh nguyên văn**
- [x] `PACK.study_names` khớp `studies.REGISTRY`; `PACK.universe is build_universe`
- [x] Test pack giả đổi được tool surface mà `loop.py` không đổi một ký tự
- [x] `grep -n "domain" src/agent/loop.py` = 0 kết quả sau phase này
- [x] `agent/domain/pack.py` và `__init__.py` không import `stocks`, `studies`,
      `toolsets` — test dựng bằng `ast` hoặc bằng một assert trên
      `sys.modules` là quá đà; một grep trong test là đủ và đọc được
- [x] `make test` + `make lint` xanh; năm cổng xanh

## Risk Assessment

**Rủi ro chính: import vòng `toolsets` ↔ `domain`.**
Tín hiệu: `ImportError: partially initialized module`.
Phản ứng đã quyết trước: chiều đúng là `toolsets` → `domain`, một chiều. Pack khai
tên bundle bằng **chuỗi**; mọi phép kiểm tên là của `toolsets`. Nếu một phase sau
thấy pack "cần" import `toolsets`, thứ nó thật sự cần là một hàm kiểm — đưa hàm đó
sang `toolsets`, không đảo chiều import.

**Rủi ro: `vn_equity.py` import `studies` kéo theo side effect đăng ký.**
`studies/__init__.py:29-35` đăng ký 4 Study **bằng chính hành vi import**.
Tín hiệu: thứ tự import đổi, hoặc test đăng ký Study hai lần
(`studies/registry.py:34-44` raise khi trùng tên).
Phản ứng: import `studies.registry.REGISTRY` chứ không import từng module Study;
`agent/tools/studies.py` đã import gói này nên side effect vốn đã xảy ra trong
tiến trình API. Nếu vẫn xung đột, `study_names` viết tay là đủ và contract test
chuyển sang chạy trong test (nơi `studies` chắc chắn đã import).

**Rủi ro: cổng import-time làm API không boot được.**
Đây là **rủi ro có chủ đích** — cùng loại với `_check_the_chat_selection_holds()`
đang chạy (`toolsets.py:247`). Một selection lệch pack mà vẫn boot là một
deployment trao nhầm tool cho model, và đó tệ hơn một lần fail nhanh.
Tín hiệu: API không start sau khi ai đó sửa một trong hai vế.
Phản ứng: thông điệp lỗi nêu cả hai vế và tên file phải sửa. **Không** hạ cổng
xuống warning.

**Rủi ro: pack là biến module rò giữa hai người dùng.**
Hôm nay không rò vì đúng một pack tồn tại và nó không mang state.
Tín hiệu: một phase sau thêm trường **thay đổi được** vào pack.
Phản ứng: pack là frozen dataclass — thêm state thay đổi được vào nó là việc phải
bị review chặn, và comment biên ở `__init__.py` nói vì sao.

## Rollback

Xoá `src/agent/domain/`, hoàn nguyên `toolsets.py` và hai file test bằng
`git checkout`. Không có migration, không có file sinh ra ngoài repo, không có
trạng thái runtime nào tồn tại quá một tiến trình. Sau rollback, `CHAT_TOOLSETS`
trở lại literal đơn độc — đúng trạng thái hôm nay.

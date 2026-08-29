# C5 domain pack — phase 01·02·03

Plan: `plans/260829-1435-c5-domain-pack/` · Nhánh: `feat/study-canvas-runtime`
Ngày: 2026-08-29 · Phase 04–06 chưa thi công.

## Kết quả

| Phase | Trạng thái | Nội dung |
|---|---|---|
| 01 | done | Bảng amendment C5 vào `CLAUDE.md`; sửa "ba bundle / 8 tool"; roadmap §3 C5 trỏ plan; số đo gốc |
| 02 | done | `DomainPack` + pack `vn-equity`; `CORE_TOOLSETS`; cổng import-time thứ hai |
| 03 | done | `refusal_vocabulary` khai bằng enum; guard Python sống lại; docstring `reasons.py` |

Năm cổng xanh: `make test` **1586 passed / 3 deselected** · `make lint` · web
`type-check` · `lint` · `test` **817 passed / 63 file** · `build`.
Đã qua một lượt `code-reviewer` độc lập — xem §Code review ở cuối.

## Số đo gốc của prompt (phase 01)

Đo bằng `messages.estimate_tokens(Message(role=SYSTEM, content=body))` — chính
hàm budget, admission và thang trim đọc. Không phải phép chia bốn ký tự.

| Section | Token | Section | Token |
|---|---|---|---|
| `mission` | 189 | `untrusted` | 876 |
| `invariants` | 1.031 | `memory` | 300 |
| `honesty` | 700 | `style` | 273 |
| `tools` | 1.978 | `context` | 151 |
| `budget` | 532 | **Tổng bodies** | **6.030** |

`prefix()` nguyên khối (bodies + tiêu đề + khung) = **6.097 token**.

**Lệch so với plan, và vì sao.** Plan ghi tổng **5.498** trên tám section. Tám số
đó khớp **chính xác từng cái** — không lệch một token. Cái thiếu là section thứ
chín: `budget` (532 token), do C1 phase 04 thêm và **đang nằm trong working tree,
chưa commit**, cùng với `PROMPT_VERSION = "2.10.0"`. Nên số phase 04/06 phải trừ
đi là **6.030**, không phải 5.498.

Hệ quả cho luật version của plan (§Luật phối hợp hai worktree, luật 2): không
đổi. Plan đã chia sẵn C1 → `2.10.0`, C5 → `3.0.0`, và *"C5 sau C1 giữ 3.0.0"*.
C1 đã ở `2.10.0` trong cây này, nên phase 04 đặt `3.0.0` đúng nguyên văn.

Một Turn thật đo ở C1 là 9.337 input token, nên prompt là **~65%** input của một
Turn (plan ghi ~59% trên số cũ).

## Lỗi bảng amendment bắt được ở bước 1 phase 01

`src/agent/prompt/__init__.py` có trong `Related Code Files` của phase 04 nhưng
**thiếu** trong bảng ở `plan.md`. Theo đúng luật của chính phase 01 — *"một file
xuất hiện ở phase mà không có trong bảng là lỗi của bảng, sửa bảng"* — bảng viết
vào `CLAUDE.md` có thêm một dòng cho nó, giới hạn *"chỉ export tên mới của hai
file trên; không thêm logic"*. Bảng trong `plan.md` chưa sửa; `CLAUDE.md` là bản
thắng cho "đang chạy hôm nay".

## Quyết định đã chốt

**Câu hỏi #3 của plan — version của pack lấy ở đâu.** Chốt theo đề xuất của
chính plan: **cả hai**. `DomainPack.version` là chuỗi viết tay (`"1.0.0"` ở
`vn_equity.py`) để người đọc diff thấy; `DomainPack.identity` là
`sha256(name | version | toolsets | study_names | refusal_vocabulary | body_text)` để một lần sửa
prose quên bump vẫn void được cache. Cùng lý lẽ `contract_hash` đã dùng.

**`study_names` viết tay, không đọc `REGISTRY`.** Lý do mạnh hơn plan ghi: không
chỉ là "viết tay để review đọc được", mà `REGISTRY` được điền **bằng hành vi
import** `src.studies`. Một pack đọc nó lúc import sẽ giữ đúng những gì tình cờ
đã đăng ký ở thời điểm đó. Contract test so với registry chạy trong test, nơi
`src.studies` chắc chắn đã import.

**`universe` typed là `Callable[..., Any]`, không phải `Callable[[Session],
Universe]`.** Plan đề xuất chữ ký cụ thể, nhưng `Universe` sống ở `src/stocks/`,
và `pack.py` bị cấm import `stocks`. Đặt tên kiểu = import kiểu. Khung giữ
callable; chỉ module của domain biết nó là gì. Lý do ghi tại chỗ trong docstring.

**Cổng import-time dùng import cục bộ trong hàm.** `_check_the_selection_matches_
the_pack()` gọi `from .domain import active_pack` **bên trong hàm**. Xem
§Code review #3 cho phạm vi chính xác của thứ này mua được — bản đầu tôi viết
docstring nói quá, reviewer bắt đúng, đã sửa.

## Bốn dữ kiện đo lại được xác nhận

| Plan viết | Đo lại hôm nay |
|---|---|
| `CHAT_TOOLSETS` 4 bundle / 12 tool, `CLAUDE.md:242` nói 8 | Đúng. `CLAUDE.md` đã sửa |
| `src/agent/domain/` không còn trên đĩa | Đúng. Dựng lại từ đầu |
| `tests/test_envelope.py` không còn → guard Python chết | Đúng. `ls` không thấy; docstring vẫn viện dẫn suốt một tuần |
| `SignalIssue` 42 member, `reasons.py` phủ 42/42 | Đúng. Cả hai vế đếm ra 42 |

## Ranh giới — C5 chạm đúng những gì

Chạm: `CLAUDE.md` · `docs/roadmap.md` · `src/agent/toolsets.py` ·
`src/alpha/reasons.py` (chỉ docstring) · `tests/test_agent_capability_contract.py`
(chỉ thêm assert) · mới `src/agent/domain/{__init__,pack,vn_equity}.py` · mới
`tests/test_agent_domain_pack.py`.

Không chạm: `src/stocks/` (`git diff --stat` rỗng, enum vẫn 42 mã) ·
`apps/web/` (`pnpm test` xanh 817/817 mà không sửa gì — đó là bằng chứng) ·
`src/agent/loop.py` (`grep -c domain` = **0**) · `src/agent/prompt/sections.py`.

Mọi file đều nằm trong bảng amendment. Không nới một dòng nào.

## Bằng chứng cho từng gate của phase 02–03

| Gate | Bằng chứng |
|---|---|
| Đổi pack không sửa `loop.py` | `test_swapping_the_pack_moves_the_tool_surface_without_touching_the_loop` — cài pack giả khai bundle `admin`, tool surface đổi theo; `test_the_loop_reaches_for_no_pack_and_no_domain` |
| `CHAT_TOOLSETS` vẫn literal đọc bằng mắt | `toolsets.py` giữ nguyên tuple viết ra; cổng chỉ *kiểm*, không *sinh* |
| Cổng raise khi lệch | Hai test, hai chiều: lệch vế selection và lệch vế pack, cùng một exception |
| Pack không đọc settings/session | `test_importing_a_pack_reads_no_settings_and_opens_no_session` — import lạnh trong subprocess sạch, bằng chứng là `get_settings.cache_info().misses == 0` |
| Khung không import domain | `test_the_frame_imports_no_domain` — `ast.walk` trên import của `pack.py` + `__init__.py`, có test đối chứng |
| `study_names` khớp registry | `PACK.study_names == tuple(sorted(studies.REGISTRY))` |
| `universe` là callable, không phải bản chép | `PACK.universe is build_universe` (danh tính) |
| Guard refusal thật sự bắt | `test_that_guard_goes_red_for_a_code_nobody_wrote_a_sentence_for` — guard viết thành hàm nhận tham số để chĩa được vào một mã cố tình vắng |

## Ghi chú vận hành

**Một lần đỏ transient đầu phiên.** Lượt `make test` đầu tiên báo 1 failed
(`test_a_call_the_turn_refused_tells_the_surface_which_ceiling_refused_it`) với
1546 test collect. Ba lượt sau — gồm một `make test` sạch — đều xanh với 1550
collect. Test đó xanh khi chạy riêng và xanh trong full-suite mọi lượt sau.
Chênh 4 test khi collect chỉ ra `__pycache__` cũ, không phải hồi quy. Không phải
của C5: nó là test của C1, và nó vẫn đỏ y hệt khi stash sạch mọi thay đổi Python
của C1.

## Còn nợ

1. **Câu hỏi #1 của plan chưa giải** — corpus `web_first.json` không có family
   hỏi store, nên nó đo tiết kiệm tốt và gần như không đo được hồi quy chất lượng
   của lượt chạm domain. Owner là C1/C4, không phải C5. Cần user quyết: thêm ~5
   case store-first, hay ghi nợ.
2. **Câu hỏi #2 chưa tới hạn** — *"số của store thắng số của web"* chuyển xuống
   body là quyết định của phase 04, cần user xác nhận vì nó động vào một câu đã
   ghim ở `CLAUDE.md`.
3. **Bảng amendment trong `plan.md`** vẫn thiếu `src/agent/prompt/__init__.py`
   (`CLAUDE.md` đã có). Sửa khi mở phase 04.
4. **`prompt_sections` của pack đang rỗng** — đúng thiết kế phase 02, phase 04
   điền. `identity` đã tính sẵn `body_text` nên không phải đổi công thức.

## Code review — kết quả và xử lý

`code-reviewer` chạy độc lập trên toàn bộ diff. Kết luận: **không có lỗi
production**, 7/7 acceptance criteria pass. Mười phát hiện, tám ở test và hai ở
thiết kế. Đã sửa tám, giữ hai có lý do.

### Đã sửa

| # | Mức | Phát hiện | Xử lý |
|---|---|---|---|
| 1 | HIGH | `importlib.reload` trong test import-purity **đầu độc cả process**: reload rebind class `DomainPack` mới, mọi `isinstance`/`is` sau đó so với class không còn tồn tại, và `finally` reload lần nữa chỉ tạo thế hệ thứ ba chứ không khôi phục. Reviewer tái hiện được: **5 failed** với một tập con đảo thứ tự | Bỏ hẳn reload. Thay bằng **subprocess sạch** — đó cũng là mô hình đúng của điều đang khẳng định ("một lần import lạnh làm gì"). Bằng chứng là `get_settings.cache_info().misses == 0`. Thêm một test đối chứng chứng minh probe bắt được |
| 2 | MEDIUM | `identity` bỏ sót `PromptSection.title` và `refusal_vocabulary`, **lệch với chính quy ước `contract_hash`** mà docstring viện dẫn: `contract._static_text` hash cả `## title`, `body_text` thì không | `body_text` render `## {title}\n\n{body}` — đúng layout của core. Một chuỗi cho cả ba việc (ship · đo token · hash), nên không thể lệch. `refusal_vocabulary` gộp vào digest theo `sorted()` |
| 4 | MEDIUM | Test mang tên "acceptance gate của cả thay đổi này" **không dựng `AgentLoop` nào**, và assert về surface là vòng tròn — nó đọc lại đúng tuple mà chính test vừa ghi | Dựng `AgentLoop(toolsets=None)` thật với pack giả. Phát hiện thêm một dữ kiện: `loop.py:153` là **from-import**, bind giá trị lúc import — nên test phải patch cả `loop.CHAT_TOOLSETS`. Không phải né tránh: production đổi pack = sửa source + restart, rebind y hệt |
| 5 | LOW-MED | Regex kiểm import có hai lối lách thật: `from .. import toolsets` bắt được `'..'`, `from src import stocks` bắt được `'src'` — đúng dạng một edit tương lai trong `__init__` sẽ viết | Chuyển sang `ast.walk`, giải cả `ImportFrom` alias. Thêm test đối chứng trên đúng ba dạng đó |
| 6 | LOW-MED | `assert "domain" not in source` trên `loop.py` là substring trần trên file **C1 đang sửa**, mà từ vựng repo dùng "domain" khắp nơi (`web_domain_denylist`, dedup domain) | Thu hẹp về import + năm symbol cụ thể. Một comment của C1 không còn làm đỏ một cổng cấu trúc |
| 7 | LOW | `PACK.refusal_vocabulary == {i.value for i in SignalIssue}` là **tautology** — `vn_equity.py` dựng nó bằng đúng comprehension đó | Đọc mã ra khỏi **source** `issues.py` bằng regex, đúng cách guard web làm. Cộng `len == 42` |
| 8 | LOW | Regex "câu khuyên" bỏ hết vế tiếng Việt plan yêu cầu, và bỏ lọt dạng giảm nhẹ: "Consider reducing exposure", "Avoid buying until confirmed" | Mở rộng sang dạng hedged + đối chứng bốn câu. Docstring nói thật: prose ở `reasons.py` là **tiếng Anh**, khớp `nên mua` ở đó là diễn kịch |
| 9 | LOW | `DomainPack(**vars(PACK))` đúng hôm nay nhưng vỡ im lặng với `slots=True` hoặc `field(init=False)` | `dataclasses.replace` |

Repro chính xác của reviewer (bốn node-id, trước đây 5 failed) giờ **7 passed**.

### Giữ, có lý do

**#3 — `toolsets` giờ kéo theo `stocks` + SQLAlchemy + Pydantic khi import
(0,45s, 9 module `stocks`).** Reviewer đo đúng, và đây là **đánh đổi plan đã
quyết trước**: phase 02 §Risk viết *"cổng import-time làm API không boot được —
đây là rủi ro có chủ đích, cùng loại với `_check_the_chat_selection_holds()`
đang chạy"*. Một selection lệch pack mà vẫn boot là một deployment trao nhầm
tool cho model.

Nhưng reviewer đúng ở chỗ **docstring tôi viết nói quá**. Đã sửa cho chính xác:
import cục bộ mua được **đúng một thứ** — lúc nó chạy, ở dòng thực thi cuối của
module, `toolsets` đã dựng xong, nên một `domain` tương lai với ngược lên tìm
`TOOLSETS` sẽ thấy, thay vì nhận module nửa vời. Nó **không** làm module này độc
lập với domain. Cycle chiều ngược — thứ gì đó dưới `stocks` import `toolsets` —
vẫn vỡ; lý do hôm nay không vỡ là **không module nào dưới `stocks`/`core` import
`src.agent`**. Đó là cạnh không được thêm, và câu này giờ nằm trong docstring.

**#10b — `universe` không được validate trong `__post_init__`.** Giữ nguyên
`| None = None`. Plan chỉ định đúng ba phép kiểm; và pack thứ hai của C8 có thể
hợp lệ mà không có khái niệm universe nào. Thêm ràng buộc bây giờ là đoán trước
hình dạng của domain chưa tồn tại.

### Cổng sau khi sửa

`make test` **1586 passed** (+15 so lượt trước) · `make lint` · web `type-check` ·
`test` **817 passed**. `identity` ổn định qua `PYTHONHASHSEED` 0/1/12345.

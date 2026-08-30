---
phase: 3
title: "Compute sandbox — phép tính tổng quát"
status: completed
priority: P1
effort: "22h"
dependencies: [2]
---

# Phase 3: Compute sandbox — phép tính tổng quát

## Overview
Tool `compute(code, inputs, constants?)`: model viết pandas **trên frame đầu
vào**, sandbox chạy, kết quả là frame mới. Đây là trục "phép tính" — thứ làm
hệ tổng quát thay cho enum op đóng — và là chỗ bất biến "model không gõ số"
được ép bằng AST, không bằng lời dặn.

## Requirements
- Functional:
  - Input: `code` (Python, ≤ 4.000 ký tự), `inputs: [frame_id ≤ 6]` → biến
    `f0..f5` là `pandas.DataFrame` dựng từ frame; `constants?: {name:
    {value, reason}}` ≤ 4; `output_kind?: series|table|matrix`.
  - Output: `frameId` + summary (shape, cột, min/max mỗi cột số, as_of) —
    **không trả DataFrame**.
  - **Validator AST trước khi chạy**, lỗi có tên:
    - `compute_literal_number`: literal số ngoài tập hằng cấu trúc
      `{0, 1, 2, …, 12, 100, 252, 365, 1_000, 1_000_000, 1_000_000_000}`
      và không phải index/slice/`round(x, n)`/`head(n)`. Muốn hằng khác →
      khai `constants` (được ghi vào provenance, cờ `has_constants`).
    - `compute_forbidden_import`: ngoài `pandas, numpy, math, statistics,
      datetime`.
    - `compute_forbidden_name`: `open, eval, exec, compile, __import__,
      getattr, setattr, globals, locals, input, breakpoint`, mọi dunder attr.
    - `compute_no_result`: không gán biến `result` là DataFrame/Series.
  - Sandbox: subprocess Python riêng, `-I`, không mạng (đóng socket qua
    `sitecustomize` hoặc `seccomp`-lite bằng `resource` + xoá module
    `socket`), rlimit CPU 5 s · RSS 512 MB · stdout 2 MB; input frame qua
    stdin JSON, output JSON. Timeout → `compute_timeout`.
  - Kết quả → Frame: DataFrame index datetime/period → `series`; ≤ 12 cột, ≤
    500 hàng (vượt → `compute_result_too_large`, gợi ý `.tail()`); `NaN` →
    `null`; cột số ép `float`; labels kế thừa từ frame nguồn khi tên cột trùng.
  - Provenance: `source="derived"`, `as_of = min(as_of inputs)`, `health` bi
    quan, `method_notes` = code hash + constants; `params` lưu `code`,
    `inputs`, `constants` → replay chạy lại code trên frames đã lưu cho cùng
    kết quả.
- Non-functional: p50 < 1,5 s trên frame 500 × 12; concurrency `SERIALIZED`
  theo Turn; `MAX_COMPUTE_PER_TURN = 6`.

## Architecture
```
tools/compute.py ── studies/compute/validator.py (AST) ── studies/compute/runner.py (subprocess)
                                                               └── studies/compute/worker.py (entry, không import src.*)
                 ── frames_buffer.read_frame ×n ── to DataFrame ── … ── Frame ── store_frame(kind="compute_frame")
```
`worker.py` là file chạy trong subprocess: đọc JSON stdin, dựng DataFrame, `exec`
code trong namespace `{pd, np, math, statistics, f0..fn, constants}`, đọc
`result`, in JSON. Không import `src`, không đọc env. Validator chạy **ngoài**
sandbox, trước spawn.

## Related Code Files
- Create: `apps/api/src/studies/compute/{__init__,validator,runner,worker,frames_io}.py`
- Create: `apps/api/src/agent/tools/compute.py`
- Modify: `apps/api/src/studies/frames_buffer.py` (kind `compute_frame`,
  `computes_in_turn(session, turn_id)`)
- Modify: `apps/api/src/agent/toolsets.py` (`studies` += `compute`)
- Modify: `apps/api/src/agent/registry.py` — **chỉ nếu** cần `ToolAccess`
  mới (`LOCAL_COMPUTE`); ưu tiên dùng `STORE` + `reads_external=False`
- Tests: `apps/api/tests/studies/test_compute_validator.py`,
  `test_compute_runner.py` (escape: network, fs, fork, sleep-bomb),
  `tests/test_agent_compute_tool.py` (frames absent, replay identical)

## Implementation Steps
0. **Kiểm `pip show pandas numpy` trong `.venv`/container.** Không có → dừng,
   hỏi user (DoD #4). Có (kéo theo vnstock) → ghim version trong report.
1. `frames_io.py`: Frame ⇄ DataFrame, giữ `labels`, `unit`; test round-trip.
2. `validator.py`: `ast.parse` → walk; tập hằng cấu trúc là hằng module có
   docstring giải thích từng số; trả `list[Violation(code, line, snippet)]`.
3. `worker.py` + `runner.py`: spawn `sys.executable -I worker.py`, rlimit,
   timeout, parse; lỗi runtime → `compute_runtime_error` kèm 3 dòng traceback
   cuối (không lộ path host).
4. Escape tests: `import socket` (bị AST), `__builtins__`, `().__class__`,
   `open('/etc/hosts')`, `while True`, `[0]*10**9`; mỗi cái một lỗi có tên.
5. `tools/compute.py`: schema, đọc inputs (ownership Turn), gọi validator →
   runner → Frame → store; summary ≤ 80 token.
6. Replay test: chạy `compute` hai lần cùng inputs → frames byte-identical;
   đổi một hằng → khác và provenance ghi.
7. `toolsets.py` + test đếm tool.
8. Đo p50/p95 trên 20 phép tính mẫu (yoy, ratio, share-of-total, rank,
   rolling mean, pivot mã × quý) — ghi report phase.

## Success Criteria
- [x] 20 phép tính mẫu đúng; 0 literal lọt; mọi escape test trả lỗi có tên.
      **Đo:** 20/20 case trong `SAMPLES` khẳng định trên *kết quả số*, không chỉ
      trên `ok` — tỉ lệ, tăng trưởng QoQ/YoY, tỉ trọng, xếp hạng, trung bình
      trượt, pivot, cộng dồn, hiệu hai cột, biên, mean/std/min-max theo nhóm,
      z-score, lọc, sort+head, merge hai frame, giá×khối lượng, rebase, đếm kỳ.
      Escape: `import socket` → `compute_forbidden_import` · `__builtins__` và
      `().__class__` → `compute_forbidden_name` · `open('/etc/hosts')` →
      `compute_forbidden_name` · `pd.read_csv` → `compute_forbidden_name` ·
      `while True` → `compute_timeout` · `[0]*10**12` →
      `compute_memory_exceeded` (Linux).
- [x] `VIC vs VCB`: `compute` trên frame BCTC → ROE theo mã, `winner`/`loser`
      gán bởi chính phép tính. **Đo:** `test_a_comparison_marks_the_winner...`
      — role đi qua `result.attrs["cell_roles"]` chứ không phải `point_roles`.
      **Sửa so với plan:** một bảng mã × chỉ tiêu có winner theo **cột**, và
      `point_roles` sẽ nói cả *hàng* thắng — đúng câu mà một so sánh sinh ra để
      tránh (`contracts.py` viết ra luật ba mức trước phase này). `frames_io`
      nhận cả ba mức; `cell_roles` là mức đúng cho so sánh.
- [x] Replay identical; frames không vào transcript.
      **Đo:** hai lần chạy cùng code + cùng inputs → `row.frames` bằng nhau
      byte-for-byte; đổi một hằng khai báo → khác, và `params.constants` ghi
      lại. Transcript: frame 30 hàng, hàng thứ 15 (`313146000`, `S15`) không
      có trong message; hai đầu mút thì có, và đó là `summary` mà plan khai.
- [x] p50 < 1,5 s; timeout/rlimit hoạt động.
      **Đo trên 20 phép tính mẫu (macOS, Python 3.12.3, pandas 2.3.3, numpy
      2.2.6):** p50 **0,261 s** · p95 **0,271 s** · min 0,251 s · max 0,272 s.
      `while True` dừng ở dưới `WALL_SECONDS + 3`.
- [x] `make test` **1935 passed** (từ 1776); năm cổng web xanh.

## Evidence — thi công 2026-08-30

**Bước 0 trả lời rồi, không phải hỏi.** `pandas>=2.0,<3` và `numpy>=1.24,<3`
đã nằm trong `requirements.txt` (dòng 50–51, kéo theo `vnstock`). Bản đang cài:
**pandas 2.3.3 · numpy 2.2.6 · Python 3.12.3**. Không thêm dependency nào.

**Trần bộ nhớ là 512 MB và con số đó đo được, không đoán.** `VmSize` của image
`stockmassive-api` sau khi import pandas + numpy là **195 MB**, nên 512 MB để
lại ~317 MB cho phép tính — trên mọi frame mà `MAX_RESULT_ROWS = 500` và
`MAX_RESULT_COLUMNS = 12` cho phép, và dưới mọi container chạy nó.

**Nhưng nó là trần của Linux, và response nói thẳng điều đó.** macOS **từ chối**
`setrlimit(RLIMIT_AS, …)` bằng `ValueError` — đo tại chỗ, không phải đọc tài
liệu. Nên `worker._apply_limits` trả về danh sách ceiling *thật sự* áp được, và
đo trong container: `['cpu', 'memory', 'files']`; trên máy dev: `['cpu',
'files']`. Test khẳng định `[0]*10**12` chết bằng **một mã có tên** chứ không
khẳng định *mã nào* — trên máy dev nó là đồng hồ, trong container là bộ nhớ.
Một test giấu khác biệt đó sẽ nói với người đọc rằng laptop có hộp của container.

**`preexec_fn` cố ý không dùng.** Handler chạy trong `asyncio.to_thread` của một
server đa luồng, và `preexec_fn` giữa `fork` và `exec` trong tiến trình đa luồng
có thể deadlock trên một lock luồng khác đang giữ. Tiến trình con tự đặt trần
của nó, ngay dòng đầu, **trước** khi import gì.

**Ba thứ xảy ra trước khi code của model được trao quyền, và thứ tự là quan trọng.**
Đặt trần → đóng mạng → dời stdout. Mạng phải đóng dù validator đã cấm
`import socket`: `pd` **đã ở trong namespace** và pandas đọc được URL. Đo:
`pd.read_json('http://…')` trả `compute_runtime_error` kèm
`URLError: <urlopen error một phép tính không đọc được ra ngoài>`.
`socket.socket` bị thay bằng một **class** chứ không phải một hàm — bản đầu dùng
hàm và refusal ra thành `TypeError: function() argument 'code' must be code`,
tức kết nối vẫn không xảy ra nhưng model không đọc được gì để sửa.

**Hai cổng import, và một test giữ chúng bằng nhau.** Validator cấm module bằng
cách **đọc code** — đó là cổng cho model một câu để sửa. `worker._safe_builtins`
bọc `__import__` — đó là cổng khi code tới được tiến trình này bằng đường khác.
Bản đầu **không** có cổng thứ hai và `import math` (validator cho phép) chết lúc
chạy vì `__builtins__` an toàn không có `__import__`. `worker.ALLOWED_MODULES`
chép lại `validator.ALLOWED_MODULES` — biên tiến trình là chỗ duy nhất một hằng
chép lại rẻ hơn cái import xoá nó đi — và một test khẳng định hai bên bằng nhau.

**`print` không cấm; stdout được dời.** Cấm một cái tên rồi hy vọng không có
đường thứ hai là sai hình dạng: `f0.info()` ghi thẳng ra stdout, và stdout **là**
giao thức. `sys.stdout` trỏ vào một buffer bị vứt; JSON đi ra fd thật giữ riêng.

**Index đếm bị bỏ, không chỉ `RangeIndex`.** `pd.concat([f0, f1])` sinh Int64Index
trùng lặp không tên; giữ nó thành cột nghĩa là một cột số 0 đứng trước con số
đầu tiên người đọc chờ. Luật: index bị bỏ khi **không tên và là số nguyên**.

**Traceback lọc theo frame, không theo dòng.** Bản đầu bỏ dòng `File …` nhưng
giữ dòng code dưới nó, nên `exec(compile(request.get("code")…` lọt vào refusal.
Giờ chỉ frame có `filename == "<compute>"` được giữ.

**Hai lỗ của bản đầu, tự tìm ra và đóng trước khi review.**
`_positions_that_are_not_figures` miễn trừ **mọi** hằng dưới một `Subscript`,
nên `f0[f0['roe'] > 0.05]` — một *bộ lọc* đội lốt chỉ số, và là cách tự nhiên
nhất để viết một ngưỡng — đi lọt im lặng. Giờ phép đi chỉ nhận **vị trí thật**:
một chỉ số, một biên `Slice`, hoặc tuple của chúng; một so sánh / lời gọi / phép
tính trong ngoặc được đọc y như ở mọi chỗ khác. Lỗ thứ hai:
`float('0.07')` đọc **đúng như** gõ `0.07`, nên một chuỗi giao cho một lời gọi
ép kiểu số được đọc là con số nó sắp trở thành — và **chỉ** ở vị trí đó, vì một
chuỗi trông như số ở chỗ khác là một *nhãn* (`f0[['2025', '2026']]`).

**Và validator **không** là một chứng minh — điều đó viết ra trong docstring.**
`7 / 100` là hai số cấu trúc và cũng là `0.07`; không phép đọc code nào tách
được nó khỏi một phần trăm câu hỏi thật sự cần. Số học trên tập cấu trúc với
tới mọi số. Thứ đóng lại là mọi đường **hiển nhiên**, mỗi đường một tên — nên
một model làm theo chỉ dẫn không bao giờ gõ một figure do sơ ý, và một model có
gõ thì được nói đúng nó vừa làm gì. Chứng minh một con số là thật nằm ở tầng
trên: nó ra từ một frame, mà frame ra từ store.

**Số cấu trúc: 0–12 · 100 · 252 · 365 · 1e3 · 1e6 · 1e9.** `rolling(20)` **bị
từ chối** và phải khai `constants` — đó là chủ ý: hai mươi phiên là một phán
đoán về thị trường, và người đọc nên thấy nó được nêu ra chứ không tìm thấy nó
bên trong một biểu thức. `head(50)`, `round(3)`, `iloc[:, 37]` thì không:
chúng nói vị trí và độ chính xác, không nói về một công ty.

**Danh mục tool trong prompt cập nhật, `PROMPT_VERSION` 3.2.0 → 3.3.0.** Đúng
ngoại lệ hẹp đã ghi trong `CLAUDE.md`: chỉ prose danh mục, không luật, không
playbook. `CATALOGUE_GROWTH_SINCE_THE_SPLIT` 238 → **574** token (đo bằng cách
render section TOOLS có và không có bốn mục), nên hai cổng đo cái split của C5
vẫn đo đúng thứ chúng được viết ra để đo.

## Risk Assessment
- Sandbox subprocess không đủ cách ly trên macOS dev vs Linux container →
  test escape chạy ở cả hai; nếu Linux có `seccomp` khả dụng thì bật thêm, ghi
  là tăng cường không phải điều kiện.
- Tập hằng cấu trúc quá hẹp → model kẹt (tín hiệu: tỉ lệ `compute_literal_
  number` cao ở phase 09) → mở `constants` đã có, **không** nới tập.
- pandas không có → **hỏi user**; kế hoạch B: `compute` trên list-of-rows với
  bộ hàm pure-Python (mất tổng quát, ghi rõ).

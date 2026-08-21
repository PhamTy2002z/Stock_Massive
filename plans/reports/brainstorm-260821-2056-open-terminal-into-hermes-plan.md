# Ghép Open Terminal vào plan Hermes — đề xuất triển khai

**Ngày:** 2026-08-21 · **Phạm vi:** đề xuất, không sửa code · **Nhánh:** develop

Đầu vào: `plans/260821-0020-agent-upgrade-hermes-lessons/` (Phase 1–2 Complete,
3–8 Pending) + `plans/reports/research-260821-2050-open-terminal-transfer.md` +
`plans/reports/brainstorm-260821-2044-agent-terminal-tool.md`.

---

## Phán quyết trước: đây là việc ở đuôi, không phải ở đầu

Số của chính plan: **58% Turn chết `grounding_failed`**, **category B 0/30**,
**36% Turn chết vì route**, ba câu hỏi live → hai màn hình trắng.

`run_python` nằm sau một cờ tắt-mặc-định, và một Turn phải **sống sót qua route +
grounding** mới chạm tới nó. Người dùng đang nhận màn hình trắng cho *"tình hình
chứng khoán VN hôm nay"* sẽ không bao giờ tới được chỗ numpy có ích.

Nên đề xuất này **không tạo phase mới, không đổi thứ tự phase, không thêm goal**.
Nó ghép 4 điểm vào chỗ đã có, cộng một nhóm bug tách hẳn ra ngoài plan.

Ba tài liệu đầu vào hội tụ vào một câu: Open WebUI trả lời bài "sandbox thiếu năng
lực" bằng **thêm năng lực** (`PIP_PACKAGES`, custom image); Hermes trả lời bằng
**dạy model dùng đúng năng lực đang có** (`terminal_hints.py`). Với
`MAX_TOOL_ROUNDS = 4`, cách của Hermes có đòn bẩy cao hơn — và rẻ hơn nhiều.

---

## Điểm 1 — Ngoài plan: hai bug executor (P0, độc lập hoàn toàn)

Cả hai trong `apps/executor/server.py`, cùng một gốc: **bound child mà không bound
container**.

| Bug | Bằng chứng | Sửa |
|---|---|---|
| Process cháu sống sót wall-clock kill, reparent về `server.py`, tồn tại mãi. ~62 orphan là `pids_limit 64` cạn → mọi `run_python` sau đó fail | `nobody 19474 99564 python -c ...` sau khi cha bị kill | `Popen(..., start_new_session=True)` + `os.killpg` thay `kill()` |
| `/tmp` là tmpfs của **container**, không của job → state đi xuyên Turn và xuyên user | `call 1` ghi `/tmp/x.txt` → `call 2` đọc `True` | tmpdir riêng mỗi job làm `TMPDIR`/`HOME`, xoá sau; hoặc dọn `/tmp` giữa job |

**Không chạm tool schema → không kích hoạt eval gate.** Không phụ thuộc phase nào,
không phase nào phụ thuộc nó. Làm bất cứ lúc nào, kể cả song song với Phase 3–5.

Đây là việc duy nhất trong toàn bộ đề xuất này nên làm **ngay**, vì nó là lỗi đúng
nghĩa chứ không phải nâng cấp.

---

## Điểm 2 — Ghép vào Phase 6.3: hint executor, chưa phải numpy

Phase 6.3 đã có mục *"gợi ý phục hồi trong lỗi tool"* theo mẫu `terminal_hints.py`.
Executor là ca dùng sẵn có tốt nhất cho nó, và plan chưa biết:

Executor **chỉ có stdlib** — probe: `['statistics','math','json','decimal']`, không
numpy/pandas/scipy. Còn `compute.py` trả traceback thô:
`ExecutorUnavailable("ModuleNotFoundError: No module named 'numpy'")`.

Chuỗi thất bại thực tế: model không được cho biết môi trường có gì → viết
`import numpy` → nhận traceback thô → **đốt một round trong bốn**. Đúng lớp lỗi
Phase 3 gọi là "mỗi round bị lãng phí là đắt gấp đôi".

**Chỗ đặt hint đã có sẵn, và nó rẻ hơn dự kiến.** Truy đường lỗi:
`ExecutorUnavailable` không nằm trong nhóm fatal (`MalformedArguments`,
`AuthUnavailable`, `ToolTimeout`, `CancelledError` — `loop.py:1128-1136`), nên nó đi
qua `_record_failure` → `tool_error_result` (`core/llm/errors.py:333`) và **tới được
model** dưới dạng:

```json
{"tool_call_id": "...", "tool": "run_python",
 "error": "ModuleNotFoundError: No module named 'numpy'", "status": "tool_error"}
```

`tool_error_result` là **một cửa duy nhất cho mọi tool lỗi**, không riêng executor.
Nên `terminal_hints` của Phase 6.3 thuộc về đúng đó: một hàm thuần map hình dạng lỗi
→ một gợi ý, gắn vào envelope này. Runtime, **không chạm tool schema, không refreeze
fixture, không eval gate** — và phục vụ luôn cả web/news/store, không chỉ
`run_python`.

Sửa theo đúng kỷ luật Phase 6.3 đã ghi (chỉ khi lỗi, tối đa **một** gợi ý, khớp đầu
tiên thắng, nói **hành động kế tiếp** không phải bài chẩn đoán, hàm thuần):

| Hình dạng lỗi | Gợi ý |
|---|---|
| `ModuleNotFoundError` / `ImportError` | executor chỉ có thư viện chuẩn — dùng `statistics`/`math`, hoặc lấy số qua tool dữ liệu |
| `wall-clock limit` | chia phép tính nhỏ hơn, hoặc giảm số điểm dữ liệu truyền vào |
| `output limit` | trả số tổng hợp, đừng trả mảng |
| `code must assign ... result` | gán kết quả vào `result` |

Và **chỉ sau khi** hint đã chạy một thời gian, nếu trace vẫn cho thấy cầu thật thì
mới `pip install numpy` trong `apps/executor/Dockerfile` (bake lúc build, container
vẫn networkless — không mở mạng như Open WebUI phải làm).

Thứ tự này quan trọng: Phase 6 tự đặt ra luật *"assumption có thể vỡ: giả định tràn
context là vấn đề thật… nếu gần bằng 0 thì hoãn phase"*. Luật đó áp cho numpy y
nguyên. Dữ liệu để quyết là `agent_tool_call` — không phải việc Open WebUI có sẵn
pandas.

---

## Điểm 3 — Ghép vào Phase 6: dồn mọi thay đổi tool schema vào **một** lần refreeze

Đo được: `run_python` có `versioned=True` (mặc định của `ToolSpec`), và
`tool_catalog_version` là sha256 của `schema().as_wire()` — **description nằm
trong đó** (`catalog.py:174-186`).

Hệ quả: sửa một chữ trong description `run_python` ⇒ đổi `tool_catalog_version` ⇒
**đóng băng lại Eval Fixture + Eval Report**.

Phase 6 **đã** phải refreeze fixture. Nên mọi thay đổi chạm schema phải đi **cùng**
Phase 6, một PR, một gate run:

- `data_ref` / preview của tầng 2
- numpy nếu được chốt (đổi khả năng ⇒ description phải nói ⇒ chạm hash)

Hint **không** thuộc nhóm này: nó nằm ở `tool_error_result` trên đường runtime, ngoài
schema (xem Điểm 2). Đó là lý do nên làm hint trước và độc lập — nó không phải chờ
gate run nào.

Rải ra thành nhiều PR = nhiều gate run = nhiều tiền, và `make eval` được tách khỏi
`make test` chính vì nó tốn tiền (`CLAUDE.md`).

---

## Điểm 4 — Ghép vào Phase 8: baseline phải pin **tổ hợp cờ**, không chỉ code

Đây là phát hiện đáng giá nhất cho plan, và nó đo được:

```
exec=off web=off mcp=off -> 39e3555fc8c48e30  (15 tools)
exec=ON  web=off mcp=off -> 208dc37f9918223b  (16 tools)
exec=off web=ON  mcp=off -> 01de733ac32cd123  (17 tools)
```

`tool_catalog_version` **phụ thuộc cờ môi trường** — vì ba nhóm tool optional
(`executor`, `web`, `mcp`) đăng ký theo `settings.*_enabled` trong `suite.py:70-73`,
và chúng đều `versioned=True` (chỉ MCP đặt `versioned=False`, `mcp/registry.py:90`).

Cộng với `adr/0016`: harness **từ chối chạy** khi pin của fixture và deployment
lệch nhau. Nên:

- Một gate run chỉ mô tả đúng tổ hợp cờ nó được đóng băng dưới.
- Bật/tắt `EXECUTOR_ENABLED` ở prod là một thay đổi **cần refreeze**, không phải
  một thao tác vận hành.
- Nếu prod bật executor mà fixture đóng băng lúc tắt, gate run **không nói gì về
  prod** — và plan này đang dùng gate run làm bằng chứng nghiệm thu cho cả 8 phase.

Đề xuất cụ thể cho Phase 8: ghi tổ hợp cờ vào Eval Report như một field bắt buộc,
cạnh run id và điểm từng category. Một dòng, và nó làm baseline mới thành cái
reproduce được.

Câu "EXECUTOR_ENABLED ở prod là gì?" còn nợ từ hai báo cáo trước hoá ra **không
phải câu hỏi vận hành** — nó là input của eval gate.

---

## Điểm 5 — Ghi nhận, không phải việc: Phase 2 đã làm `run_python` hữu dụng hơn

`_untrusted_claim` trả `Citation(source=DERIVED)` chứ không raise —
derived evidence là citation **hợp lệ**, chỉ không đủ cho khuyến nghị/price zone.
Nên sau fail-open của Phase 2, một con số derived trong prose không còn kết thúc
Turn, chỉ hạ cấp block.

Tức là `run_python` vừa được nâng giá trị mà không ai sửa gì nó. Không có việc gì
phát sinh từ điều này — ghi để đừng lo, và để Phase 8 biết mà đọc
`downgraded_blocks` cho đúng.

---

## Không lấy — nhắc lại, nay có thêm bằng chứng

| Thứ | Vì sao |
|---|---|
| Terminals orchestrator, policy, K8s, scheduled reset | Cần Enterprise License, không lấy được code. `adr/0011` vẫn đúng: hạ tầng nặng nhất cho nhóm user nội bộ |
| Network + egress allowlist | Thành đường tắt fetch API vượt provenance và quota vnstock. Deps bake lúc build là đủ |
| Filesystem bền, shell, package install runtime | State bền là thứ `run_python` cố ý không có; là gốc của cả hai bug ở Điểm 1 |
| PNG/PDF/HTML dashboard | Chart là **Widget** (`adr/0012`) |
| `EXECUTE_DESCRIPTION` (description là env var) | Nay có bằng chứng cứng ở Điểm 4: description nằm trong hash catalog. Cấu hình được ⇒ catalog version phụ thuộc môi trường ⇒ fixture chết. Repo **đã vô tình có** dạng nhẹ của vấn đề này qua cờ bật/tắt |

---

## Sequencing đề xuất

```
Điểm 1 (2 bug executor)  ──────────── bất kỳ lúc nào, song song, không eval gate
Phase 3 → (4 ∥ 5) → 6 → 7 → 8        giữ nguyên phụ thuộc của plan
                        ↑          ↑
                   Điểm 2+3     Điểm 4
```

Không phase mới. Không đổi goal. Ba dòng thêm vào `plan.md` (Điểm 2 vào bảng Phase
6, Điểm 4 vào mục Eval gate) là đủ để plan mang những cái này.

Tổng công việc thật phát sinh: **hai bug nhỏ + một bảng hint + một field trong Eval
Report.** Còn lại là quyết định *không* làm.

---

## Câu chưa rõ

- `agent_tool_call WHERE status='unknown_tool'` từ khi ship `run_python` cho thấy
  gì? Quyết numpy phụ thuộc hoàn toàn vào bảng này. Nếu nó trống, Điểm 2 dừng ở
  hint và numpy không bao giờ cần đến.
- Fixture 1.4.0 hiện tại được đóng băng dưới tổ hợp cờ nào? Nếu không ai ghi lại,
  Phase 8 không so được với nó theo cách nói được điều gì chắc chắn — và đó là
  lý do thêm field cờ vào Eval Report cần làm ở Phase 8, không phải sau.
- Ngoài `run_python`, hình dạng lỗi nào của web/news/store đáng có hint? Kỷ luật của
  Hermes là **đào tần suất từ DB sản xuất** trước khi viết hint (*"a 250k-terminal-result
  window"*), không đoán. Ta có `agent_tool_call.error` — nên đọc nó trước khi viết bảng
  hint, để bảng phản ánh lỗi thật chứ không phải lỗi tưởng tượng.

# Open Terminal (Open WebUI) — tinh túy và cái gì chuyển được về Stock_Massive

**Ngày:** 2026-08-21 · **Nguồn:** 13 trang `docs.openwebui.com` (`features/open-terminal/**`, `reference/*`, `features/chat-conversations/**/code-execution/*`) · **Phạm vi:** đọc + đối chiếu, không sửa code

Tiếp nối `brainstorm-260821-2044-agent-terminal-tool.md`. Báo cáo đó xác nhận
`run_python` + service `executor` đã ship. Báo cáo này đọc cách Open WebUI làm
cùng bài toán ở quy mô lớn, rồi lọc ra cái gì thật sự chuyển được.

**"Open Terminal" là tên riêng, không phải mình đoán** — đây là feature có 35 trang
docs của Open WebUI, và nó là bản nâng cấp thay thế Code Interpreter (Pyodide) cũ.

---

## Phần 1 — Tinh túy: 8 ý tưởng thật của họ

### 1. Tách Control layer / Action layer

| Layer | Thành phần | Việc |
|---|---|---|
| Control | Open WebUI core | prompt, context, tool, state, permission, user |
| Action | Open Terminal substrate | filesystem, shell, package manager, process, preview |

Đây chính xác là hình dạng Stock_Massive đã có: `api` = control, `executor` = action.
Xác nhận `adr/0019` chọn đúng trục chia. **Đã có, không phải học.**

### 2. Giá trị nằm ở *stateful*, không ở *execute*

Docs nói thẳng Code Interpreter cũ là "a narrower execution surface"; Open Terminal
rộng hơn vì có filesystem, shell, package, process, preview. Vòng lặp họ bán là
**write → run → đọc traceback → sửa → chạy lại**:

> "The AI writes a scraper, hits an unexpected page layout, reads the
> `AttributeError` traceback, adjusts the CSS selectors, and re-runs successfully."

Đây là điểm khác biệt triết học lớn nhất so với mình, và **mình cố ý không lấy** —
xem Phần 3.

### 3. Policy là đơn vị quản trị, không phải env var rời rạc

Orchestrator "Terminals" định nghĩa mọi thứ qua *policy*:

| Field | Việc |
|---|---|
| `image` | image cho workspace mới |
| `cpu_limit` / `memory_limit` / `storage` | `2`/`4Gi`/`10Gi` |
| `storage_mode` | `per-user` / `shared` / `shared-rwo` |
| `env` | inject env var |
| `idle_timeout_minutes` | tear down khi rỗi |
| `restricted`, `pod_security_context`, `container_security_context` | security context |

Và **hard cap toàn cục policy không vượt được**: `TERMINALS_MAX_CPU`,
`TERMINALS_MAX_MEMORY`, `TERMINALS_MAX_STORAGE`. Hai tầng: policy tự chọn trong
khung, admin giữ khung.

Quan trọng: *"Policy changes apply to newly provisioned workspaces. Existing running
workspaces keep their current image until they are stopped, refreshed, or cleaned up."*
Họ chấp nhận eventual consistency thay vì cố hot-reload.

### 4. Isolation theo **user**, không theo **call**

Hai model:
- `OPEN_TERMINAL_MULTI_USER=true` — một container, mỗi user một `/home/{user-id}`.
  Docs tự thừa nhận điểm yếu: *"Shared network namespace means users can reach each
  other through bound ports. Not suitable for untrusted deployments."*
- Terminals orchestrator — **mỗi user một container**, provision on-demand, cleanup
  khi idle, **warm start** khi user quay lại.

Chi phí của per-call isolation (cold start) được họ trả bằng warm start per-user.
Mình chọn per-call; đây là trade-off khác chứ không phải mình sai.

### 5. Egress allowlist thay vì no-network

```
-e OPEN_TERMINAL_ALLOWED_DOMAINS="pypi.org,github.com,*.npmjs.org"
```

Họ **cần** network để agent tự `pip install` lúc chạy. Nên thay vì cắt mạng, họ
allowlist domain. Đổi lại họ mất luôn khả năng nói "kết quả này không thể đến từ
internet" — đúng thứ mình đang giữ.

### 6. Dependency là config, không phải image rebuild

`OPEN_TERMINAL_PACKAGES` (apt), `OPEN_TERMINAL_PIP_PACKAGES`, `OPEN_TERMINAL_NPM_PACKAGES`.
Nặng hơn thì custom image, chặn bằng `TERMINALS_ALLOWED_IMAGES` (glob allowlist).
Docs nói rõ: sửa nhẹ thì dùng env var, đừng build image.

### 7. System prompt + tool description là bề mặt operator tune được

- `OPEN_TERMINAL_SYSTEM_PROMPT` — thay hoàn toàn, có placeholder `{{os}} {{kernel}}
  {{arch}} {{hostname}} {{user}} {{shell}} {{python_version}} {{home}}`
- `OPEN_TERMINAL_INFO` — *append* vào prompt sinh tự động (giữ phần mô tả runtime)
- `OPEN_TERMINAL_EXECUTE_DESCRIPTION` — "tool inventory for AI agents", tức là
  **mô tả tool đưa cho model cũng là config**

Ý hay: mặc định họ tự sinh prompt mô tả runtime thật (OS, kernel, python version)
thay vì để model đoán môi trường.

### 8. Trung thực về ranh giới — giống văn hoá ADR của mình

Hai câu đáng đóng khung:

> File browser home boundary: **"This is not a security boundary."** — nó là UX,
> client-side, server trả `GET /files/cwd` → `root.path`; *"terminal commands and
> model tools still operate with the permissions of the terminal container."*

> `CODE_INTERPRETER_BLOCKED_MODULES`: **"an opt-in convenience filter, not a
> security boundary."**

Và cảnh báo Docker socket: *"effectively root access on your machine."*
Cùng một kỷ luật `adr/0011` đã dùng khi loại `RestrictedPython`.

### Chi tiết vận hành đáng ghi

| Thứ | Giá trị |
|---|---|
| `OPEN_TERMINAL_MAX_SESSIONS` | 16 |
| `OPEN_TERMINAL_EXECUTE_TIMEOUT` | unset mặc định (!) |
| `OPEN_TERMINAL_SESSION_CWD_TTL` | 604800 (7 ngày) |
| Log | dir + `MAX_LOG_SIZE` 50MB + `LOG_RETENTION` 7 ngày + flush interval/buffer |
| Scheduled reset | cron 5 field / `@weekly` / `@monthly` / ISO datetime, có `timezone`, **idle-safe** (chờ session rỗi mới xoá), chỉ xoá file persisted |
| Config precedence | defaults → `/etc/open-terminal/config.toml` → `~/.config/...` → env → CLI flag |
| Tool loop | native mode = **unlimited multi-round**, cần `chat_id` + `id` + `stream:true` + `session_id`; legacy mode = **1 round** |
| Secrets | orchestrator **từ chối forward** `OPEN_TERMINAL_API_KEY` từ policy, tự sinh key riêng mỗi instance |

Cảnh báo secrets của họ: *"Policy env vars are visible to the user inside their
terminal. Do not put secrets in a policy unless users are allowed to see and use them."*

### Kỷ luật domain workflow (đáng học nhất trong nhóm use-case)

Workflow `database-analysis`, prompt verbatim:
> *"$Database Analyst Connect to my PostgreSQL database at `db.example.com` and
> analyze the `orders` table. What are our top-selling products this quarter?"*

Quy tắc họ áp cho agent:
1. Explore schema trước
2. **Hiện SQL ra trước khi chạy** để user kiểm
3. Luôn thêm `LIMIT` chống pull nhầm cả bảng
4. Aggregate + `GROUP BY` cho summary, đóng connection khi xong
5. Credential qua env, **không bao giờ paste vào chat**: *"Never paste passwords
   directly in chat: they get saved in chat history."*

Workflow `data-reports`: profile → clean (lưu bản sạch riêng) → analyze (chốt 3–5
finding) → visualize → assemble → store. Cộng một câu về giọng điệu:
*"Always explain findings in plain English, not statistical jargon."*

---

## Phần 2 — Chuyển được về Stock_Massive

Xếp theo giá trị thật. Cả bốn đều là *đối chiếu*, chưa sửa gì.

### A. Executor chỉ có stdlib — trần năng lực thật (giá trị cao nhất)

Probe trực tiếp qua queue volume hôm nay:

```
libs available: ['statistics', 'math', 'json', 'decimal']
numpy / pandas / scipy / matplotlib / sklearn → KHÔNG có
```

`apps/executor/Dockerfile` là `python:3.12-slim` + `COPY server.py`, không pip
install gì. Nên "bounded Python arithmetic" hiện tại nghĩa là **toán stdlib tay
không**: covariance matrix, OLS, percentile theo interpolation... đều phải tự viết
trong 8.000 ký tự, và mỗi lỗi số học là một lượt tool bị đốt.

Lối ra của Open WebUI cho đúng bài này là `OPEN_TERMINAL_PIP_PACKAGES`. Lối ra của
mình gọn hơn và **không cần network lúc chạy**: `pip install numpy` ngay trong
`apps/executor/Dockerfile` lúc build.

Ranh giới phải giữ: numpy **không** nâng derived thành registered evidence.
`adr/0010` vẫn là cửa duy nhất cho signal mới. Nó chỉ làm derived evidence bớt đau.

Không chạm tool schema → **không kích hoạt eval gate**.

### B. `/tmp` là kênh chia sẻ xuyên Turn và xuyên user (bug thật, đã chứng minh)

`_bounded_child` tạo `TemporaryDirectory(dir="/tmp")` cho mỗi job và dọn sau — nhưng
code **được** ghi thẳng vào `/tmp`, và tmpfs đó là của *container*, không phải của
*job*. Probe hai lần gọi rời nhau:

```
call 1:  open('/tmp/x.txt','w').write('hello')
call 2:  os.path.exists('/tmp/x.txt')  ->  True
```

Một executor phục vụ mọi Turn của mọi user. Nên Turn của user A ghi được dữ liệu
mà Turn của user B đọc lại — bounded bởi tmpfs 64m và mất khi restart, nhưng vẫn là
kênh xuyên user mà `adr/0019` không mô tả, và là state tồn tại trong một thiết kế
tuyên bố stateless.

Open WebUI giải bài này bằng per-user container + scheduled reset — quá nặng cho
mình. Lối ra tương xứng: cấp cho mỗi job một tmpdir riêng làm `TMPDIR`/`HOME` và
xoá sau, hoặc dọn `/tmp` giữa các job.

Cộng với lỗi orphan process ở báo cáo trước, cả hai đều nằm trong
`apps/executor/server.py` và đều là "child bounded, container thì không".

### C. `OPEN_TERMINAL_EXECUTE_TIMEOUT` unset — đối chiếu có lợi cho mình

Timeout mặc định của họ là *không có*. Của mình cứng ở `min(10.0, ...)` cả hai phía
(`compute.py:57`, `server.py:55`). Không phải chỗ nào mình cũng thua; đây là chỗ
mình chặt hơn và nên giữ.

Tương tự `OPEN_TERMINAL_MAX_SESSIONS=16`: đó là phiên bản *khai báo tử tế* của cái
mình đang làm ngầm — queue tuần tự một slot. Nếu sau này chạm giới hạn, cap tường
minh + lỗi rõ ràng tốt hơn là để client ăn `ExecutorUnavailable` oan.

### D. Kỷ luật `database-analysis` — mình đã vượt, nên ghi nhận chứ không copy

"Hiện SQL trước khi chạy" là chuẩn minh bạch của họ. Mình mạnh hơn một bậc: mọi tool
call đều vào `agent_tool_call` trace, và `grounding.py` **đối chiếu con số trong
prose với trace đã cite** — figure lệch trace là hard failure (`adr/0018`). Không
cần bê gì về.

Còn quy tắc credential thì mình đã ở phía an toàn hơn bằng thiết kế: executor chạy
`env={}` (probe xác nhận chỉ còn `LC_CTYPE`), không có DB credential nào để lộ.
Trong khi workflow của họ **cố ý** đẩy `DB_PASS` vào env của sandbox.

---

## Phần 3 — Cố ý không lấy, kèm lý do

| Thứ của họ | Vì sao không |
|---|---|
| Network + egress allowlist | Biến `run_python` thành đường tắt fetch API, vượt provenance và quota vnstock. Deps bake lúc build là đủ, không cần mạng runtime |
| Shell / filesystem / package install lúc chạy | Phá ranh giới evidence `adr/0019`; state bền là thứ `run_python` cố ý không có |
| Stateful workspace + vòng lặp sửa-rồi-chạy-lại | Giá trị của họ đến từ *iterate tới khi ra kết quả đúng*. Với khuyến nghị đầu tư, "chạy lại tới khi số đẹp" là chính cái `adr/0018` tồn tại để chặn. `MAX_TOOL_ROUNDS=4` đã đủ cho retry lành mạnh |
| Xuất PNG / PDF / HTML dashboard | Chart là **Widget** theo `adr/0012`, không phải ảnh render. `finance-dashboard` của họ đẻ ra file HTML — mình không đi đường đó |
| `EXECUTE_DESCRIPTION` (tool description là env var) | **Sẽ phá eval gate.** `tool_catalog_version` là hash của tool *schema*, và Eval Fixture pin đúng version đó (`adr/0016`); harness từ chối chạy khi pin và deployment lệch. Description cấu hình được ⇒ catalog version phụ thuộc môi trường ⇒ fixture chết. Từ chối dứt khoát |
| Terminals orchestrator, policy, K8s operator, scheduled reset | Cần **Enterprise License**, không lấy được code. Và lý luận `adr/0011` vẫn đúng: đây là hạng mục hạ tầng nặng nhất cho một nhóm user nội bộ |
| `MULTI_USER=true` một container | Docs tự nhận không dùng được cho untrusted. Mô hình per-call của mình đã tốt hơn ở trục này |
| Log riêng + retention 7 ngày | `agent_tool_call` đã là audit trail, và nó gắn với Turn — mạnh hơn log file rời |

---

## Khuyến nghị

Chỉ hai việc, cả hai gọn trong `apps/executor/`, cả hai **không chạm tool schema nên
không kích hoạt eval gate**:

1. **`pip install numpy` trong `apps/executor/Dockerfile`** (A). Nâng trần năng lực
   thật của derived evidence mà không nới một ranh giới nào. Deps bake lúc build,
   container vẫn networkless.
2. **Cô lập `/tmp` theo job** (B) + **process-group kill** (báo cáo trước). Hai lỗi
   cùng một gốc: bound child mà không bound container.

Cập nhật `adr/0019` sau khi sửa: ghi orphan process và `/tmp` chia sẻ là residual
risk đã xử lý, và ghi rõ deps bake-at-build là *cách* giữ được lời hứa networkless
— để lần sau không ai lý luận rằng cần mở mạng để có numpy.

Không xây orchestrator, không mở mạng, không thêm filesystem. Muốn năng lực mới thì
cửa vẫn là tool mới qua Signal Registry (`adr/0010`).

---

## Câu chưa rõ

- Có ai đọc `agent_tool_call WHERE status='unknown_tool'` từ khi ship `run_python`
  chưa? Nó là dữ liệu duy nhất nói được model đang *muốn* tính gì mà stdlib không
  cho. Quyết numpy hay không nên dựa vào đó chứ không phải vào Open WebUI.
- Ngoài numpy còn cần gì? Chọn theo trace, không theo danh sách "thường dùng".
- `EXECUTOR_ENABLED` ở production hiện là gì? (còn nợ từ báo cáo trước)

# Terminal tool cho agent — đánh giá tích hợp

**Ngày:** 2026-08-21 · **Phạm vi:** đánh giá + khuyến nghị, không sửa code · **Nhánh:** develop

## Kết luận trước

Capability này **đã tồn tại, đã ship, và đang chạy**. Không có gì để "tích hợp" —
`run_python` là tool thứ 9 trong catalog, chạy trên service `executor` riêng
(networkless, file-queue), quyết định kiến trúc nằm ở `docs/adr/0019` (supersede
`0011`). Container đã up 4 ngày trong stack dev, `EXECUTOR_ENABLED=true` ở `.env`.

Nên câu hỏi thật không phải "có làm không" mà **"còn thiếu gì"**. Trả lời: một lỗ
hổng self-DoS đã chứng minh được, một quyết định budget cần chốt, phần còn lại là
ranh giới cố ý đừng nới.

## Cái đang có

| Lớp | Hiện trạng |
|---|---|
| Contract | `code` + `inputs` JSON → `result` JSON. Không file, không plot (`adr/0012`) |
| Giới hạn API-side | `MAX_CODE_CHARS=8_000`, `MAX_INPUT_BYTES=16KB`, timeout ≤10s (`tools/compute.py`) |
| Giới hạn executor | output 64KB, stdout 16KB, `cpus 0.5`, `mem 256m`, `pids_limit 64`, tmpfs 64m noexec |
| Isolation | `network_mode: none`, `read_only`, UID 65534, `cap_drop: ALL`, `no-new-privileges`, `env={}`, child chạy `python -I -S` |
| Evidence | Envelope `claim_class: "derived"` → `EvidenceSource.DERIVED` → `_untrusted_claim()` (`grounding.py:142,776`). Không lập được verdict / reference price / price zone |
| Fail-safe | `executor_enabled=False` mặc định → tool **vắng** khỏi catalog, không phải hứa suông |
| Đo cầu | `agent_tool_call.status='unknown_tool'` đếm tool model muốn mà không có |

### Probe thực tế (chạy hôm nay qua queue volume)

| Thử | Kết quả |
|---|---|
| Arithmetic (`pstdev` → annualized vol) | ✅ trả `{"derived": {claim_class: "derived", result: {...}}}` |
| `socket.gethostbyname` | ⛔ `gaierror: name resolution` — không có network namespace |
| Ghi `/x` | ⛔ `Read-only file system` |
| `while True: pass` | ⛔ `execution exceeded the wall-clock limit` |
| `os.environ` | ✅ chỉ `{LC_CTYPE}` — không credential, không app env |
| Đọc `/etc/passwd` | ✅ đọc được (base image; không có source mount, không có secret) |
| `subprocess.run(["id"])` | ✅ `uid=65534(nobody)` |

## Khoảng trống

### 1. Process cháu sống sót qua wall-clock kill — self-DoS (thật, đã chứng minh)

`_bounded_child` gọi `process.kill()` trên **duy nhất** child trực tiếp
(`apps/executor/server.py:81-83`). Child spawn `subprocess.Popen` rồi treo: cha bị
kill, cháu được reparent về `server.py` và **sống mãi**.

```
nobody 19474 99564  /usr/local/bin/python -c import time while True: time.sleep(1)
                ^ PPID = server.py, sau khi cha đã bị kill vì timeout
```

Bán kính: `pids_limit 64` → ~62 orphan là executor không fork được nữa, **mọi**
`run_python` sau đó fail; orphan quay CPU thì ăn hết `cpus 0.5` làm chậm tất cả.
Không phải escape khỏi container, nhưng là degradation vĩnh viễn tới khi restart.

Hướng sửa (~5 dòng, gọn trong `apps/executor/server.py`): `Popen(...,
start_new_session=True)` rồi `os.killpg(os.getpgid(pid), SIGKILL)` thay `kill()`.
**Không chạm tool schema → không kích hoạt eval gate.**

### 2. `run_python` ăn cùng budget với network (quyết định cần chốt)

`data_access=ToolDataAccess.EXTERNAL` (`compute.py:104`) → tính vào
`MAX_EXTERNAL_TOOL_CALLS = 6` chung với `web_search`/`fetch_url`/MCP
(`loop.py:250,1111`). Một phép cộng networkless tốn đúng bằng một lượt fetch web.

Đây là chọn lựa, không phải bug: `EXTERNAL` là cách nói "không phải store". Nhưng
hệ quả thực tế là model phải cân giữa tính toán và tra cứu, trong khi nút thắt
thật (quota vnstock, tiền Tavily) chỉ nằm ở nhóm sau. Nếu tách, đó là thay đổi
**agent loop → bắt buộc Eval Report** (`docs/agents/eval-battery.md`).

Khuyến nghị: chưa tách. Chỉ tách khi trace cho thấy `run_python` thực sự đang
ép cạn budget — dữ liệu đó lấy từ `agent_tool_call`, không cần đoán.

### 3. Queue tuần tự, một slot

`main()` xử lý request lần lượt, mỗi job tới 10s + `POLL_SECONDS=0.02`. Hai Turn
song song thì Turn thứ hai chờ trọn job đầu; client-side deadline chỉ
`timeout + 2.0s` (`compute.py:59`) nên Turn thứ hai dễ ăn `ExecutorUnavailable`
dù executor vẫn khỏe. Cũng nên biết: `os.chmod(self.queue, 0o777)` — chấp nhận
được vì chỉ `api` và `executor` mount volume đó.

Mức độ: chưa đau ở user count hiện tại. Ghi nhận, đừng sửa sớm.

### 4. Đọc được rootfs base image — non-issue

`/etc/passwd` đọc được, nhưng không có source mount, không DB credential, `env={}`.
Không có gì đáng lấy. Ghi vào ADR như risk đã chấp nhận, không sửa.

## Ranh giới cố ý — đừng nới

Nếu "terminal" nghĩa là shell + filesystem + network, thì mỗi phần đều phá một
invariant đang giữ hệ thống đứng được:

- **Network trong sandbox** → biến `run_python` thành đường tắt fetch API, vượt
  toàn bộ provenance và quota (`plans/reports/research-260820-2327` đã ghi nhận).
- **RPC gọi lại tool khác từ sandbox** → phá `ToolDataAccess` và trace/budget
  per-call, vì chỉ dispatch qua `ToolCatalog.dispatch` mới được trace.
- **Xuất file/ảnh** → chart là Widget theo `adr/0012`, không phải ảnh render.
- **Derived → registered evidence** → mất đúng thứ `adr/0018` tồn tại để chặn.

## Khuyến nghị

1. **Sửa process-group kill** (#1). Lỗi thật, đã chứng minh, sửa nhỏ, không eval gate.
2. **Cập nhật `adr/0019`**: bổ sung orphan-process là residual risk đã xử lý; ghi rootfs readable là risk đã chấp nhận.
3. **Không xây thêm "terminal"**. Muốn nới capability thì lối ra đúng là **tool mới qua Signal Registry** (`adr/0010`), như `adr/0011` đã viết: *"the first exit is a new tool, not a sandbox"*.
4. **Đọc trace trước khi tách budget** (#2), đừng chốt bằng suy luận.

## Câu chưa rõ

- `EXECUTOR_ENABLED` ở production đang là gì? Repo chỉ cho thấy dev `.env=true`, default code `False`.
- Đã có ai đọc `agent_tool_call WHERE status='unknown_tool'` từ khi ship `run_python` chưa? Đó là dữ liệu duy nhất nói được capability này còn thiếu gì thật.

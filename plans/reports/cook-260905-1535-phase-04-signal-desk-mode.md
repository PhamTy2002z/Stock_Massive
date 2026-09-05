---
title: "Phase 4 — Signal Desk mode và market evidence trong deep pipeline"
date: 2026-09-05
status: DONE
plan: "plans/260905-0001-signal-desk-visual-harness/phase-04-evidence-readiness-agent-loop.md"
---

# Phase 4 — Signal Desk mode và market evidence trong deep pipeline

## Đã làm

| File | Việc |
|---|---|
| `apps/api/src/agent/schemas.py` | `mode: Literal["chat","signal_desk"] = "chat"` trên `CreateTurnRequest`. |
| `apps/api/src/agent/router.py` | Đọc `mode` từ body, không suy từ text. |
| `apps/api/src/agent/loop.py` | `SIGNAL_DESK_MODE`; note variant chọn theo **surface** đã resolve. |
| `apps/api/src/agent/turns.py` | `mode` → `create_turn`, → lane, → `RunningTurn`, → toolset của loop. |
| `apps/api/src/agent/service.py` | `loop_factory` nhận `toolsets`. |
| `apps/api/src/agent/evidence/pipeline.py` | `MARKET_PLANNER_NOTE` / `MARKET_RESEARCH_NOTE` + `planner_note()` / `research_note()`. |
| `apps/api/src/agent/prompt/sections.py`, `domain/vn_equity.py` | Gỡ mâu thuẫn prompt (xem dưới). |
| `apps/web/src/lib/alpha-desk/api.ts` | Gửi `mode` — **cùng commit** với schema. |
| Tests | transport, lifecycle, notes mới, 4 loop-factory double. |

**Không có file mới ở runtime.** Không `readiness.py`, không digest, không state
machine thứ hai — đúng như phase doc đã cắt.

## Quyết định lệch plan, và lý do

### Note variant chọn theo surface, không theo mode

Plan viết "biến thể `PLANNER_NOTE`/`RESEARCH_NOTE` cho signal_desk". Triển khai
key theo `MARKET_TOOL in surface.by_name` chứ không theo mode.

Lý do: hai thứ này chỉ khác nhau ở đúng một trường hợp — Turn signal_desk trên
host mà provider bị tắt (`deployment_profile != personal_internal`, hoặc flag
off, hoặc package không import được). Ở đó **surface đúng và mode sai**: một note
bảo model gọi `get_market_data` khi tool không có trong danh sách chỉ tốn một
round để model phát hiện ra. Đây là hai-chiều theo roadmap §"Cửa một chiều và
hai chiều" (cấu trúc module nội bộ), không cần deviation.

### Prompt nói dối khi Turn cầm tool đọc giá

`HONESTY` viết "Dữ kiện phụ thuộc thời điểm phải được đọc … **bằng công cụ
web**" và `vn_equity` chỉ hướng dẫn `web_search` + `fetch_url`. Với một Turn
signal_desk đang cầm `get_market_data`, cả hai câu đều sai và rủi ro thật là
model **từ chối dùng tool nó đang có**.

Sửa tối thiểu:

- `HONESTY`: "bằng công cụ web" → "bằng công cụ của lượt này"; thêm nửa còn lại
  của quy tắc — *không được nói rằng không đọc được một thứ mà một công cụ trong
  danh sách đó đọc được*.
- `vn_equity`: thêm một câu — khi lượt này có công cụ dữ liệu thị trường, mọi số
  giá/khối lượng phải đến từ nó, vì snippet không kèm đơn vị, múi giờ hay ranh
  giới phiên.

**Giữ nguyên** "Hệ thống không có bảng giá trực tiếp": câu đó vẫn đúng —
`get_market_data` trả nến **đã đóng**, không phải bảng giá live — và
`test_prompt_is_honest_about_missing_local_analysis_runtime` khoá nó có chủ đích.

### `signalDesk` boolean ở client → `mode` chuỗi trên wire

Giữ boolean phía browser (đó là bản chất của một pill hai vị trí) và dịch sang
mode có tên ở ranh giới request. Client luôn gửi `"chat"` hoặc `"signal_desk"`,
không bao giờ bỏ trống: bỏ trống làm "người đọc tắt desk" và "client này cũ hơn
desk" thành cùng một request, mà chỉ một trong hai là lựa chọn.

### Bốn test double phải đổi chữ ký

`loop_factory` thêm kwarg `toolsets` nên bốn double trong test đỏ (Turn treo chờ
settle, không phải fail nhanh — mất một lượt chẩn đoán). Đã sửa cả bốn nhận
`toolsets`, và double trong `test_agent_turn_lifecycle.py` nay **truyền tiếp**
vào `AgentLoop` để test khẳng định trên wiring chứ không phải trên double.

## Đo được

```
cd apps/api && pytest -q            1508 passed, 3 deselected
compileall src tests golden         OK
pnpm --dir apps/web lint            OK
pnpm --dir apps/web type-check      OK
pnpm --dir apps/web test            471 passed (40 files)
E2E_NEXT_DIST_DIR=.next-verify pnpm build   OK
git diff --check                    sạch
```

Retired-path scan: mọi hit `Study|widget|indicator` còn lại đều là câu khẳng
định rằng năng lực đó **không tồn tại**, hoặc là "indicator" theo nghĩa UI
(đèn báo chia sẻ màn hình). Không có board nào quay lại.

## Test đã thêm

| Test | Khoá điều gì |
|---|---|
| `test_the_same_words_in_two_modes_are_two_questions` | `mode` nằm trong idempotency payload → 409, không trả nhầm Turn cũ. |
| `test_the_signal_desk_mode_skips_the_router_and_widens_the_surface` | Câu "FPT?" ngắn, không keyword — router sẽ cho LIGHT; mode cho DEEP + surface có market. |
| `test_a_chat_turn_cannot_reach_the_market_read` | Nửa còn lại: chat = `CHAT_TOOLSETS`, không có `get_market_data`. |
| `test_agent_signal_desk_notes.py` (4) | Note chọn theo surface; note market nêu đủ ba rule ledger enforce; surface thứ ba không mua thêm ceiling. |
| `api.test.ts` (2) | Client gửi `signal_desk` khi bật, `chat` khi tắt **và** khi không ai set. |

Test đã có sẵn phủ hai case còn lại — request không `mode` byte-compatible, và
`mode` lạ → 422 trước khi có row. Không viết trùng.

Status: DONE

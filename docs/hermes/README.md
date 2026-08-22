# Hermes Agent — hồ sơ khảo sát

Đợt đọc code `NousResearch/hermes-agent` (MIT, sparse clone HEAD `f43eabe`,
2026-08-20/21) để rút bài học cho `apps/api/src/agent` của Stock_Massive.

Chỉ giữ **research**. Plan `260821-0020-agent-upgrade-hermes-lessons`, các report
thi công (B1/B2a/Frontend C), lần chạy Golden Question Set và hai brainstorm nằm
ngoài phạm vi thư mục này — chúng vẫn ở git history của `develop` và ở worktree
`.claude/worktrees/hermes-harness/plans/`.

Phủ: **365 file Python / 349.505 dòng, UNASSIGNED = 0** — kiểm chứng ở
`hermes-coverage-260820-2352.md`.

## Đọc theo thứ tự này

| # | File | Dòng | Nội dung |
|---|---|---|---|
| 1 | [hermes-synthesis-260821-0030.md](hermes-synthesis-260821-0030.md) | 203 | **Bản hợp nhất** — kết luận của cả 9 vùng khảo sát. Vào đây trước. |
| 2 | [research-260820-2338-hermes-agent-teardown.md](research-260820-2338-hermes-agent-teardown.md) | 368 | Mổ tổng quan: quy mô, giá trị thật nằm ở đâu, cái gì đem được sang |
| 3 | [hermes-coverage-260820-2352.md](hermes-coverage-260820-2352.md) | 50 | Ma trận phủ — mỗi file Hermes gán cho đúng một report hoặc bị loại kèm lý do |

## Report theo vùng

| Vùng | File | Dòng | Đọc code gì |
|---|---|---|---|
| Vòng lặp + prompt | [hermes-core-loop](hermes-core-loop-260820-2352.md) | 362 | `conversation_loop.py` (8.436d), `prompt_builder.py`, `system_prompt.py`, `verification_*.py` |
| Vòng đời turn | [hermes-turn-lifecycle](hermes-turn-lifecycle-260820-2352.md) | 449 | Streaming, công bố tiến trình; đối chiếu `turns.py`/`loop.py`/`events.py`/`progress.py` + `live-turn.ts` |
| Tuyến LLM + subagent | [hermes-route-subagent](hermes-route-subagent-260820-2352.md) | 594 | `error_classifier.py` (taxonomy `FailoverReason`), kiến trúc subagent; đối chiếu `core/llm/*` |
| Context | [hermes-context](hermes-context-260820-2352.md) | 247 | 4 lớp context độc lập xếp tầng, mỗi lớp tắt/mở riêng — không có "context manager" |
| Tool | [hermes-tools](hermes-tools-260820-2352.md) | 246 | 4 lớp tool tách biệt |
| Ký ức + skill | [hermes-memory](hermes-memory-260820-2352.md) | 476 | Ký ức, skill, vòng tự cải thiện |
| Điều phối + state | [hermes-orchestrator-state](hermes-orchestrator-state-260820-2352.md) | 252 | `AIAgent`, tầng lưu trữ `hermes_state` |
| MCP / ops / eval | [hermes-mcp-ops-eval](hermes-mcp-ops-eval-260820-2352.md) | 231 | `mcp_tool.py` (8.235d), 3 transport, OAuth, monitoring, hook, executor |
| Web + bảo mật ngữ cảnh | [hermes-web-security](hermes-web-security-260820-2352.md) | 198 | `web_tools.py`, `url_safety.py`, `threat_patterns.py`, `redact.py`, `spill_safety.py`; đối chiếu `agent/tools/web.py` |

## Lưu ý khi dùng lại

- Mọi trích dẫn `path:line` trỏ vào sparse clone Hermes ở scratchpad (đã mất),
  không phải repo này. Muốn xác minh thì clone lại tại HEAD `f43eabe`.
- Phần đối chiếu với `apps/api/src/agent` viết trước commit `1e7b936`
  (thay harness bằng trợ lý tổng quát 5 tool). Kiến trúc phía ta đã đổi —
  đọc như bối cảnh lịch sử, không phải mô tả code hiện tại.

# Hermes Agent — ma trận phủ, để "không miss gì" là chuyện kiểm chứng được

Nguồn: `NousResearch/hermes-agent` (MIT), sparse clone 2026-08-20.
Tổng kiểm kê bằng script: **365 file Python / 349.505 dòng**. Mỗi file được gán
cho đúng một report, hoặc bị loại trừ kèm lý do. **UNASSIGNED = 0.**

## Trong phạm vi — 212 file / 218.429 dòng

| Vùng | File | Dòng | Report |
|---|---|---|---|
| Vòng lặp + dựng prompt (đọc trực tiếp) | 3 | 12.062 | `hermes-core-loop-260820-2352.md` |
| Quản lý context & nén | 12 | 20.401 | `hermes-context-260820-2352.md` |
| Kiến trúc tool | 22 | 14.481 | `hermes-tools-260820-2352.md` |
| Ký ức, skill, tự cải thiện | 22 | 20.695 | `hermes-memory-260820-2352.md` |
| Lane web + bảo mật ngữ cảnh | 10 | 6.060 | `hermes-web-security-260820-2352.md` |
| Vòng đời turn, streaming, tiến trình | 40 | 11.408 | `hermes-turn-lifecycle-260820-2352.md` |
| Độ bền tuyến LLM + subagent | 64 | 61.908 | `hermes-route-subagent-260820-2352.md` |
| Điều phối trung tâm + lưu trữ | 21 | 44.689 | `hermes-orchestrator-state-260820-2352.md` |
| MCP, observability, hook, eval, executor | 28 | 26.725 | `hermes-mcp-ops-eval-260820-2352.md` |

## Ngoài phạm vi — 143 file / 131.076 dòng

Loại trừ có lý do, không phải bỏ sót.

| Nhóm | File | Dòng | Vì sao loại |
|---|---|---|---|
| Chỉ dành cho coding agent | 54 | 54.592 | terminal, 7 sandbox backend, browser, file ops, patch/diff, LSP, computer-use, checkpoint git. `ADR-0011` đã từ chối sandboxed execution; không tool nào đọc được store của ta. **Ngoại lệ**: `tools/environments/*` vẫn được đọc trong report `mcp-ops-eval` để đối chiếu với `ADR-0019` |
| Bề mặt CLI/TUI | 30 | 41.983 | `cli.py` 21.445 dòng, spinner, kawaii face, kanban, cron, skills hub. Ta có Next.js shell 3 vùng |
| Voice / media | 24 | 22.880 | TTS, STT, wake-word, sinh ảnh/video. Non-goal |
| Desktop GUI | 26 | 5.599 | preview pane, pane focus, tour, pet. Non-goal |
| Nền tảng chat | 9 | 6.022 | Discord, Feishu, Home Assistant, Microsoft Graph, send_message. Non-goal |

## Cách kiểm lại

Script sinh bảng này nằm ở scratchpad phiên
(`cov2.txt`); nó gán chủ theo tên file và in ra danh sách `UNASSIGNED`. Bất kỳ
file mới nào không khớp luật nào sẽ hiện ra ở đó, nên bảng không thể âm thầm
thiếu.

## Trạng thái

| Report | Trạng thái |
|---|---|
| `research-260820-2338-hermes-agent-teardown.md` | xong — bản tổng hợp vòng một |
| `hermes-coverage-260820-2352` | xong — file này |
| 8 report vùng | đang chạy song song |

Sau khi cả 8 xong: hợp nhất thành một bản khuyến nghị port, xếp theo mức giảm
được ba nhóm triệu chứng đã đo (58% Turn `grounding_failed`, 36% Turn chết vì
route, khuôn trình bày analysis-first).

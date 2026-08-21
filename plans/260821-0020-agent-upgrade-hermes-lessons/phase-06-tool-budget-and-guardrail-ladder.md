---
phase: 6
title: "Ngân sách tool và thang guardrail"
status: pending
priority: P2
effort: "2-3d"
dependencies: [2, 5]
---

# Phase 6: Ngân sách tool và thang guardrail

## Overview

Hai việc: chống tràn context từ kết quả tool theo ba tầng, và thay bước nhảy
"allow → kết thúc Turn" bằng thang `allow → warn → block → halt` với halt rất muộn.

## Requirements

- Functional: kết quả tool lớn được giữ lại trên đĩa và thay bằng preview +
  tham chiếu, thay vì cắt cụt.
- Functional: gọi lặp một tool vô nghĩa được **cảnh báo** trước, chỉ halt khi lặp nhiều.
- Non-functional: controller guardrail không có tác dụng phụ — trả quyết định,
  runtime quyết biến nó thành gì.
- Non-functional: tool không rõ hình dạng mặc định coi là **có tác dụng phụ**
  (an toàn mặc định cho cái không biết).

## Architecture

### 6.1 Ba tầng chống tràn

Mẫu `tool_result_storage.py` của Hermes, nguyên văn: *"Defense against
context-window overflow operates at three levels."*

| Tầng | Cơ chế | Ta có gì |
|---|---|---|
| 1 | Mỗi tool tự cắt output trước khi trả | có — `MAX_TOOL_RESULT_BYTES` |
| 2 | Sau khi tool trả, vượt ngưỡng riêng của tool → lưu đầy đủ, trong context chỉ còn preview + đường dẫn | **chưa có** |
| 3 | Sau khi gom **mọi** kết quả tool của một lượt, tổng vượt trần → spill cái lớn nhất tới khi dưới trần | **chưa có** |

Tầng 3 là tầng ta thiếu quan trọng nhất: nhiều kết quả cỡ trung cộng lại tràn.

Phân giải ngưỡng theo khuôn `budget_config.py`: `pinned > config > registry >
default`. Ta đã có `data_ref` trong ý tưởng `docs/specs/0004` W1 — tầng 2 chính
là chỗ nó thuộc về.

Nơi lưu: ta không có sandbox, nên đơn giản hơn Hermes — lưu vào Postgres cạnh
`agent_tool_call.result`, hoặc một bảng phụ. **Không** dùng đĩa: worktree song
song và container ephemeral làm đường dẫn đĩa không đáng tin.

### 6.2 Thang guardrail

Mẫu `tool_guardrails.py`. Controller thuần, không tác dụng phụ:
*"Runtime code owns whether those decisions become warning guidance, synthetic
tool results, or controlled turn halts."*

Ngưỡng mặc định của Hermes — chú ý halt **rất** muộn:

| Điều kiện | Ngưỡng |
|---|---|
| Cùng một lời gọi y hệt thất bại | warn sau **2** |
| Cùng một tool thất bại | warn sau **3** |
| Tool idempotent không tạo tiến triển | warn sau **2** |
| Cùng một tool thất bại | **halt sau 8** |

Với `MAX_TOOL_ROUNDS = 4` của ta, halt-sau-8 không đạt được — nên ngưỡng phải
scale theo ngân sách round, không copy số. Đây là chỗ **không** được bắt chước số.

Hai frozenset cần phân loại tool của ta: idempotent (đọc store, web_search,
fetch_url, recall_facts) vs có tác dụng phụ (remember_fact, và mọi tool MCP/
không rõ — theo `tool_result_classification.py`: *"Unknown/plugin/MCP tools stay
effect-capable by default."*)

### 6.3 Gợi ý phục hồi trong lỗi tool

Mẫu `terminal_hints.py`: khi tool lỗi, stderr thô làm model đi sai hướng. Họ đào
tần suất từ DB sản xuất (*"a 250k-terminal-result window"*) rồi map hình dạng lỗi
phổ biến sang **một** câu gợi ý hành động kế tiếp.

Ta đã có `refusal_reason` trong `tools/catalog.py`. Nới nó mang gợi ý: refuse vì
Window Health thì nói rõ tool nào có cửa sổ ngắn hơn phục vụ được.

Quy tắc thiết kế của họ đáng giữ: chỉ khi lỗi; tối đa **một** gợi ý, khớp đầu
tiên thắng; chỉ quét đầu output; gợi ý nói **hành động kế tiếp**, không phải bài
chẩn đoán; hàm thuần, không I/O.

## Related Code Files

- Modify: `apps/api/src/agent/tools/catalog.py` — ngưỡng mỗi tool, gợi ý phục hồi
- Create: `apps/api/src/agent/tools/spillover.py` — tầng 2 + 3
- Create: `apps/api/src/agent/guardrails.py` — controller thuần, thang quyết định
- Modify: `apps/api/src/agent/loop.py` — gọi guardrail, áp quyết định
- Modify: `apps/api/src/agent/persistence.py` — lưu kết quả tool đầy đủ
- Modify: `apps/api/alembic/versions/` — migration cho bảng/cột spillover
- Modify: `apps/api/tests/test_agent_tool_catalog.py`, `test_agent_tool_suite.py`

## Implementation Steps

1. **Backup DB trước migration** (luật bắt buộc của repo).
2. Migration: chỗ lưu kết quả tool đầy đủ.
3. Tầng 2: vượt ngưỡng riêng → lưu, thay bằng preview + `data_ref`.
4. Tầng 3: tổng mỗi lượt vượt trần → spill cái lớn nhất trước.
5. Controller guardrail thuần + test bảng quyết định.
6. Nối vào `loop.py`: warn thành guidance trong message tổng hợp (dùng lại cơ chế
   nudge Phase 2), halt thành terminal.
7. Ngưỡng scale theo `MAX_TOOL_ROUNDS`, không copy số của Hermes.
8. Gợi ý phục hồi trong `refusal_reason`.
9. `make test`. **Eval Report** — phase này chạm tool catalog và
   `tool_catalog_version`, nên phải đóng băng lại Eval Fixture.

## Success Criteria

- [ ] DB đã backup trước migration
- [ ] Kết quả tool lớn: context chỉ còn preview + `data_ref`, bản đầy đủ truy được
- [ ] Tổng kết quả một lượt vượt trần → spill, Turn không tràn context
- [ ] Controller guardrail không có tác dụng phụ (test: gọi 100 lần, không state ngoài)
- [ ] Tool không rõ hình dạng mặc định là có-tác-dụng-phụ (test)
- [ ] Ngưỡng halt scale theo `MAX_TOOL_ROUNDS`, có test cho biên
- [ ] `refusal_reason` mang gợi ý hành động, tối đa một
- [ ] Eval Fixture đóng băng lại, `tool_catalog_version` cập nhật
- [ ] `make test` xanh + Eval Report đính PR

## Risk Assessment

**Rủi ro**: spill làm model mất dữ liệu nó cần, trả lời tệ hơn. **Tín hiệu**:
`answer_kinds.analysis` giảm sau phase này. **Phản ứng**: nâng ngưỡng tầng 2;
preview phải mang đủ hình dạng để model biết có gì trong `data_ref`.

**Rủi ro**: migration trên bảng `agent_tool_call` đang có dữ liệu. **Phản ứng**:
backup trước; cột mới nullable, thuần cộng thêm.

**Rủi ro**: copy ngưỡng 8 của Hermes vào hệ có 4 round → halt không bao giờ chạm,
guardrail thành vô dụng. **Tín hiệu**: `halt` count = 0 mãi. **Phản ứng**: ngưỡng
phải là hàm của `MAX_TOOL_ROUNDS` ngay từ đầu, không phải hằng số.

**Assumption có thể vỡ**: giả định tràn context do kết quả tool là vấn đề thật.
Nếu ops cho thấy `ContextOverflow` (Phase 1 phân loại) gần bằng 0, tầng 2/3 là
giải pháp cho vấn đề không tồn tại — khi đó **hoãn** phase này và làm Phase 7 trước.

## Rollback

Cờ tắt spillover; cột migration nullable nên giữ được. Guardrail có cờ riêng.

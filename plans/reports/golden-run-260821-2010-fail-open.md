# Golden Question Set trên harness fail-open

Ngày chạy: 2026-08-21. Model: `gpt-5.6-terra` (session), route CLIProxyAPI cục bộ.
Code: Phase 1 + Phase 2 sau khi sửa hết phát hiện của `code-reviewer`.
Mỗi câu một thread riêng — câu trước không được làm bằng chứng cho câu sau.

## Kết quả

| # | Status | Terminal reason | blocks / chars | citations / follow-up | Hạ cấp |
|---|---|---|---|---|---|
| G1 | `complete` | `—` | 2 / 381 | 0 / 5 | missing_as_of |
| G2 | `incomplete` | `grounding_failed` | 1 / 243 | 0 / 0 | — |
| G3 | `complete` | `—` | 1 / 77 | 1 / 4 | — |
| G4 | `complete` | `—` | 2 / 595 | 4 / 5 | — |
| G5 | `incomplete` | `grounding_failed` | 2 / 479 | 0 / 0 | missing_as_of |
| G6 | `complete` | `—` | 2 / 499 | 0 / 5 | unknown_field_path |
| G7 | `complete` | `—` | 3 / 675 | 12 / 5 | — |
| G8 | `incomplete` | `grounding_failed` | 1 / 243 | 0 / 0 | — |
| G9 | `complete` | `—` | 6 / 951 | 2 / 5 | missing_as_of, no_supporting_field |
| G10 | `complete` | `—` | 2 / 193 | 0 / 3 | — |
| G11 | `complete` | `—` | 1 / 99 | 0 / 4 | — |
| G12 | `incomplete` | `grounding_failed` | 1 / 243 | 0 / 0 | — |

## Ba con số của Phase 2

| Đo | Trước (baseline 1.4.0) | Lượt này |
|---|---|---|
| Màn hình trắng | 2/3 câu phiên live 2026-08-20 | **0/12** |
| Turn chết `grounding_failed` | 58% (100/171) | **4/12 = 33%** |
| `answer_kinds.analysis` | 0 | **10/12** |

Không câu nào ra màn hình trắng: câu ít chữ nhất là G3 với 77 ký tự. Bốn Turn chết đều
nhận `BLOCKED_TURN_NOTICE` (243 ký tự) — sàn có chữ, chưa phải câu trả lời dùng được.

## Bốn điều kiện nghiệm thu plan nêu tên

| Câu | Yêu cầu | Kết quả |
|---|---|---|
| G4 "Tình hình chứng khoán VN hôm nay" | số + citation chip + 3 follow-up | **Đạt** — 4 citation, 5 follow-up, 595 ký tự. Widget 0 (thuộc Phase 5) |
| G12 "Về STB thì sao" | số từ store + widget + tin từ web | **Không đạt** — `grounding_failed` / `figure_mismatch` |
| G11 "Hey bro" | trả lời hội thoại, không tool call | **Đạt** — `answer_kind=education`, 0 tool call, 4 follow-up |
| G9 "Có nên mua STB" | Gate còn hiệu lực: đủ điều kiện hoặc nói rõ thiếu gì | **Đạt** — `recommendation=blocked`, nêu `missing_as_of` + `no_supporting_field`, vẫn trả 951 ký tự phân tích |

## Vấn đề còn lại, và nó không thuộc Phase 2

Cả **4** Turn chết đều cùng một mã: `figure_mismatch` — con số model viết không khớp field
nó trích. Đây đúng là một trong 8 mã integrity mà G2 chốt **giữ chặn**, và `ADR-0018` gọi
là *"a hard failure in every block"*. Gate đang làm đúng việc; vấn đề là model viết sai số.

Phase 2 không chạm được vào đó. Ba đường có thể:

1. **Phase 3 (System Prompt Contract)** — cổng G1 định đưa prose chống bịa vào Contract.
2. Nudge hiện chỉ có 1 lượt, và với `figure_mismatch` thì `REPAIR_GUIDANCE` đã nói đúng
   điều cần nói. Nâng `MAX_GATE_ATTEMPTS` lên 3 là một cần cân đo — tốn thêm một lời gọi.
3. Kiểm xem model có đang trích **đúng** field nhưng narrate sai đơn vị/tỉ lệ hay không.
   Nếu vậy đó là lỗi trình bày field, không phải lỗi bịa số, và sửa ở tool payload rẻ hơn.

## Hạ cấp đang phát sinh

`missing_as_of` (G1, G5, G9) và `unknown_field_path` (G6) chiếm toàn bộ. Trước Phase 2 cả
hai **kết thúc Turn**; giờ chúng hạ cấp và Turn vẫn trả lời — đúng hiệu ứng nhắm tới.
Không mã integrity nào bị hạ cấp.

## Ảnh hưởng thấy được của các fix sau review

| Fix | Bằng chứng |
|---|---|
| Dedupe notice trùng | G1: 11 block → **2 block** (cùng câu `missing_as_of` không còn lặp) |
| `recommendation` chỉ đếm khuyến nghị thật | G1: `blocked` → **`not_applicable`** (G1 là prose, chưa từng định khuyến nghị) |
| Fallback trước nudge | Không ca nào kích hoạt trong lượt này (mọi `figure_mismatch` xảy ra ở attempt 1); phủ bằng unit test |

## Giới hạn của lượt đo

- Hạn mức Turn/ngày cắt ở câu thứ 7; 5 câu còn lại chạy trên user thứ hai. Không ảnh
  hưởng kết quả — quota là per-user, mỗi câu vẫn thread riêng.
- LLM có phương sai: G5 lượt trước `complete`, lượt này `grounding_failed`. Một lượt 12 câu
  không thay được gate run của Eval Battery.
- Widget 0/12 ở mọi câu. Thuộc Phase 5, không phải hồi quy.

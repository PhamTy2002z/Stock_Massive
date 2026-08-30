# Phase 03 — body pack vào prefix ổn định, và một danh tính cho cái đầu ấy

**Ngày:** 2026-08-29 · `PROMPT_VERSION` 3.0.0 → **3.1.0**

## Cái đổi

Body của pack đi từ **system note dán đuôi mỗi call** (sau mọi kết quả tool) vào
**một block bên trong system message**, giữa core và giá trị render cho Turn:

```
[core — giống nhau mọi Turn mọi người đọc]   breakpoint
[body pack — giống nhau mọi Turn dưới một pack]   breakpoint
[- today: … / - user_name: …]
```

Thứ tự là **tần suất thay đổi**, và đó chính là định nghĩa của prefix cache:
route đọc lại phần cache tới byte đầu tiên khác nhau. Body đặt sau ngày sẽ chỉ
cache được core; body dán đuôi — chỗ nó vừa rời khỏi — không cache được gì của
chính nó.

**Hai breakpoint chứ không một**, vì hai block hỏng theo hai đồng hồ: core đổi
khi ai đó sửa prompt, body đổi khi swap domain. Một breakpoint trên chuỗi ghép
sẽ void core mỗi lần pack nhúc nhích — mà core lớn gấp bảy lần body.

## Trung tính về token, đúng như thiết kế

| | Phase 02 | Phase 03 |
|---|---:|---:|
| Constructed token | 687.269 | **687.145** |
| `domain_body` | 21.235 | 21.111 |
| Mọi layer khác | — | **không đổi một token** |

**−124 token, và toàn bộ là `MESSAGE_OVERHEAD_TOKENS`** — 4 token × 31 lượt gọi
từng mang body như một message riêng. Body giờ chia chung message với core nên
không còn phí message của riêng nó. Không có gì khác dịch chuyển, và đó là bằng
chứng đây là một phép dời chỗ chứ không phải một phép cắt.

## Reservation biến mất, không phải được sửa

Trước: `_construct` trừ `domain_body_tokens(state)` khỏi ceiling, `_call` append
message. Một *ước lượng* về một message do người khác dựng.

Sau: body nằm trong transcript, `estimate_tokens` đo nó từ **chuỗi thật sự gửi
đi**, như mọi block khác của prompt. `_appended` chỉ còn ba note. Không còn hai
biểu thức phải khớp nhau vì chỉ còn một phép đo.

`domain_body_tokens` giữ lại — câu hỏi "Turn này trả bao nhiêu cho playbook" vẫn
đáng hỏi và đây là chỗ duy nhất viết ra câu trả lời — nhưng docstring đã nói rõ
nó không còn reserve gì.

## Cache identity có caller runtime đầu tiên

`cache_key(model, tool_surface_digest, pack_identity)` tồn tại từ C5 và **chưa
từng có caller runtime nào**. Giờ nó tính một lần mỗi Turn, ngay sau
`resolve_tool_surface`, và đi cùng mọi `CompletionRequest` qua `metadata`.

Trong đó: model · `PROMPT_VERSION` · `PROMPT_HASH` · digest tool surface ·
`pack.identity`. Không có: user, thread, ngày, mode, câu hỏi. Test khẳng định
bằng **đẳng thức**: hai Turn khác nhau mọi thứ — người đọc, câu hỏi, ngày, mode
— sinh **một** identity.

`metadata` **không lên wire** (`transport._body` không đọc nó), và đó là chủ ý:
route chưa được chứng minh đọc bất kỳ trường cache nào, gửi một trường nó bỏ qua
là một lời khẳng định trong body request mà không gì phía sau tôn trọng.
`llm_prompt_cache_control_enabled` vẫn `False`.

## Vì sao version bump dù không một chữ nào đổi

3.1.0. Vị trí một chỉ dẫn **so với một trang văn bản không đáng tin** là một
phần của "model đã được nói gì". Một artifact ghi dưới 3.0.0 được sinh ra bởi
một cách sắp xếp khác của cùng những câu đó.

## Rủi ro còn mở

**Instruction precedence.** Body giờ đứng *trước* mọi kết quả tool thay vì sau.
Nếu Golden live ở phase 05 thấy một gate C1 tụt, đây là nghi phạm đầu tiên và
rollback là trả body về tail — phase 01/02 vẫn độc lập và dùng được.

## Trạng thái

- [x] Body chỉ có khi trigger bật, đúng một lần, từ call kế tiếp tới cuối Turn
- [x] Body đứng trước runtime/user/tool trong wire content thật
- [x] Không token body nào vừa trong context vừa bị reserve — `_appended` còn ba note
- [x] Pack/surface đổi thì identity đổi; ngày/tên/câu hỏi không làm đổi
- [x] `cache_control` vẫn off; wire không nhận trường mới
- [x] C5 domain-pack test xanh nguyên (25 pass) · `make test` **1739 pass**

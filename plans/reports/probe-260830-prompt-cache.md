# Probe: prefix cache tự động của route, trên đúng cái đầu C2 dựng

- Ngày chạy: 2026-08-30
- Model: `gpt-5.6-terra`
- `prompt_cache_control`: **False**
- Danh tính cái đầu: `gpt-5.6-terra|3.2.0|6cde2ded5198848d0e9b621c9b61fb7cf4d63cc45444c8591ab625420aff2921|6d7fc32cfd41e99e1c2f78c1563bbf1db78f32a12e3a734874d7ccc8b17f23ae|cc7d0bfad33a3ffd4c293f1cdcb3366729b93fbf7e59f6d4aa0f855e54623228`

| Prefix | Token prefix | Lượt | Hit | Fresh | Cached read | Cache write | Tỷ lệ cached |
|---|---:|---:|---:|---:|---:|---:|---:|
| `core` | 5,695 | 4 | 1 | 16,397 | 4,864 | 0 | 22.9% |
| `core+domain-body` | 6,376 | 4 | 4 | 4,149 | 19,456 | 0 | 82.4% |
| **tổng** | | 8 | 5 | 20,546 | 24,320 | 0 | 54.2% |

## Đối chiếu ledger

| | Provider nói | `llm_call_usage` ghi |
|---|---:|---:|
| Fresh | 20,546 | 20,546 |
| Cached read | 24,320 | 24,320 |
| Cache write | 0 | 0 |
| Số dòng | 8 | 8 |

Chi phí probe: **51,887 µUSD**.

## Đọc thế nào

Đơn vị là **tổng**, không phải từng lượt. Đo 2026-08-23 trên chính route
này ghi nhận load balancer phục vụ 3 hit trên 8 lượt cùng một prefix, nên
một lượt miss không nói được gì; một tổng bằng không thì có.

Verdict: cache **đang đọc**.

Không sửa cờ nào từ script này. `llm_prompt_cache_control_enabled` là một
quyết định đã kiểm chứng và một phép đo không đảo nó — nó chỉ nói phép đo
cũ còn đúng hay không trên cái đầu mới.

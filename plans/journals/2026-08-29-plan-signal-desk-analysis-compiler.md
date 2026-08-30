---
title: Plan Signal Desk analysis compiler
date: 2026-08-29
summary: Brainstorm + research landscape rồi chốt plan mười phase đưa Signal Desk từ Study viết sẵn sang compiler query → compute → render, giữ bất biến "model không gõ số".
---

# Plan Signal Desk analysis compiler

## What happened

Scout code Signal Desk và research landscape generative-UI / BI copilot /
finance copilot chạy song song. Kiểm kê DB thật lúc 22:55 đính chính một câu
sai trong brainstorm: kho BCTC **đã có** (`financial_statement_line` 302.528
dòng, 1.235 mã, 8 quý) nhưng chỉ một Study đọc — câu "so sánh BCTC VIC vs VCB"
tệ vì thiếu dây nối, không thiếu dữ liệu. Ghi
`plans/reports/brainstorm-260829-2240-signal-desk-generative-bi.md`, rồi tạo
plan `plans/260829-2304-signal-desk-analysis-compiler` mười phase.

## Decision

Rejected A (thêm Study tới ≥10 — đoán trước câu hỏi) và B (Lovable/v0 sinh
code, Vega-Lite tự do — số đi qua model). Chọn C: ba trục độc lập và tổng
quát — `query` trả frame từ sáu nguồn store, `compute` chạy pandas trên frame
trong sandbox với AST chặn literal số, Board DSL v2 với ngữ pháp ép trực quan
(KPI strip bắt buộc, caption ≤ 280 ký tự không chữ số ngoài placeholder,
`data_table` chỉ ở appendix), server chọn widget theo hình dạng frame, layout
12 cột, 5 archetype, lint + auto-compose. Study thành template trên cùng
composer. `frame_from_evidence` là chỗ duy nhất model chép số, và chỉ nhận số
có mặt trong text trang đã fetch cùng Turn.

S1 định nghĩa lại theo đó; gate là golden `signal_desk` 50 câu do người ngoài
team viết, sáu grader bất biến 100% + pass ≥ 90%. Phase 08 (prompt) blockedBy
C2 phase 05 vì đổi kích thước context C2 đang đo. Bronze là phase 10
conditional trên 9 câu go/no-go.

## Next steps

User xác nhận ba quyết định (S1 định nghĩa lại · data trước · caption do model
template) và trả bốn câu hỏi mở trong plan.md. Rồi `/ak:plan validate` hoặc
red-team trước khi cook phase 01 (amendment). Phase 03 bước 0 phải kiểm pandas
có sẵn trước khi viết một dòng sandbox.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

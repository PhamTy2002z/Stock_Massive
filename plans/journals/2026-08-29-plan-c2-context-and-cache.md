---
title: Plan C2 context and cache
date: 2026-08-29
summary: Chốt plan năm phase dựa trên context replay và measurement cache tự động đã kiểm chứng.
---

# Plan C2 context and cache

## What happened

Đọc roadmap, code path context/prompt/Golden và các report C1/C5. Tạo plan `plans/260829-2141-c2-context-and-cache` gồm năm phase: baseline replay, deterministic prune, stable domain prefix, cache measurement và graduation gate.

## Decision

Giữ `llm_prompt_cache_control_enabled=False`. Measurement ngày 2026-08-23 cho thấy route đã cache prefix tự động, còn explicit `cache_control=True` không tạo uplift. C2 vì vậy đo cache theo aggregate và lấy giảm constructed token ít nhất 20% từ prune deterministic, không coi cached read là token đã loại bỏ.

Full tool result vẫn ở Tool Call Trace; model chỉ đọc projection dedup/collapsed handle. Domain body chuyển ngay sau core nhưng giữ nguyên trigger và sticky lifetime của C5.

## Next steps

Validate plan ở design gate, sau đó cook tuần tự năm phase. Phase 1 phải tạo replay corpus từ trace Golden thật; không dùng fixture giả nếu trace đã hết retention. C2 chỉ được đổi sang Current khi replay, C1 behavior gates và aggregate automatic cache đều đạt.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

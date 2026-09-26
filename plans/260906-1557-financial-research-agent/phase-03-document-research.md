---
phase: 3
title: "Tìm và đọc tài liệu/BCTC"
status: pending
priority: P1
effort: "10–15 engineer-days"
dependencies: [2]
---

# Phase 3: Tìm và đọc tài liệu/BCTC

Context: [Plan](./plan.md) · [Decision register](./decisions-and-dependencies.md) · [Validation](./validation-strategy.md)

## Overview

Đưa HTML/PDF/XLSX/DOCX từ URL hoặc upload vào production evidence flow. Ưu tiên báo cáo gốc, bảng nhiều kỳ và thuyết minh, gồm tài liệu scan.

## Requirements

- Reuse parser hiện có; parser unit tests không đủ chứng minh runtime integration.
- Có page/cell/section locator, extraction confidence, partial/truncated state và bản gốc có quyền truy cập.
- MIME sniffing, byte/page/uncompressed-size/CPU/time quotas; private attachments owner-scoped.
- OCR fallback nằm trong phạm vi, nhưng engine được chọn bằng corpus; không gửi tài liệu riêng tới cloud chưa được chấp thuận.

## Architecture

`web_search → fetch_url → bounded download → MIME router → parse_document → page/table observations → evidence store → research context`.
Upload đi qua AttachmentStore/owner check rồi cùng extraction pipeline. Không raw PDF decode UTF-8 như text.

## Related Code Files

| Action | Files |
|---|---|
| Modify download seam | `apps/api/src/agent/tools/web.py`, `apps/api/src/core/web_lane.py` |
| Modify parser/evidence | `apps/api/src/agent/evidence/documents.py`, `pipeline.py`, `contracts.py` |
| Modify upload flow | `apps/api/src/agent/attachments.py`, `router.py`, `schemas.py`, `messages.py` |
| Modify UI/proxy consumer | `apps/web/src/components/shell/composer.tsx`, `attachment-chip.tsx`, `apps/web/src/lib/alpha-desk/api.ts` |
| Tests | `test_agent_document_evidence.py`, `test_agent_attachments.py`, `test_agent_turn_attachments.py`, `test_agent_attachment_injection.py`, web `attachments.test.tsx` |
| Create only if needed | Bounded OCR adapter next to documents.py; parser worker helper, not new service |

## Implementation Steps

1. Collect representative issuer filings: text PDF, scan, mixed pages, XLSX, DOCX; annual long reports, quarterly statements and notes. Ground-truth table cells and publication metadata.
2. Trace URL and upload end to end. Current ALLOWED_TYPES lacks document types, router resolves non-images as UTF-8; update both backend and browser accept/proxy limits together.
3. Route on validated media type plus file signature, preserve final public URL/security checks on redirects; reject encrypted/unsupported documents with typed reason.
4. Reuse parse_document and extend table/section extraction only where corpus fails. Preserve original label, column period, unit and row identity; merged cells and multi-page headers need explicit handling.
5. Introduce bounded process execution for hostile/expensive parsing and OCR. Terminate worker on timeout/cancel; cap decompression and pages; no network from parser unless separately entitled OCR service.
6. Read documents selectively by relevant pages/sections while retaining full locator and a way to retrieve remaining sections through approved fetch semantics. Never mark truncated read as entire filing reviewed.
7. Probe OCR candidates on exact-number/cell alignment and Vietnamese labels, latency and deployment constraints. Low confidence material numbers require corroboration or remain unverified.
8. Wire extracted evidence into Turn before research context is composed; prompt receives relevant excerpts/refs, not every byte or thousands of rows.
9. Cache public evidence only with rights; private document storage and excerpts scoped to owner. Define raw/extracted retention and deletion/replay behavior.
10. Add production-path E2E fixture: user provides filing URL/upload → research sees page evidence → claim links correct cell/page → refresh works.

## Test Matrix

| Case | Gate |
|---|---|
| PDF URL + correct MIME / misleading suffix | Actual bytes choose parser |
| PDF scan/mixed | OCR route or explicit unreadable gap, never silent empty success |
| XLSX zip bomb/external formula link | Bounded rejection, no network/formula execution |
| Wrong owner attachment ID | Same not-found behavior, no metadata leak |
| Long annual report exceeds quota | Partial disclosed; no fabricated reviewed-all assertion |
| Cancellation during parser | Worker ends, Turn settles, no orphan process |
| Multi-period table | Labels/unit/period travel with extracted numbers |

## Success Criteria

- [ ] URL and upload production integration pass for supported document types.
- [ ] Every material extracted number has correct locator/unit/period or remains unverified.
- [ ] 0 cross-owner/private-cache leakage; 0 parser egress or surviving cancelled workers in adversarial suite.
- [ ] OCR and extraction accuracy measured against frozen cells; threshold locked W1, no averaged score hiding failed mandatory type.

## Validation

Run listed parser/attachment suites, web attachment tests, type-check and affected golden document family. Real filing canary separate from fixture replay. Quote unchanged limits or approve revised limits with measured payload sizes.

## Risk Assessment

Scanning/table extraction cannot resolve every report → include readable partial answer and exact missing pages; do not invent data. Provider CDN blocks fetch → use alternate official locator or user upload; browser-computer-use is not automatically opened.

## Rollback / handoff

Feature flag document intake; keep old image/text handling. Preserve accepted uploads under retention policy even if parser is disabled. Handoff source corpus hashes, extraction metrics, supported types and OCR privacy decision.

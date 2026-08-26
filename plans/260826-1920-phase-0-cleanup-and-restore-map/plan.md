---
title: "Phase 0 cleanup and restore map"
description: "Dọn hết nợ Phase 0 rip-out để nền sạch, đồng thời ghi bản đồ restore cho brief Text.txt (không triển khai restore trong plan này)."
status: in-progress (phase 1-5 done)
priority: P1
effort: "1-2 ngày"
tags: [refactor, cleanup, rip-out]
created: 2026-08-26
---

# Phase 0 cleanup and restore map

## Overview

Phase 0 rip-out (commit `9611982`, `f4821d9`, `93c23cf`) đã xoá market surfaces
xuống lane chat, test 940/406 pass. Nhưng nợ còn: 8 dir `stocks/*` rỗng, 12
signal module mồ côi, ~30 setting cấu hình chỉ dùng cho code đã rip, bảng DB
chưa drop, backup chưa verify restore, tag chưa push. Plan này dọn hết những
thứ đó **và** ghi bản đồ khôi phục sau này (theo brief `docs/Text.txt` trên
`origin/develop`) — bản đồ chỉ để tham chiếu, không thi công trong plan này.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Xoá 100% code chết còn sót sau Phase 0 (thư mục rỗng, module mồ côi, setting stale) | P1 |
| 2 | Verify backup restore rồi drop bảng DB đã rip qua alembic revision mới | P1 |
| 3 | Dọn tag/branch: xoá stub Phase 1 chưa dùng, push `v-with-market-surfaces`, refresh CLAUDE.md | P1 |
| 4 | Ghi bản đồ restore cho brief Text.txt: intraday spine, financial store, indices/sector, news+universe | P2 |

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Kick-off & inventory verification](./phase-01-start.md) | Done |
| 2 | [Rip empty stocks directories and dead dnse shell](./phase-02-rip-empty-stocks-directories-and-dead-dnse-shell.md) | N/A (dirs untracked) |
| 3 | [Rip 12 orphan signal modules and reconcile registry](./phase-03-rip-12-orphan-signal-modules-and-reconcile-registry.md) | Done (only nulls; 11 kept live) |
| 4 | [Prune stale config settings and validator](./phase-04-prune-stale-config-settings-and-validator.md) | Done |
| 5 | [Verify backup and drop rip-out tables via alembic](./phase-05-verify-backup-and-drop-rip-out-tables-via-alembic.md) | Done |
| 6 | [Tidy Phase 1 stub, push archive tag, refresh CLAUDE.md](./phase-06-tidy-phase-1-stub-push-archive-tag-refresh-claudemd.md) | Pending |
| 7 | [Restore map: vnstock Diamond intraday spine](./phase-07-restore-map-vnstock-diamond-intraday-spine.md) | Reference only |
| 8 | [Restore map: financial statement store market-wide](./phase-08-restore-map-financial-statement-store-market-wide.md) | Reference only |
| 9 | [Restore map: market indices and sector membership](./phase-09-restore-map-market-indices-and-sector-membership.md) | Reference only |
| 10 | [Restore map: news RSS and universe expansion](./phase-10-restore-map-news-rss-and-universe-expansion.md) | Reference only |

Phases 1-6 thực thi trong plan này. Phases 7-10 là bản đồ cho lần restore
tiếp theo — chỉ ghi phạm vi, không thi công.

## Success Criteria

- [ ] `find src/stocks -type d -empty` trả về rỗng (không còn shell dir)
- [ ] `grep -rl "from src.stocks.signals.\(corporate_actions\|cross_sectional\|foreign_flow\|foreign_share_flow\|fundamentals\|indicators\|market_behavior\|moments\|nulls\|reference\|risk\|volatility\)" src/ tests/` trả về rỗng, và các file đó không còn trên disk (hoặc được ghi rõ vì sao giữ)
- [ ] `grep -inE "dnse|fiinquant|alpha_desk|realtime_ingestion|realtime_queue|realtime_worker|backfill|warmup" src/core/config.py` trả về rỗng
- [ ] `pg_restore --list` xác nhận `pre-rip-out-260825.sql.gz` decompress + parse được
- [ ] Alembic revision mới drop các bảng liên quan (thư danh ở Phase 5); `alembic upgrade head` xanh trên DB dev
- [ ] `plans/260826-1909-phase-1-domain-pack/` bị xoá; `src/agent/domain/pack.py` bị xoá
- [ ] `git tag v-with-market-surfaces` đã push lên `origin`
- [ ] CLAUDE.md cập nhật: "Không còn tồn tại" liệt kê chính xác những gì đã rip lần này; roadmap nói rõ Phase 1 domain pack **bị hoãn** để chờ quyết định brief Text.txt
- [ ] `apps/api` `make test` 940 pass / 0 fail
- [ ] `apps/web` `pnpm type-check && pnpm lint && pnpm test && pnpm build` xanh
- [ ] Docker: `docker compose up -d api` + healthcheck xanh với `LLM_CAPABILITY_PROBE_ENABLED=false`

## Constraints

- Hard freeze vẫn giữ (ngoài `src/agent/*`) chỉ khi **thao tác là "xoá"** —
  plan này cắt sạch nợ, không thêm feature mới.
- Không đổi wire format, không đổi hành vi runtime lane chat.
- Alembic: chỉ **thêm** revision drop, không sửa migration cũ.
- Không push tag/branch nếu user chưa xác nhận (Phase 6 có gate hỏi).
- Không xoá backup dump — giữ đến khi bảng đã drop và verified.

## Non-goals

- Không build canvas / view registry / decision engine / opportunity score
- Không restore realtime spine, financial store, market indices, news feed
  (chỉ ghi bản đồ)
- Không mở rộng Universe (giữ 30 mã declared cho tới lần restore)
- Không đụng domain pack Phase 1 — stub bị xoá, sẽ mở lại sau

## Risk

| Risk | Xác suất | Impact | Mitigation |
|------|---------|--------|-----------|
| Signal module "mồ côi" thực ra có test ẩn hoặc import gián tiếp qua registry | Trung bình | Test đỏ | Phase 3 grep registry, chạy `make test -k signal` trước khi rm |
| Backup dump không restore được | Thấp | Không rollback được | Phase 5 verify decompress + `pg_restore --list` trước bất cứ drop nào |
| Alembic drop revision phá schema đang được ai đó dev song song | Thấp | Migration conflict | Chỉ chạy trên dev DB local; PR về develop sau khi user đã merge Phase 0 3 commit |
| CLAUDE.md drift so với thực tế repo | Trung bình | Session sau nhầm | Phase 6 grep lại "Không còn tồn tại" đối chiếu `git ls-files` |

## Rollback

- Từng phase 1-6 là một commit riêng. `git revert` từng commit.
- Bảng đã drop (Phase 5): restore từ `backups/pre-rip-out-260825.sql.gz`.
- Tag đã push (Phase 6): `git push --delete origin v-with-market-surfaces`
  chỉ khi chưa ai clone.

<!-- slug: phase-0-cleanup-and-restore-map -->

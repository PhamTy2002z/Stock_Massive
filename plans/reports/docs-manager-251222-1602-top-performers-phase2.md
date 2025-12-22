# Documentation Update: Top Performers Phase 2

**Date**: 2025-12-22
**Subagent**: docs-manager
**Feature**: Top Performers Weekly Collection Job

---

## Summary

Updated project documentation to reflect Phase 2 completion of top-performers-feature. Added weekly scheduled job details across multiple documentation files.

---

## Changes Made

### 1. `docs/codebase-summary.md`

**Section: Tech Stack - Backend**
- Updated APScheduler description: `APScheduler 4.0 (daily intraday collection, weekly top performers)`

**Section: Directory Structure**
- Added `models.py` note: `SQLAlchemy models (IntradayBar, TopPerformer)`
- Updated `jobs.py` description: `Scheduled jobs (intraday collection/cleanup, top performers weekly)`
- Added new file: `top_performers_collector.py # Weekly top performers collection by net profit`

**Section: Key Features - Current (Completed)**
- Added: `Top Performers: Weekly scheduled job (Sun 02:00 ICT) collecting quarterly net profit rankings for HOSE+HNX symbols`

**Section: Important Files - Backend**
- Updated `models.py`: `SQLAlchemy models (IntradayBar, TopPerformer)`
- Added: `top_performers_collector.py: Weekly top performers collection with adaptive rate limiting`
- Updated `jobs.py`: `Scheduled jobs (intraday collection/cleanup, top performers weekly)`

---

### 2. `docs/system-architecture.md`

**Section: Directory Structure**
- Updated `models.py` note: `SQLAlchemy models (IntradayBar, TopPerformer)`
- Updated `jobs.py` description: `Scheduled jobs (intraday collection/cleanup, top performers weekly)`
- Added new file: `top_performers_collector.py # Weekly top performers collection by net_profit`

**Section: Database Schema**
- Added new TopPerformer table schema with:
  - Fields: id, symbol, company_name, exchange, year, quarter, net_profit, revenue, rank, collected_at
  - Indexes: symbol, rank, collected_at
  - Unique constraint: (symbol, year, quarter)

**Section: Scheduled Jobs**
- Added new row:
  - **Job**: Top Performers Collection
  - **Schedule**: 02:00 ICT Sunday
  - **Description**: Fetch quarterly income statements for HOSE+HNX symbols (~700-800), rank by net_profit, store top performers with adaptive rate limiting

---

## Implementation Details Documented

### Weekly Job Configuration
- **Schedule**: Every Sunday at 02:00 ICT
- **Scope**: ~700-800 symbols (HOSE + HNX)
- **Data Source**: Quarterly income statements via vnstock
- **Ranking**: By net_profit descending
- **Storage**: top_performers table with year/quarter/symbol uniqueness
- **Rate Limiting**: Adaptive delays to handle API limits

### Database Model
- TopPerformer table added to schema documentation
- Includes financial metrics (net_profit, revenue)
- Indexed for efficient querying by symbol, rank, and collection time

---

## Files Not Modified

- `project-roadmap.md` - Already had "Top Performers Batch Job" marked as completed Dec 22, 2025
- `code-standards.md` - No changes needed (implementation follows existing patterns)
- `deployment-guide.md` - No deployment changes required
- `design-guidelines.md` - No UI components in Phase 2

---

## Verification

All documentation updates are:
- ✅ Consistent with actual implementation
- ✅ Following existing doc structure/format
- ✅ Using correct terminology (net_profit, ICT timezone)
- ✅ Minimal and focused on Phase 2 changes only

---

## Unresolved Questions

None. Documentation is complete and synchronized with Phase 2 implementation.

# Phase 03: Volume Analysis API

**Parent Plan:** [plan.md](plan.md)
**Dependencies:** [Phase 01](phase-01-database-setup.md), [Phase 02](phase-02-data-collection-service.md)
**Docs:** [Brainstorm Report](../reports/brainstorm-251218-intraday-volume-database-design.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2024-12-18 |
| Priority | High |
| Implementation Status | Completed |
| Review Status | Approved with Recommendations |

**Description:** Create API endpoint to analyze intraday volume patterns, identifying peak trading periods within the 9:00-15:00 trading session.

## Key Insights

- Trading session: 9:00-15:00 Vietnam time (6 hours)
- 5-min bars = 72 bars per day
- Analysis groups by hour + 5-min bucket to find patterns
- Return avg/total volume per time slot across N days

## Requirements

1. Create volume analysis endpoint
2. Query database for N-day historical bars
3. Aggregate by time-of-day (hour + minute bucket)
4. Return ranked peak volume periods

## Architecture

```
GET /api/v1/stocks/{symbol}/volume-analysis
├── Query params: days (default 10), top_n (default 10)
├── Query database for bars in date range
├── Group by hour + minute_bucket
├── Calculate avg_volume, total_volume, sample_count
└── Return sorted by avg_volume DESC
```

## Related Code Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/src/stocks/router.py` | Update | Add volume-analysis endpoint |
| `apps/api/src/stocks/schemas.py` | Update | Add VolumeAnalysis response schema |
| `apps/api/src/stocks/intraday_collector.py` | Update | Add analysis query method |

## Implementation Steps

### Step 1: Add response schemas

```python
# Add to apps/api/src/stocks/schemas.py
class VolumeTimePeriod(BaseModel):
    hour: int
    minute_bucket: int  # 0, 5, 10, 15, ...
    time_label: str     # "09:00", "09:05", etc.
    avg_volume: float
    total_volume: int
    sample_count: int

class VolumeAnalysisResponse(BaseModel):
    symbol: str
    days_analyzed: int
    trading_session: str  # "09:00-15:00"
    peak_periods: list[VolumeTimePeriod]
    generated_at: datetime
```

### Step 2: Add analysis method to IntradayCollector

```python
# Add to apps/api/src/stocks/intraday_collector.py
from sqlalchemy import select, func, extract
from datetime import datetime, timedelta

class IntradayCollector:
    # ... existing methods ...

    async def analyze_volume(
        self,
        symbol: str,
        days: int = 10,
        top_n: int = 10
    ) -> dict:
        """Analyze volume patterns for a symbol over N days."""
        cutoff_date = datetime.now() - timedelta(days=days)

        # Query with time-of-day grouping
        stmt = (
            select(
                extract('hour', StockIntradayBar.bar_time).label('hour'),
                (extract('minute', StockIntradayBar.bar_time) / 5 * 5).label('minute_bucket'),
                func.avg(StockIntradayBar.volume).label('avg_volume'),
                func.sum(StockIntradayBar.volume).label('total_volume'),
                func.count().label('sample_count'),
            )
            .where(StockIntradayBar.symbol == symbol.upper())
            .where(StockIntradayBar.bar_time >= cutoff_date)
            .where(extract('hour', StockIntradayBar.bar_time) >= 9)
            .where(extract('hour', StockIntradayBar.bar_time) < 15)
            .group_by('hour', 'minute_bucket')
            .order_by(func.avg(StockIntradayBar.volume).desc())
            .limit(top_n)
        )

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        periods = []
        for row in rows:
            hour = int(row.hour)
            minute = int(row.minute_bucket)
            periods.append({
                'hour': hour,
                'minute_bucket': minute,
                'time_label': f"{hour:02d}:{minute:02d}",
                'avg_volume': float(row.avg_volume),
                'total_volume': int(row.total_volume),
                'sample_count': int(row.sample_count),
            })

        return {
            'symbol': symbol.upper(),
            'days_analyzed': days,
            'trading_session': '09:00-15:00',
            'peak_periods': periods,
            'generated_at': datetime.now(),
        }
```

### Step 3: Add API endpoint

```python
# Add to apps/api/src/stocks/router.py
from src.stocks.schemas import VolumeAnalysisResponse

@router.get("/{symbol}/volume-analysis", response_model=VolumeAnalysisResponse)
async def get_volume_analysis(
    symbol: str,
    days: int = Query(default=10, ge=1, le=30),
    top_n: int = Query(default=10, ge=1, le=72),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze intraday volume patterns for a stock.

    Returns peak volume periods within trading session (09:00-15:00).
    """
    collector = IntradayCollector(db)
    result = await collector.analyze_volume(symbol, days, top_n)

    if not result['peak_periods']:
        raise HTTPException(
            status_code=404,
            detail=f"No intraday data found for {symbol} in last {days} days"
        )

    return result
```

## Todo List

- [x] Add VolumeTimePeriod and VolumeAnalysisResponse schemas
- [x] Add analyze_volume method to IntradayCollector
- [x] Add volume-analysis endpoint to router
- [x] Test with sample data
- [x] Verify response format

## Success Criteria

- [x] Endpoint returns 200 with valid data
- [x] Peak periods sorted by avg_volume DESC
- [x] Time labels formatted correctly (HH:MM)
- [x] 404 returned when no data exists

## Review Summary

**Review Date:** 2025-12-19
**Review Report:** [code-reviewer-251219-volume-analysis-api.md](../reports/code-reviewer-251219-volume-analysis-api.md)
**Status:** Approved with Recommendations

**Key Findings:**
- Quality Score: 8.5/10
- Test Coverage: 96.4% (80/83 tests passing)
- Security: No critical issues
- Performance: Minor optimization opportunities

**High Priority Actions:**
1. Fix test database connection leaks
2. Add query timeout handling

**Medium Priority:**
1. Add covering index for volume analysis queries
2. Consider parallelizing bulk collection operations

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| No data for symbol | Medium | Low | Return 404 with clear message |
| Slow query | Low | Medium | Index on symbol + bar_time exists |
| Timezone issues | Medium | Medium | Store in UTC, convert on display |

## Security Considerations

- Validate symbol format (existing validation)
- Limit days parameter (max 30)
- Limit top_n parameter (max 72)

## Next Steps

After completion, proceed to [Phase 04: Scheduled Jobs](phase-04-scheduled-jobs.md)

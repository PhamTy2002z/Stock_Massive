---
phase: 2
title: Backend - Foreign Snapshot Endpoint
status: pending
estimated_files: 3
---

# Phase 2: Backend - Foreign Snapshot Endpoint

## Objective

Create a new API endpoint that uses `company.trading_stats()` to provide foreign investor snapshot data.

## Tasks

### 2.1 Add Response Schema

**File:** `apps/api/src/stocks/trading/schemas.py`

```python
class ForeignSnapshotResponse(BaseModel):
    """Snapshot of foreign investor activity from trading_stats."""
    symbol: str
    foreign_volume: int  # Today's foreign trading volume
    foreign_room: int  # Remaining foreign ownership room
    ownership_ratio: float | None  # Current foreign ownership percentage (0-1)
    total_volume: int  # Today's total trading volume
    avg_volume_2w: float | None  # 2-week average volume
    foreign_pct_of_volume: float | None  # Foreign volume as % of total
    last_updated: str  # ISO timestamp
```

### 2.2 Add Service Method

**File:** `apps/api/src/stocks/trading/service.py`

```python
def get_foreign_snapshot(self, symbol: str) -> ForeignSnapshotResponse:
    """Get current foreign investor snapshot from trading_stats."""
    symbol = validate_symbol(symbol)
    try:
        stock = Vnstock().stock(symbol=symbol, source=self.source)
        df = stock.company.trading_stats()

        if df is None or df.empty:
            return ForeignSnapshotResponse(
                symbol=symbol,
                foreign_volume=0,
                foreign_room=0,
                ownership_ratio=None,
                total_volume=0,
                avg_volume_2w=None,
                foreign_pct_of_volume=None,
                last_updated=datetime.now().isoformat()
            )

        # Extract first row (should be single row)
        row = df.iloc[0] if len(df) > 0 else {}

        foreign_vol = int(row.get('foreign_volume', 0) or 0)
        total_vol = int(row.get('total_volume', 0) or 0)

        # Calculate foreign % of total volume
        foreign_pct = (foreign_vol / total_vol * 100) if total_vol > 0 else None

        return ForeignSnapshotResponse(
            symbol=symbol,
            foreign_volume=foreign_vol,
            foreign_room=int(row.get('foreign_room', 0) or 0),
            ownership_ratio=safe_float(row.get('current_holding_ratio')),
            total_volume=total_vol,
            avg_volume_2w=safe_float(row.get('avg_match_volume_2w')),
            foreign_pct_of_volume=foreign_pct,
            last_updated=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error fetching foreign snapshot for {symbol}: {e}")
        raise StockServiceError(f"Failed to fetch foreign snapshot: {e}")
```

### 2.3 Add Router Endpoint

**File:** `apps/api/src/stocks/trading/router.py`

```python
# Add new cache instance
foreign_snapshot_cache = TradingHoursCache(
    key_prefix="stock:foreign_snapshot:",
    ttl_trading=120,  # 2 min during trading (snapshot data)
    ttl_off_hours=1800,  # 30 min off-hours
)

@router.get(
    "/{symbol}/foreign-snapshot",
    response_model=ForeignSnapshotResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_foreign_snapshot(symbol: str) -> ForeignSnapshotResponse:
    """Get current foreign investor snapshot.

    Returns foreign volume, ownership ratio, and remaining room.
    This is a snapshot (not historical data).
    """
    cache_key = symbol
    cached = foreign_snapshot_cache.get(cache_key)
    if cached:
        return ForeignSnapshotResponse(**cached)

    try:
        service = get_trading_service()
        result = service.get_foreign_snapshot(symbol)
        foreign_snapshot_cache.set(cache_key, result.model_dump())
        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

## Verification

```bash
# Test endpoint
curl http://localhost:8000/api/v1/stocks/VNM/foreign-snapshot

# Expected response
{
  "symbol": "VNM",
  "foreign_volume": 820196,
  "foreign_room": 2089955445,
  "ownership_ratio": 0.506,
  "total_volume": 2449027,
  "avg_volume_2w": 3538353.0,
  "foreign_pct_of_volume": 33.5,
  "last_updated": "2024-12-27T14:30:00"
}
```

## Dependencies

- vnstock `Vnstock().stock().company.trading_stats()` method
- Existing cache infrastructure

## Notes

- Returns current snapshot, not historical data
- `ownership_ratio` is 0-1 scale (multiply by 100 for percentage)
- `foreign_room` is number of shares foreigners can still buy

# Scheduled Jobs Pattern Research

**Date:** 2025-12-22
**Focus:** Existing scheduled jobs implementation for top-performers feature

---

## 1. Existing Job Patterns

### Job Structure (`apps/api/src/stocks/jobs.py`)
- **Async jobs**: `collect_intraday_data_job()`, `cleanup_old_data_job()`
- **Sync jobs**: `collect_daily_ohlcv_job()` (wrapped in async via `run_in_executor`)
- **Return format**: Dict with `success`, `failed`, `total_*` counts

### Job Types
1. **Intraday collection** (L24-45): Fetches configured symbols, uses `IntradayCollector`
2. **Cleanup** (L48-68): Deletes old data based on retention days
3. **Daily OHLCV** (L71-176): Batch processes all symbols with rate limit handling

---

## 2. Scheduler Configuration

### Setup (`apps/api/src/core/scheduler.py`)
- **Library**: APScheduler `AsyncScheduler`
- **Trigger**: `CronTrigger` with timezone `Asia/Ho_Chi_Minh`
- **Job registration**: `scheduler.add_schedule(func, trigger, id=unique_id)`

### Existing Schedule
```python
# Intraday collection: 15:30 ICT (configurable)
CronTrigger(hour=settings.intraday_collect_hour, minute=settings.intraday_collect_minute)

# Cleanup: 16:00 ICT (fixed)
CronTrigger(hour=16, minute=0)

# Daily OHLCV: 20:00 ICT (configurable)
CronTrigger(hour=settings.daily_ohlcv_hour, minute=settings.daily_ohlcv_minute)
```

### Async Wrapper Pattern (L15-18)
```python
async def collect_daily_ohlcv_job_async():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, collect_daily_ohlcv_job)
```

---

## 3. Data Storage Approach

### Database Models (`apps/api/src/stocks/models.py`)
- **StockDailyOHLCV**: Daily bars (symbol, trade_date unique constraint)
- **StockIntradayBar**: 5-min bars (symbol, bar_time unique constraint)

### Storage Patterns

**Async Upsert** (`intraday_collector.py` L113-142):
```python
stmt = insert(StockIntradayBar).values(bars)
stmt = stmt.on_conflict_do_update(
    index_elements=["symbol", "bar_time"],
    set_={fields}
)
result = await self.db.execute(stmt)
```

**Sync Upsert** (`jobs.py` L179-254):
```python
conn.execute(text("""
    INSERT INTO stock_daily_ohlcv (...) VALUES (...)
    ON CONFLICT (symbol, trade_date) DO UPDATE SET ...
"""), {...})
```

### Key Features
- **Idempotent**: Upsert prevents duplicates
- **Batch processing**: Collect → combine → save
- **Error isolation**: Individual symbol failures don't stop batch

---

## 4. Adding New Scheduled Job

### Steps
1. **Create job function** in `apps/api/src/stocks/jobs.py`:
   ```python
   async def new_job_name() -> dict:
       # Return dict with success/failed/count metrics
   ```

2. **Register in scheduler** (`apps/api/src/core/scheduler.py`):
   ```python
   await scheduler.add_schedule(
       new_job_name,
       CronTrigger(hour=X, minute=Y, timezone="Asia/Ho_Chi_Minh"),
       id="unique-job-id"
   )
   ```

3. **Add config settings** (if needed):
   - Schedule time: `NEW_JOB_HOUR`, `NEW_JOB_MINUTE`
   - Enable flag: `NEW_JOB_ENABLED`

4. **Database model** (if storing new data):
   - Create model in `models.py`
   - Add unique constraint for idempotent upsert
   - Add indexes for queries

---

## 5. Rate Limit Handling Patterns

### VNStock Wrapper (`jobs.py` L11-16)
- **Safe wrapper**: `get_stock_history()` with `max_retries`, `base_delay`
- **Exception**: `VnstockRateLimitError` caught separately
- **Adaptive delay**: `get_adaptive_delay(base_delay)` increases with failures

### Rate Limit Strategy (L136-161)
```python
try:
    df = get_stock_history(..., max_retries=2, base_delay=3.0)
except VnstockRateLimitError:
    rate_limit_count += 1
    logger.warning(f"Rate limited for {symbol}, skipping")

# Adaptive per-symbol delay
delay = get_adaptive_delay(base_delay)
time.sleep(delay)

# Extra batch pause if rate limits detected
if rate_limit_count > 0:
    batch_pause = min(30, rate_limit_count * 5)
    time.sleep(batch_pause)
```

### Best Practices
- **Track rate limits**: Separate counter from errors
- **Skip vs retry**: Skip rate-limited symbols, log warning
- **Backoff**: Increase delays when limits detected
- **Batch coordination**: Pause between batches if limits hit

---

## Recommendations for Top-Performers Job

1. **Follow async pattern**: Use `async def` + `IntradayCollector` style
2. **Schedule**: Morning (e.g., 08:00 ICT before market open) or evening (e.g., 18:00 after close)
3. **Data model**: New table `stock_top_performers` with date + symbol unique constraint
4. **Calculation**: Query `StockDailyOHLCV` for % change, volume metrics
5. **Rate limits**: No external API calls if using existing DB data

---

## Unresolved Questions
None

"""Router for market context endpoints (manual triggers)."""
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.core.database import get_sync_db
from src.stocks.market_context_service import MarketContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market-context", tags=["market-context"])


def get_db():
    """Dependency for sync database session."""
    with get_sync_db() as db:
        yield db


@router.post("/trigger-eod")
def trigger_eod_pipeline(
    target_date: date = Query(None, description="Target date (default: today)"),
    db: Session = Depends(get_db),
):
    """Manually trigger EOD pipeline for market context metrics.

    Use for backfilling historical data or re-running failed jobs.
    """
    try:
        service = MarketContextService(db)
        result = service.run_eod_pipeline(target_date)
        return {
            "status": "success",
            "message": f"EOD pipeline completed for {target_date or 'today'}",
            "result": result,
        }
    except Exception as e:
        logger.error(f"Manual EOD trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill")
def backfill_historical_data(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    db: Session = Depends(get_db),
):
    """Backfill historical market context data for date range.

    Skips weekends automatically. Use for initial data population.
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")

    try:
        service = MarketContextService(db)
        results = []
        current_date = start_date

        while current_date <= end_date:
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                try:
                    result = service.run_eod_pipeline(current_date)
                    results.append({
                        "date": str(current_date),
                        "status": result.get("status", "unknown"),
                    })
                except Exception as e:
                    results.append({
                        "date": str(current_date),
                        "status": "failed",
                        "error": str(e),
                    })

            current_date += timedelta(days=1)

        success_count = sum(1 for r in results if r["status"] == "success")
        return {
            "status": "completed",
            "message": f"Backfilled {success_count}/{len(results)} days from {start_date} to {end_date}",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

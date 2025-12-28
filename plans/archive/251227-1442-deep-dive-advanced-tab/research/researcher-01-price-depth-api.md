# Research: Vnstock `price_depth()` API - VCI Source

**Date**: 2024-12-27
**Researcher**: researcher-01
**Context**: Deep Dive Advanced Tab - Order Flow Sub-tab

---

## 1. API Usage

### Basic Usage
```python
from vnstock import Quote

quote = Quote(symbol='VCB', source='VCI')
df = quote.price_depth()  # Returns DataFrame
```

### Optional Parameters
- `show_log` (bool, default=False): Display debug logs

### Compatibility
- ✅ Hoạt động với VCI source
- ✅ Vnstock 3.2.2+ (March 2025): Fixed VCI API changes
- ✅ Vnstock 3.3.0+ (Nov 2025): Unified multi-source system

---

## 2. Data Structure (Expected)

### Typical Price Depth Output
Based on standard market data format, expect DataFrame with:

**Columns:**
- `bid_price_1`, `bid_price_2`, `bid_price_3` - Top 3 bid prices
- `bid_volume_1`, `bid_volume_2`, `bid_volume_3` - Volumes at each bid level
- `ask_price_1`, `ask_price_2`, `ask_price_3` - Top 3 ask prices
- `ask_volume_1`, `ask_volume_2`, `ask_volume_3` - Volumes at each ask level
- `timestamp` - Data timestamp

**Sample (hypothetical):**
```
bid_price_3  bid_vol_3  bid_price_2  bid_vol_2  bid_price_1  bid_vol_1  ask_price_1  ask_vol_1  ask_price_2  ask_vol_2  ask_price_3  ask_vol_3
92200        5000       92300        8500       92350        12000      92400        3200       92500        2100       92600        4500
```

**Note:** Cấu trúc chính xác cần verify bằng test thực tế với VCI.

---

## 3. Pydantic Schema Proposal

### Response Schema
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PriceLevel(BaseModel):
    """Single price level with volume"""
    price: float = Field(..., description="Price at this level")
    volume: int = Field(..., description="Volume available at this price")

class PriceDepthResponse(BaseModel):
    """Price depth response with 3 bid/ask levels"""
    symbol: str = Field(..., description="Stock symbol")

    # Bid levels (buy orders)
    bid_1: PriceLevel = Field(..., description="Best bid (highest buy price)")
    bid_2: Optional[PriceLevel] = Field(None, description="Second best bid")
    bid_3: Optional[PriceLevel] = Field(None, description="Third best bid")

    # Ask levels (sell orders)
    ask_1: PriceLevel = Field(..., description="Best ask (lowest sell price)")
    ask_2: Optional[PriceLevel] = Field(None, description="Second best ask")
    ask_3: Optional[PriceLevel] = Field(None, description="Third best ask")

    # Aggregates
    total_bid_volume: int = Field(..., description="Sum of all bid volumes")
    total_ask_volume: int = Field(..., description="Sum of all ask volumes")
    spread: float = Field(..., description="ask_1.price - bid_1.price")
    spread_percent: float = Field(..., description="(spread / bid_1.price) * 100")

    timestamp: datetime = Field(..., description="Data timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "VCB",
                "bid_1": {"price": 92350, "volume": 12000},
                "bid_2": {"price": 92300, "volume": 8500},
                "bid_3": {"price": 92200, "volume": 5000},
                "ask_1": {"price": 92400, "volume": 3200},
                "ask_2": {"price": 92500, "volume": 2100},
                "ask_3": {"price": 92600, "volume": 4500},
                "total_bid_volume": 25500,
                "total_ask_volume": 9800,
                "spread": 50,
                "spread_percent": 0.054,
                "timestamp": "2024-12-27T14:30:00"
            }
        }
```

---

## 4. Implementation Notes

### Service Layer
```python
# stocks/price/service.py
def get_price_depth(self, symbol: str) -> PriceDepthResponse:
    """Get real-time price depth (bid/ask levels)."""
    quote = Quote(symbol=symbol, source='VCI')
    df = quote.price_depth()

    # Parse DataFrame → Pydantic model
    # Handle missing levels gracefully
    # Calculate aggregates (total volumes, spread)

    return PriceDepthResponse(...)
```

### Caching
- **TTL Trading Hours**: 30s (real-time data)
- **TTL Off-Hours**: 5min
- **Rate Limit Tier**: Heavy (short cache)

---

## Unresolved Questions

1. **Data Structure**: Cần test thực tế với VCI để confirm column names chính xác
2. **Update Frequency**: VCI cập nhật price depth mỗi bao lâu? (1s, 5s, 10s?)
3. **Error Handling**: VCI trả về gì khi market closed hoặc stock suspended?
4. **Depth Levels**: VCI có support >3 levels không? (extend bid_4, bid_5...)

---

**Next Steps**: Test API với symbol thực (VCB, ACB) để verify data structure trước khi implement service.

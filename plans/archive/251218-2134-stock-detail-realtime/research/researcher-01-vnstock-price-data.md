# Vnstock Library Research: Real-time Stock Data

## Overview
Vnstock provides comprehensive Vietnamese stock market data via Python API. Primary classes: `Trading`, `Quote`, `Finance`, `Vnstock`.

---

## 1. Price Board Data (Real-time)

### API Method
```python
from vnstock import Trading
trading = Trading()
df = trading.price_board(symbols_list=['VCB'], flatten_columns=True, drop_levels=[0])
```

### Available Fields (61 columns total)
| UI Requirement | Vnstock Field | Type | Notes |
|----------------|---------------|------|-------|
| Match Price | `match_price` | int64 | Current trading price |
| Ceiling | `ceiling` | int64 | Upper price limit |
| Floor | `floor` | int64 | Lower price limit |
| Reference Price | `ref_price` | int64 | Opening reference |
| Highest | `highest` | int64 | Day's high |
| Lowest | `lowest` | int64 | Day's low |
| Accumulated Volume | `accumulated_volume` | int64 | Total traded volume |
| Accumulated Value | `accumulated_value` | float64 | Total traded value |

### Additional Useful Fields
- `organ_name`: Company name
- `exchange`: HSX/HNX/UPCOM
- `trading_status`: TRADING_ACTIVATED, etc.
- `avg_match_price`: Average match price
- `match_vol`: Last match volume
- `foreign_buy_volume`, `foreign_sell_volume`: Foreign trading
- `bid_1_price`, `bid_1_volume` ... `bid_3_*`: Bid levels
- `ask_1_price`, `ask_1_volume` ... `ask_3_*`: Ask levels

---

## 2. Company Overview

### API Methods
```python
from vnstock import Vnstock
stock = Vnstock().stock(symbol='VCB', source='VCI')
overview = stock.company.overview()
profile = stock.company.profile()
```

### Overview Fields
| UI Requirement | Vnstock Field | Type |
|----------------|---------------|------|
| Company Name | `short_name` | object |
| Industry | `industry` | object |
| Market Cap | (calculate from price * issue_share) | - |
| Issue Share | `issue_share` | float64 |
| Exchange | `exchange` | object |
| Foreign Percent | `foreign_percent` | float64 |
| Outstanding Share | `outstanding_share` | float64 |
| Employees | `no_employees` | int64 |
| Website | `website` | object |

### Profile Fields
- `company_name`: Full legal name
- `company_profile`: Description
- `history_dev`: Development history
- `business_strategies`: Strategy info

---

## 3. Financial Ratios

### API Methods
```python
from vnstock import Finance
finance = Finance(symbol='VCB', source='VCI')

# Historical ratios
df = finance.ratio(period='year', lang='en')

# Summary ratios (current)
stock = Vnstock().stock(symbol='VCB', source='VCI')
summary = stock.company.ratio_summary()
```

### Ratio Fields Mapping
| UI Requirement | Vnstock Field | Source |
|----------------|---------------|--------|
| EPS | `eps` or `eps_ttm` | ratio_summary |
| P/E | `pe` or `price_to_earning` | ratio_summary / ratio |
| P/B | `pb` or `price_to_book` | ratio_summary / ratio |
| Beta | `Beta` (Vietnamese col) | ratio (lang='vi') |
| Dividend Yield | `Tỷ suất cổ tức` | ratio (lang='vi') |
| ROE | `roe` | ratio_summary |
| ROA | `roa` | ratio_summary |
| BVPS | `bvps` | ratio_summary |

### Dividend History
```python
dividends = stock.company.dividends()
# Returns: exercise_date, cash_year, dividend_percentage, issue_method
```

---

## 4. Code Examples

### Complete Price Board Fetch
```python
from vnstock import Trading

trading = Trading()
df = trading.price_board(
    symbols_list=['VCB', 'ACB', 'TCB'],
    flatten_columns=True,
    drop_levels=[0]
)

# Extract key fields
for _, row in df.iterrows():
    print({
        'symbol': row['symbol'],
        'match_price': row['match_price'],
        'ceiling': row['ceiling'],
        'floor': row['floor'],
        'ref_price': row['ref_price'],
        'highest': row['highest'],
        'lowest': row['lowest'],
        'volume': row['accumulated_volume'],
        'value': row['accumulated_value'],
    })
```

### Company + Ratios Combined
```python
from vnstock import Vnstock

stock = Vnstock().stock(symbol='VCB', source='VCI')
overview = stock.company.overview()
ratios = stock.company.ratio_summary()

# Merge data
company_data = {
    'name': overview['short_name'].iloc[0],
    'industry': overview['industry'].iloc[0],
    'issue_share': overview['issue_share'].iloc[0],
    'eps': ratios['eps'].iloc[0],
    'pe': ratios['pe'].iloc[0],
    'pb': ratios['pb'].iloc[0],
    'roe': ratios['roe'].iloc[0],
}
```

---

## 5. Limitations & Notes

1. **Beta not in English**: Must use `lang='vi'` for Beta field
2. **Market Cap**: Not directly provided; calculate as `match_price * issue_share`
3. **Real-time Delay**: Price board has ~15s delay (not true real-time)
4. **Rate Limits**: No official docs, but recommend throttling requests
5. **Data Source**: VCI recommended for most complete data
6. **Dividend Yield**: Available in Vietnamese ratio output only

---

## 6. Existing Service Integration

Current `StockService` in `/apps/api/src/stocks/service.py` already implements:
- `get_price_board()` - needs field mapping update
- `get_company_overview()` - working
- `get_financial_ratios()` - working

### Recommended Updates
1. Update `_df_to_price_board()` to map all 61 fields
2. Add `match_price`, `highest`, `lowest` to `PriceBoardItem` schema
3. Add `ratio_summary()` call for current EPS/PE/Beta

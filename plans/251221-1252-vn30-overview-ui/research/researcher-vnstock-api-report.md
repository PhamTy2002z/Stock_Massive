# vnstock API Research Report - VN30 Data Retrieval

## Overview
vnstock is a Python library for accessing Vietnamese stock market data. This report focuses on retrieving VN30 index stocks with real-time prices and company information.

## 1. Installation & Setup

```python
# Install vnstock
pip install vnstock3

# Basic initialization
from vnstock import Vnstock, Listing, Trading, Company

# Initialize listing object (for stock lists)
listing = Listing(source='VCI')

# Initialize trading object (for price data)
trading = Trading(symbol='SYMBOL', source='VCI')

# Initialize company object (for company info)
company = Company(symbol='SYMBOL', source='VCI')
```

**Note**: VCI (Vietcap) is the default and recommended data source.

## 2. Get VN30 Stock List

### Method: symbols_by_group()
Returns list of stock symbols in VN30 index.

```python
from vnstock import Listing

listing = Listing(source='VCI')
vn30_symbols = listing.symbols_by_group('VN30')

# Output: pandas Series with stock symbols
# Example: ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', ...]
```

**Returns**: pandas Series containing VN30 stock symbols

## 3. Get Company Names

### Method: company.overview()
Retrieves company overview including name, industry, and basic info.

```python
from vnstock import Company

# For each symbol in VN30
company = Company(symbol='VCB', source='VCI')
overview = company.overview()

# Key fields:
# - short_name: Company short name (e.g., 'Vietcombank')
# - exchange: Trading exchange (HOSE, HNX)
# - industry: Industry sector
# - website: Company website
```

**Output Structure**:
```
Columns:
- exchange: str (HOSE/HNX)
- industry: str (industry name)
- company_type: str
- short_name: str (company name)
- website: str
- no_shareholders: int
- foreign_percent: float
- outstanding_share: float
- delta_in_week: float
- delta_in_month: float
- delta_in_year: float
```

### Alternative: All Symbols with Names
```python
from vnstock_data import Listing

listing = Listing(source='vnd')
all_stocks = listing.all_symbols()

# Returns DataFrame with:
# - symbol, type, exchange, listing_status, company_name, etc.
```

## 4. Get Current Price & Price Change

### Method A: price_board() - Real-time Price Data
Best for getting current prices for multiple stocks at once.

```python
from vnstock import Trading

trading = Trading()
symbols_list = ['VCB', 'ACB', 'TCB', 'BID']
price_data = trading.price_board(symbols_list=symbols_list)

# Key fields:
# - last_price: Current price
# - price_change: Absolute price change
# - price_change_pct: Percentage change
# - volume: Trading volume
# - value: Trading value
```

**Alternative with vnstock_data**:
```python
from vnstock_data import Trading

trading = Trading(symbol='VCB', source='vci')
price_board = trading.price_board(['VCB','ACB','TCB','BID'],
                                   flatten_columns=True,
                                   drop_levels=[0])
```

### Method B: company.overview() - Price Change Metrics
Includes price change percentages over different periods.

```python
company = Company(symbol='VCB', source='VCI')
overview = company.overview()

# Price change fields:
# - delta_in_week: float (weekly change %)
# - delta_in_month: float (monthly change %)
# - delta_in_year: float (yearly change %)
```

### Method C: intraday() - Real-time Intraday Data
For second-accurate real-time data during trading hours (9:00-15:00).

```python
from vnstock import Quote

quote = Quote(symbol='VCI', source='VCI')
intraday_data = quote.intraday()

# Returns DataFrame with:
# - time: timestamp
# - price: current price
# - volume: trade volume
# - match_type: Buy/Sell
# - id: transaction ID
```

## 5. Complete Implementation Example

```python
from vnstock import Listing, Trading, Company
import pandas as pd

# Step 1: Get VN30 symbols
listing = Listing(source='VCI')
vn30_symbols = listing.symbols_by_group('VN30')
symbols_list = vn30_symbols.tolist()

# Step 2: Get real-time prices for all VN30 stocks
trading = Trading()
price_data = trading.price_board(symbols_list=symbols_list)

# Step 3: Get company names and details
vn30_data = []
for symbol in symbols_list:
    try:
        company = Company(symbol=symbol, source='VCI')
        overview = company.overview()

        vn30_data.append({
            'symbol': symbol,
            'company_name': overview['short_name'].iloc[0],
            'industry': overview['industry'].iloc[0],
            'exchange': overview['exchange'].iloc[0]
        })
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")

# Step 4: Combine data
companies_df = pd.DataFrame(vn30_data)
final_data = companies_df.merge(price_data, on='symbol', how='left')

# Result: DataFrame with symbol, company_name, current_price, price_change_pct
```

## 6. Data Sources

vnstock supports multiple data sources:
- **VCI** (Vietcap): Default, most reliable
- **TCBS**: Alternative source
- **VND** (VNDirect): For comprehensive listing data
- **MSN**: For international data

## 7. Key Considerations

1. **Rate Limiting**: API calls may be rate-limited; implement delays for bulk requests
2. **Trading Hours**: Real-time data available 9:00-15:00 VN time
3. **Data Freshness**: price_board() provides most current data
4. **Error Handling**: Always wrap API calls in try-except blocks
5. **Source Selection**: VCI recommended for Vietnamese stocks

## 8. API Response Times

- `symbols_by_group()`: Fast (~1s)
- `price_board()`: Fast for batch (~2-3s for 30 stocks)
- `company.overview()`: Moderate (~1-2s per symbol)
- `intraday()`: Fast (~1s)

## Recommended Approach for VN30 Dashboard

1. Use `symbols_by_group('VN30')` to get current VN30 list
2. Use `price_board(symbols_list)` for batch price retrieval
3. Cache company names (they rarely change)
4. Refresh price data every 30-60 seconds during trading hours
5. Use `company.overview()` for detailed company info on-demand

## Unresolved Questions

1. Exact rate limits for VCI source not documented
2. Historical VN30 composition changes not covered
3. After-hours price data availability unclear

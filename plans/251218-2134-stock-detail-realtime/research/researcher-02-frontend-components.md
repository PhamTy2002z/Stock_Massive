# Frontend Stock Detail Components Analysis

**Date:** 2024-12-18
**Path:** `/apps/web/src/components/dashboard/`

---

## 1. Component Overview

| Component | Purpose | Lines |
|-----------|---------|-------|
| `StockTickerHeader` | Display symbol, company name, price, change | 65 |
| `StockDetailPanel` | Quick stats grid (volume, GTGD, market cap, industry) | 67 |
| `StockStatsTable` | Detailed 3-column stats table | 109 |
| `StockCompanyInfo` | Company info card with description | 72 |

All components are client-side (`"use client"`) and use `cn()` utility for className merging.

---

## 2. Props & Interfaces

### StockTickerHeader
```typescript
interface StockTickerHeaderProps {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  className?: string
}
```
**Real-time fields:** `price`, `change`, `changePercent`

### StockDetailPanel
```typescript
interface StockDetailPanelProps {
  volume: number        // shares
  tradingValue: number  // billion VND
  marketCap: number     // billion VND
  industry: string
  className?: string
}
```
**Real-time fields:** `volume`, `tradingValue`

### StockStatsTable
```typescript
interface StockStatsTableProps {
  // Intraday prices
  openPrice: number
  highPrice: number
  lowPrice: number
  tradingVolume: number
  // 52-week data
  marketCap: number
  high52Week: number
  low52Week: number
  avgVolume52Week: number
  // Fundamentals
  eps: number | null
  pe: number | null
  beta: number | null
  dividendYield: number | null
  className?: string
}
```
**Real-time fields:** `openPrice`, `highPrice`, `lowPrice`, `tradingVolume`
**Static fields:** 52-week data, fundamentals (EPS, P/E, Beta, Dividend)

### StockCompanyInfo
```typescript
interface StockCompanyInfoProps {
  symbol: string
  industry: string
  marketCap: number
  outstandingShares: number
  exchange: string | null
  vn30Rank: number | null
  description: string
  className?: string
}
```
**Static fields:** All (company metadata)

---

## 3. Data Fields Summary

### Real-Time Data (needs live updates)
| Field | Component(s) | Update Frequency |
|-------|--------------|------------------|
| `price` | TickerHeader | High |
| `change` | TickerHeader | High |
| `changePercent` | TickerHeader | High |
| `volume` | DetailPanel, StatsTable | Medium |
| `tradingValue` | DetailPanel | Medium |
| `openPrice` | StatsTable | Once/day |
| `highPrice` | StatsTable | Medium |
| `lowPrice` | StatsTable | Medium |

### Static/Semi-Static Data
| Field | Component(s) | Update Frequency |
|-------|--------------|------------------|
| `symbol`, `companyName` | TickerHeader | Static |
| `industry` | DetailPanel, CompanyInfo | Static |
| `marketCap` | All 3 | Daily |
| `outstandingShares` | CompanyInfo | Quarterly |
| `exchange`, `vn30Rank` | CompanyInfo | Static |
| `description` | CompanyInfo | Static |
| `high52Week`, `low52Week` | StatsTable | Daily |
| `avgVolume52Week` | StatsTable | Daily |
| `eps`, `pe`, `beta`, `dividendYield` | StatsTable | Quarterly |

---

## 4. Current State: All Props Are Dynamic

- **No hardcoded values** in components - all data passed via props
- Components are pure presentational (no data fetching)
- Vietnamese locale formatting (`vi-VN`) applied consistently
- Null handling for optional fundamentals (`eps`, `pe`, `beta`, `dividendYield`)

---

## 5. Integration Points for Real-Time Data

### Recommended Architecture
```
Parent Container (data fetching)
├── useQuery/SWR for initial data
├── WebSocket/SSE for real-time updates
└── Pass props to child components
    ├── StockTickerHeader (price, change)
    ├── StockDetailPanel (volume, tradingValue)
    ├── StockStatsTable (intraday prices)
    └── StockCompanyInfo (static data)
```

### Key Integration Points
1. **Price Updates:** `StockTickerHeader` - needs `price`, `change`, `changePercent`
2. **Volume Updates:** `StockDetailPanel` + `StockStatsTable` - needs `volume`, `tradingValue`
3. **Intraday Range:** `StockStatsTable` - needs `highPrice`, `lowPrice`

### Suggested Data Structure for Real-Time
```typescript
interface RealTimeStockData {
  symbol: string
  price: number
  change: number
  changePercent: number
  volume: number
  tradingValue: number
  highPrice: number
  lowPrice: number
  timestamp: number
}
```

---

## 6. Observations

- Components well-structured for real-time integration (stateless, prop-driven)
- Formatting utilities duplicated across components (could be centralized)
- No loading/error states built into components
- No animation for price changes (consider adding flash effect)

---

## 7. Unresolved Questions

1. Where is the parent container that composes these components?
2. What API endpoint currently provides stock detail data?
3. Is there existing WebSocket infrastructure in the codebase?

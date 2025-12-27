# Phase 2: Frontend Hooks & API Client

## Context
Frontend cần 6 hooks để fetch data từ backend endpoints. Sử dụng TanStack Query v5.

## Overview
Create hooks và API client functions cho Order Flow, Technical, Money Flow data.

## Requirements
- R1: 6 hooks với TanStack Query pattern
- R2: API client functions trong lib/api.ts
- R3: Query keys trong lib/query-keys.ts
- R4: TypeScript types cho responses
- R5: Loading/error states handling

## Architecture
```
apps/web/src/
├── hooks/
│   ├── use-order-stats.ts      # Order Flow
│   ├── use-price-depth.ts      # Order Flow
│   ├── use-ratio-summary.ts    # Technical
│   ├── use-trading-stats.ts    # Technical
│   ├── use-foreign-trading.ts  # Money Flow
│   └── use-prop-trading.ts     # Money Flow
├── lib/
│   ├── api.ts                  # ADD: API functions
│   └── query-keys.ts           # ADD: Query keys
└── types/
    └── advanced.ts             # Response types
```

## Related Files
| File | Action | Description |
|------|--------|-------------|
| `apps/web/src/hooks/use-order-stats.ts` | CREATE | Order stats hook |
| `apps/web/src/hooks/use-price-depth.ts` | CREATE | Price depth hook |
| `apps/web/src/hooks/use-ratio-summary.ts` | CREATE | Ratio summary hook |
| `apps/web/src/hooks/use-trading-stats.ts` | CREATE | Trading stats hook |
| `apps/web/src/hooks/use-foreign-trading.ts` | CREATE | Foreign trading hook |
| `apps/web/src/hooks/use-prop-trading.ts` | CREATE | Prop trading hook |
| `apps/web/src/lib/api.ts` | EDIT | Add API functions |
| `apps/web/src/lib/query-keys.ts` | EDIT | Add query keys |

## Implementation Steps

### Step 2.1: Add TypeScript Types
```typescript
// types/advanced.ts
export interface PriceLevel {
  price: number
  volume: number
}

export interface PriceDepthResponse {
  symbol: string
  bid_1: PriceLevel
  bid_2?: PriceLevel
  bid_3?: PriceLevel
  ask_1: PriceLevel
  ask_2?: PriceLevel
  ask_3?: PriceLevel
  total_bid_volume: number
  total_ask_volume: number
  spread: number
  spread_percent: number
  timestamp: string
}

export interface RatioSummaryResponse {
  pe?: number
  pb?: number
  ps?: number
  roe?: number
  roa?: number
  roic?: number
  current_ratio?: number
  debt_to_equity?: number
}

export interface TradingStatsResponse {
  total_volume?: number
  avg_volume?: number
  total_value?: number
  avg_value?: number
  high_price?: number
  low_price?: number
}

export interface OrderStatsItem {
  date: string
  buy_order_count: number
  sell_order_count: number
  buy_order_volume: number
  sell_order_volume: number
}

export interface ForeignTradingItem {
  date: string
  buy_volume: number
  sell_volume: number
  net_volume: number
  buy_value: number
  sell_value: number
  net_value: number
}

export interface PropTradingItem {
  date: string
  buy_volume: number
  sell_volume: number
  net_volume: number
}
```

### Step 2.2: Add API Client Functions
```typescript
// lib/api.ts - ADD
export async function fetchOrderStats(symbol: string, days = 30) {
  const end = new Date().toISOString().split('T')[0]
  const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  const res = await fetch(`${API_BASE}/stocks/${symbol}/order-stats?start=${start}&end=${end}`)
  return res.json()
}

export async function fetchPriceDepth(symbol: string) {
  const res = await fetch(`${API_BASE}/stocks/${symbol}/price-depth`)
  return res.json()
}

export async function fetchRatioSummary(symbol: string) {
  const res = await fetch(`${API_BASE}/stocks/${symbol}/ratio-summary`)
  return res.json()
}

export async function fetchTradingStats(symbol: string) {
  const res = await fetch(`${API_BASE}/stocks/${symbol}/trading-stats`)
  return res.json()
}

export async function fetchForeignTrading(symbol: string, days = 30) {
  const end = new Date().toISOString().split('T')[0]
  const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  const res = await fetch(`${API_BASE}/stocks/${symbol}/foreign-trading?start=${start}&end=${end}`)
  return res.json()
}

export async function fetchPropTrading(symbol: string, days = 30) {
  const end = new Date().toISOString().split('T')[0]
  const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  const res = await fetch(`${API_BASE}/stocks/${symbol}/prop-trading?start=${start}&end=${end}`)
  return res.json()
}
```

### Step 2.3: Add Query Keys
```typescript
// lib/query-keys.ts - ADD
export const advancedKeys = {
  orderStats: (symbol: string) => ['order-stats', symbol] as const,
  priceDepth: (symbol: string) => ['price-depth', symbol] as const,
  ratioSummary: (symbol: string) => ['ratio-summary', symbol] as const,
  tradingStats: (symbol: string) => ['trading-stats', symbol] as const,
  foreignTrading: (symbol: string) => ['foreign-trading', symbol] as const,
  propTrading: (symbol: string) => ['prop-trading', symbol] as const,
}
```

### Step 2.4: Create Hooks
```typescript
// hooks/use-order-stats.ts
export function useOrderStats(symbol: string, days = 30) {
  return useQuery({
    queryKey: advancedKeys.orderStats(symbol),
    queryFn: () => fetchOrderStats(symbol, days),
    staleTime: 5 * 60 * 1000, // 5min
    enabled: !!symbol,
  })
}
```

```typescript
// hooks/use-price-depth.ts
export function usePriceDepth(symbol: string) {
  return useQuery({
    queryKey: advancedKeys.priceDepth(symbol),
    queryFn: () => fetchPriceDepth(symbol),
    staleTime: 30 * 1000, // 30s - real-time
    refetchInterval: 30 * 1000,
    enabled: !!symbol,
  })
}
```

```typescript
// hooks/use-ratio-summary.ts
export function useRatioSummary(symbol: string) {
  return useQuery({
    queryKey: advancedKeys.ratioSummary(symbol),
    queryFn: () => fetchRatioSummary(symbol),
    staleTime: 60 * 60 * 1000, // 1h
    enabled: !!symbol,
  })
}
```

```typescript
// hooks/use-trading-stats.ts
export function useTradingStats(symbol: string) {
  return useQuery({
    queryKey: advancedKeys.tradingStats(symbol),
    queryFn: () => fetchTradingStats(symbol),
    staleTime: 15 * 60 * 1000, // 15min
    enabled: !!symbol,
  })
}
```

```typescript
// hooks/use-foreign-trading.ts
export function useForeignTrading(symbol: string, days = 30) {
  return useQuery({
    queryKey: advancedKeys.foreignTrading(symbol),
    queryFn: () => fetchForeignTrading(symbol, days),
    staleTime: 15 * 60 * 1000, // 15min
    enabled: !!symbol,
  })
}
```

```typescript
// hooks/use-prop-trading.ts
export function usePropTrading(symbol: string, days = 30) {
  return useQuery({
    queryKey: advancedKeys.propTrading(symbol),
    queryFn: () => fetchPropTrading(symbol, days),
    staleTime: 15 * 60 * 1000, // 15min
    enabled: !!symbol,
  })
}
```

## Todo List
- [ ] Create types/advanced.ts with response types
- [ ] Add 6 API functions to lib/api.ts
- [ ] Add query keys to lib/query-keys.ts
- [ ] Create use-order-stats.ts hook
- [ ] Create use-price-depth.ts hook
- [ ] Create use-ratio-summary.ts hook
- [ ] Create use-trading-stats.ts hook
- [ ] Create use-foreign-trading.ts hook
- [ ] Create use-prop-trading.ts hook

## Success Criteria
- [ ] All hooks return data, isLoading, error states
- [ ] TypeScript types match backend responses
- [ ] staleTime configured appropriately per endpoint
- [ ] Hooks disabled when symbol is empty
- [ ] price-depth has refetchInterval for real-time

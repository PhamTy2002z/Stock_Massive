# Audit Report: Advanced Section Calculation Review

**Date:** 2025-12-28
**Scope:** Financial Statements > Advanced Tab
**Reference:** stock-data-analysis skill

---

## Executive Summary

Reviewed all 4 subtabs (Technical, Order Flow, Money Flow, Sector). Most calculations are correct. Found 3 minor threshold discrepancies that should be adjusted for better alignment with industry standards.

---

## 1. Technical Subtab

### 1.1 RatioSummaryCard (`ratio-summary-card.tsx:42-93`)

| Metric | Current | Skill Reference | Status |
|--------|---------|-----------------|--------|
| P/E | max: 20 | <20 | ✅ OK |
| P/B | max: 3 | <3 implied | ✅ OK |
| ROE | min: 15% | >10% | ⚠️ Conservative |
| ROA | min: 5% | >5% | ✅ OK |
| ROIC | min: 10% | - | ✅ OK |
| Current Ratio | 1-3 | 1.5-3 | ⚠️ Min should be 1.5 |
| D/E | max: 2 | <1 (good) | ⚠️ Max too high |

### 1.2 TradingStatsCard
- Display-only component, no calculations
- Formatting functions correct

---

## 2. Order Flow Subtab

### 2.1 Calculations (`order-flow-charts.tsx:271-276`)

```javascript
netVolume = buy_volume - sell_volume          // ✅
buyOrderPct = (buy_orders / totalOrders) * 100 // ✅
buyVolumePct = (buy_volume / totalVolume) * 100 // ✅
```

**Status:** All correct

---

## 3. Money Flow Subtab

### 3.1 Foreign Flow Calculations (`foreign-flow-charts.tsx:162-170`)

```javascript
foreignPct = foreign_pct_of_volume              // ✅ From API
volumeVsAvg = (total_volume / avg_volume_2w) * 100 // ✅
```

**Status:** All correct

---

## 4. Sector Subtab

### 4.1 Premium/Discount Formula (`service.py:957-971`)

```python
premium = ((value - median) / abs(median)) * 100
```

**Status:** ✅ Correct

### 4.2 5-Tier Classification (`premium-badge.tsx:18-57`)

| Tier | Range | Color |
|------|-------|-------|
| Vượt trội | >30% | Emerald |
| Tốt | +10% → +30% | Green |
| Trung bình | ±10% | Gray |
| Kém | -10% → -30% | Red |
| Rất kém | <-30% | Bright Red |

**Status:** ✅ Good classification system

---

## 5. Backend Health Scoring

### 5.1 Benchmarks (`health_scoring.py:10-21`)

| Metric | Good | Excellent | Skill | Match |
|--------|------|-----------|-------|-------|
| ROE | 15% | 20% | >10% | ⚠️ |
| ROA | 8% | 12% | >5% | ⚠️ |
| D/E | 1.0 | 0.5 | <1 | ✅ |
| Current | 1.5 | 2.0 | 1.5-3 | ✅ |
| P/E | 15 | 10 | <20 | ✅ |

### 5.2 Dimension Weights (`health_scoring.py:24-30`)

| Dimension | Weight |
|-----------|--------|
| Profitability | 30% |
| Liquidity | 20% |
| Leverage | 20% |
| Efficiency | 15% |
| Valuation | 15% |

**Status:** Reasonable distribution

### 5.3 F-Score (Simplified)

Current implementation uses 6 criteria (vs original 9):

1. ✅ Positive ROA
2. ✅ Positive CFO
3. ✅ ROA improving
4. ✅ Accrual quality (CFO > Net Income)
5. ✅ Leverage decreasing
6. ✅ Liquidity improving

**Missing criteria:**
- Shares outstanding (dilution check)
- Gross margin improvement
- Asset turnover improvement

**Note:** Simplified version acceptable for quick assessment. Max score is 6/6 (not 9).

---

## 6. FCF Analysis

### 6.1 Formulas (`service.py:720-799`)

```python
FCF = CFO + CapEx          # CapEx negative ✅
FCF_Margin = FCF / Revenue  # ✅
FCF_Yield = FCF / MarketCap # ✅
CCC = DSO + DIO - DPO      # ✅
```

**Status:** All correct

---

## Issues to Fix

### Priority: Low (Threshold Adjustments)

1. **Current Ratio min** (`ratio-summary-card.tsx:85`)
   - Current: `min: 1`
   - Recommended: `min: 1.5`

2. **D/E max** (`ratio-summary-card.tsx:91`)
   - Current: `max: 2`
   - Recommended: `max: 1.5`

3. **ROE min** (`ratio-summary-card.tsx:66`)
   - Current: `min: 15`
   - Optional: `min: 10` (less conservative)

---

## Conclusion

| Component | Formula Accuracy | Notes |
|-----------|------------------|-------|
| Technical Subtab | ✅ Correct | Threshold tweaks optional |
| Order Flow | ✅ Correct | - |
| Money Flow | ✅ Correct | - |
| Sector Comparison | ✅ Correct | - |
| Health Scoring | ✅ Correct | F-Score simplified (6/9) |
| FCF Analysis | ✅ Correct | - |

**Overall Status:** ✅ Production Ready

Minor threshold adjustments are cosmetic/preferential and do not affect data accuracy.

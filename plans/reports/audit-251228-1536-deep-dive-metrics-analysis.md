# Audit Report: Deep Dive Tab - Financial Metrics Analysis

**Date:** 2025-12-28
**Auditor:** Claude Code with stock-data-analysis skill
**Scope:** Deep Dive tab (`/analytics/deep-dive`) - Financial metrics calculations & display

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| Health Score Calculation | ✅ CHUẨN | Đúng công thức, 5 dimensions weighted |
| F-Score Implementation | ⚠️ PARTIAL | 6/9 criteria (simplified version) |
| Ratio Display | ✅ CHUẨN | Thresholds phù hợp VN market |
| Trend Charts | ✅ CHUẨN | ROE/ROA có benchmark reference line |
| Risk Metrics | ❌ THIẾU | Chưa có VaR, Sharpe, Beta, Drawdown |
| Peer Comparison | ✅ CHUẨN | Có sector median & premium/discount |

**Overall Grade: 78/100** - Solid fundamental analysis, missing risk metrics

---

## 1. Health Score Analysis (Backend: `health_scoring.py`)

### 1.1 Dimension Weights
```python
DIMENSION_WEIGHTS = {
    "profitability": 0.30,  # ✅ Đúng - cao nhất
    "liquidity": 0.20,      # ✅ Hợp lý
    "leverage": 0.20,       # ✅ Hợp lý
    "efficiency": 0.15,     # ✅ Hợp lý
    "valuation": 0.15,      # ✅ Hợp lý
}
# Total = 1.0 ✅
```

### 1.2 Benchmark Thresholds (Vietnam Market Adjusted)

| Ratio | Code "good" | Code "excellent" | Skill Target | Status |
|-------|-------------|------------------|--------------|--------|
| ROE | 15% | 20% | >10% | ✅ Stricter (tốt) |
| ROA | 8% | 12% | N/A | ✅ |
| Net Margin | 10% | 15% | >10% | ✅ Match |
| Current Ratio | 1.5 | 2.0 | 1.5-3 | ✅ Match |
| D/E | 1.0 | 0.5 | <1 | ✅ Match |
| P/E | 15 | 10 | <20 | ✅ Stricter |
| P/B | 2.0 | 1.5 | N/A | ✅ |

**Kết luận:** Thresholds được điều chỉnh phù hợp thị trường VN, thậm chí còn strict hơn skill guidelines.

### 1.3 Normalize Score Algorithm

```python
# Code thực tế:
if value >= excellent: return 100
elif value >= good: return 70 + 30*(value-good)/(excellent-good)
else: return max(0, 70*value/good)

# Skill guidelines:
scores['pe'] = max(0, 100 * (1 - pe / 50))
scores['roe'] = min(100, roe * 5)
```

**Nhận xét:** Code implementation dùng linear interpolation giữa good/excellent thay vì formula đơn giản của skill. Cách tiếp cận của code **tốt hơn** vì:
- Có gradient mượt hơn
- Phân biệt rõ good vs excellent performance
- Xử lý edge cases tốt hơn

---

## 2. Piotroski F-Score Analysis

### 2.1 Implementation (6/9 criteria)

| # | Criterion | Implemented | Code Status |
|---|-----------|-------------|-------------|
| 1 | Positive ROA | ✅ | `positive_roa` |
| 2 | Positive CFO | ✅ | `positive_cfo` |
| 3 | ROA Improving | ✅ | `roa_improving` |
| 4 | Accrual Quality (CFO > Net Income) | ✅ | `accrual_quality` |
| 5 | Leverage Decreasing | ✅ | `leverage_decreasing` |
| 6 | Liquidity Improving | ✅ | `liquidity_improving` |
| 7 | No Share Dilution | ❌ | Chưa implement |
| 8 | Gross Margin Improving | ❌ | Chưa implement |
| 9 | Asset Turnover Improving | ❌ | Chưa implement |

**UI Bug:** `f-score-indicator.tsx:34` hiển thị `/9` nhưng chỉ tính 6 criteria:
```tsx
{score}/9 ({text})  // Nên đổi thành /6
```

### 2.2 Scoring Logic
```python
# F-Score rating
>= 7: "Mạnh"      # ⚠️ Không thể đạt 7+ với 6 criteria
>= 4: "Trung bình"
< 4: "Yếu"
```

**Issue:** Rating thresholds không phù hợp với 6 criteria max:
- Suggest: >=5 Mạnh, >=3 Trung bình, <3 Yếu

---

## 3. Ratio Summary Card Analysis

### 3.1 Displayed Ratios (8 metrics)

| Ratio | Threshold Good | Skill Target | Match |
|-------|----------------|--------------|-------|
| P/E | max: 20 | <20 | ✅ |
| P/B | max: 3 | N/A | ✅ |
| P/S | No threshold | N/A | OK |
| ROE | min: 15% | >10% | ✅ Stricter |
| ROA | min: 5% | N/A | ✅ |
| ROIC | min: 10% | N/A | ✅ |
| Current Ratio | 1-3 | 1.5-3 | ⚠️ Min nên là 1.5 |
| D/E | max: 2 | <1 | ⚠️ Nên strict hơn |

### 3.2 Color Coding Logic
```tsx
// Màu hiện tại
value < min || value > max → text-red-600
otherwise → text-green-600

// ✅ Đúng approach
```

---

## 4. Trend Charts Analysis

### 4.1 Revenue/Profit Chart
- **Data:** revenue, gross_profit, net_profit
- **Chart Type:** ComposedChart (Bar + Line)
- **Format:** Billions (T/B/M)
- **✅ Đúng pattern** theo skill visualization guidelines

### 4.2 ROE/ROA Chart
```tsx
<ReferenceLine y={15} label="Benchmark 15%" />
```
- **✅ Có benchmark line** - Skill yêu cầu "Compare dimensions"
- ROE benchmark 15% phù hợp với BENCHMARKS["roe"]["good"]

### 4.3 Cash Flow Chart
- **Data:** CFO, CFI, CFF
- **Chart Type:** BarChart với ReferenceLine y=0
- **✅ Đúng pattern** - hiển thị 3 dòng tiền cơ bản

---

## 5. Missing Risk Metrics (GAP Analysis)

Theo `stock-data-analysis` skill, cần có:

| Metric | Description | Status | Priority |
|--------|-------------|--------|----------|
| VaR (95%) | Value at Risk | ❌ THIẾU | HIGH |
| Sharpe Ratio | Risk-adjusted return | ❌ THIẾU | HIGH |
| Beta | Market correlation | ❌ THIẾU | HIGH |
| Alpha | Excess return | ❌ THIẾU | MEDIUM |
| Max Drawdown | Peak-to-trough decline | ❌ THIẾU | MEDIUM |
| Volatility | Price volatility | ❌ THIẾU | HIGH |

**Impact:** Không thể đánh giá đầy đủ risk/return profile của cổ phiếu.

---

## 6. Recommendations

### High Priority
1. **Fix F-Score display:** Đổi `/9` → `/6` trong `f-score-indicator.tsx:34`
2. **Fix F-Score thresholds:** Điều chỉnh rating để phù hợp 6 criteria max
3. **Add Risk Metrics section:** Implement VaR, Sharpe, Beta, Volatility

### Medium Priority
4. **Current Ratio threshold:** Đổi min từ 1 → 1.5 trong `ratio-summary-card.tsx:85`
5. **D/E threshold:** Đổi max từ 2 → 1.5 (stricter) trong `ratio-summary-card.tsx:91`
6. **Complete F-Score:** Thêm 3 criteria còn thiếu

### Low Priority
7. **Add historical comparison:** Track trend của các metrics qua thời gian
8. **Sector benchmark overlay:** Thêm sector average vào trend charts

---

## 7. Files Reviewed

| File | Lines | Status |
|------|-------|--------|
| `apps/api/src/stocks/financial/health_scoring.py` | 230 | ✅ |
| `apps/api/src/stocks/financial/service.py` | 995 | ✅ |
| `apps/web/src/components/dashboard/financial-health/health-score-card.tsx` | 135 | ✅ |
| `apps/web/src/components/dashboard/financial-health/score-breakdown.tsx` | 52 | ✅ |
| `apps/web/src/components/dashboard/financial-health/f-score-indicator.tsx` | 68 | ⚠️ Bug |
| `apps/web/src/components/dashboard/financial-health/health-radar-chart.tsx` | 70 | ✅ |
| `apps/web/src/components/dashboard/advanced-tab/widgets/ratio-summary-card.tsx` | 146 | ⚠️ Adjust |
| `apps/web/src/components/dashboard/financial-trends/trend-charts-card.tsx` | 113 | ✅ |
| `apps/web/src/components/dashboard/financial-trends/revenue-profit-chart.tsx` | 105 | ✅ |
| `apps/web/src/components/dashboard/financial-trends/roe-roa-chart.tsx` | 76 | ✅ |
| `apps/web/src/components/dashboard/financial-trends/cash-flow-chart.tsx` | 79 | ✅ |

---

## 8. Unresolved Questions

1. **F-Score criteria:** Có nên implement đủ 9 criteria hay giữ simplified 6?
2. **Risk metrics data source:** vnstock có API cho historical returns để tính VaR/Sharpe/Beta không?
3. **Benchmark:** Dùng VN-INDEX hay VN30 làm market benchmark cho Beta calculation?

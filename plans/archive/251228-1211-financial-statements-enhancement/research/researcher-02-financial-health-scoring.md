# Financial Health Scoring Research

## 1. DuPont Analysis

### 3-Factor Model (Traditional)
**Formula:**
```
ROE = Net Profit Margin × Asset Turnover × Equity Multiplier
    = (Net Income/Sales) × (Sales/Total Assets) × (Total Assets/Equity)
```

**Components:**
- **Net Profit Margin**: Operational efficiency measure
- **Asset Turnover**: Asset utilization efficiency
- **Equity Multiplier**: Financial leverage indicator

**Implementation:**
```python
def dupont_3factor(net_income, sales, total_assets, equity):
    npm = net_income / sales
    asset_turnover = sales / total_assets
    equity_multiplier = total_assets / equity
    return npm * asset_turnover * equity_multiplier
```

### 5-Factor Model (Extended)
**Formula:**
```
ROE = Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Equity Multiplier
    = (NI/EBT) × (EBT/EBIT) × (EBIT/Revenue) × (Revenue/Assets) × (Assets/Equity)
```

**Components:**
1. **Tax Burden** (NI/EBT): Tax impact
2. **Interest Burden** (EBT/EBIT): Interest expense impact
3. **EBIT Margin** (EBIT/Revenue): Operating profitability
4. **Asset Turnover** (Revenue/Assets): Asset efficiency
5. **Equity Multiplier** (Assets/Equity): Leverage

**Use Case:** 5-factor provides deeper insight into ROE drivers vs 3-factor

## 2. Altman Z-Score

### Formula (Public Manufacturing)
```
Z = 1.2×X₁ + 1.4×X₂ + 3.3×X₃ + 0.6×X₄ + 1.0×X₅

Where:
X₁ = Working Capital / Total Assets
X₂ = Retained Earnings / Total Assets
X₃ = EBIT / Total Assets
X₄ = Market Value of Equity / Total Liabilities
X₅ = Sales / Total Assets
```

### Interpretation Thresholds
| Z-Score | Zone | Risk Level |
|---------|------|------------|
| > 2.99 | Safe | Low bankruptcy risk |
| 1.81 - 2.99 | Grey | Moderate risk |
| < 1.81 | Distress | High bankruptcy risk (2yr) |

### Implementation Notes
- Developed by Edward Altman (1968, NYU)
- 80-90% accuracy for 2-year bankruptcy prediction
- Variations exist for private/non-manufacturing firms
- For Vietnam: use emerging market Z-Score variant if available

```python
def altman_z_score(wc, re, ebit, mv_equity, sales, total_assets, total_liabilities):
    x1 = wc / total_assets
    x2 = re / total_assets
    x3 = ebit / total_assets
    x4 = mv_equity / total_liabilities
    x5 = sales / total_assets
    return 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
```

## 3. Piotroski F-Score

### 9 Binary Criteria (0 or 1 point each)

**Profitability (4 pts):**
1. ROA > 0 (positive net income)
2. Operating Cash Flow > 0
3. ROA increase vs prior year
4. Accrual quality: CFO > Net Income

**Leverage/Liquidity (3 pts):**
5. Long-term debt ratio decreased vs prior year
6. Current ratio increased vs prior year
7. No new shares issued

**Operating Efficiency (2 pts):**
8. Gross margin increased vs prior year
9. Asset turnover increased vs prior year

### Scoring Interpretation
- **8-9 points**: Strong financial position
- **5-7 points**: Moderate/Average
- **0-2 points**: Weak financial position

### Implementation
```python
def piotroski_fscore(metrics_current, metrics_prior):
    score = 0
    # Profitability
    score += 1 if metrics_current['roa'] > 0 else 0
    score += 1 if metrics_current['cfo'] > 0 else 0
    score += 1 if metrics_current['roa'] > metrics_prior['roa'] else 0
    score += 1 if metrics_current['cfo'] > metrics_current['net_income'] else 0
    # Leverage/Liquidity
    score += 1 if metrics_current['ltd_ratio'] < metrics_prior['ltd_ratio'] else 0
    score += 1 if metrics_current['current_ratio'] > metrics_prior['current_ratio'] else 0
    score += 1 if metrics_current['shares'] <= metrics_prior['shares'] else 0
    # Efficiency
    score += 1 if metrics_current['gross_margin'] > metrics_prior['gross_margin'] else 0
    score += 1 if metrics_current['asset_turnover'] > metrics_prior['asset_turnover'] else 0
    return score
```

## 4. Vietnam Market Considerations

### Typical Benchmarks (VN-Index)
**Note:** Vietnam-specific data limited in search results. General emerging market benchmarks:

- **ROE**: 12-18% (good), >18% (excellent)
- **ROA**: 5-10% (good), >10% (excellent)
- **P/E Ratio**: 10-15 (reasonable for EM)
- **Debt/Equity**: <1.0 preferred, <0.5 conservative
- **Current Ratio**: >1.5 healthy, >2.0 strong

### Market-Specific Adjustments
- State-owned enterprises (SOEs): Higher leverage acceptable
- Banking sector: Different ratios (CAR, NPL, etc.)
- Real estate: Higher debt typical, focus on interest coverage
- Manufacturing: Focus on asset turnover, inventory days

### Data Sources for VN Benchmarks
- SSI Securities (ssi.com.vn)
- VNDirect (vndirect.com.vn)
- HOSE (hsx.vn)
- State Securities Commission (ssc.gov.vn)

## 5. Normalization Approaches (0-100 Scale)

### Method 1: Min-Max Normalization
**Formula:**
```
Score = ((Value - Min) / (Max - Min)) × 100
```

**Pros:** Simple, preserves relative relationships
**Cons:** Sensitive to outliers

### Method 2: Percentile Ranking
**Formula:**
```
Percentile = (Count of values below / Total count) × 100
```

**Pros:** Robust to outliers, intuitive
**Cons:** Loses magnitude info

### Method 3: Winsorized Min-Max (Recommended)
**Process:**
1. Cap extreme values at 5th/95th percentile
2. Apply min-max on winsorized data
3. Scale to 0-100

**Pros:** Balances outlier robustness with magnitude preservation
**Cons:** More complex

### Composite Score Example
```python
def composite_health_score(z_score, f_score, roe_dupont):
    # Normalize each component
    z_norm = normalize_z_score(z_score)  # Map Z thresholds to 0-100
    f_norm = (f_score / 9) * 100  # F-Score already 0-9
    roe_norm = percentile_rank(roe_dupont, industry_roe_data)

    # Weighted average
    weights = {'z': 0.4, 'f': 0.3, 'roe': 0.3}
    return z_norm*weights['z'] + f_norm*weights['f'] + roe_norm*weights['roe']
```

### Z-Score Normalization Mapping
```python
def normalize_z_score(z):
    if z >= 2.99: return 100
    elif z <= 1.81: return 0
    else: return ((z - 1.81) / (2.99 - 1.81)) * 100  # Linear interpolation
```

## Implementation Recommendations

1. **Start with Piotroski F-Score**: Simplest, binary criteria, works well for VN market
2. **Add Altman Z-Score**: For bankruptcy risk screening
3. **Use 3-Factor DuPont**: Sufficient for most analysis; 5-factor for deep dives
4. **Normalization**: Percentile ranking for cross-stock comparison, winsorized min-max for absolute scoring
5. **Composite Score**: Weight based on investment strategy (growth vs value vs safety)

## Unresolved Questions

1. Vietnam-specific Z-Score coefficients (if available from local research)?
2. Industry-specific F-Score thresholds for VN market?
3. Historical VN-Index sector benchmarks for ratio normalization?
4. Optimal weights for composite score in VN context?

## Sources

Research conducted via web search; specific Vietnam market data requires local brokerage reports (SSI, VNDirect) or academic studies on Vietnamese equity markets.

# Volume Anomaly Detection Algorithms Research

## 1. Statistical Methods for Detecting Unusual Volume

### Z-Score Method
- Formula: `Z = (V - μ) / σ` where V=current volume, μ=mean, σ=standard deviation
- Lookback period: typically 20-50 days for daily data
- Threshold: |Z| > 2 (unusual), |Z| > 3 (highly unusual)
- Pros: Statistically robust, accounts for volatility
- Cons: Assumes normal distribution (volume often skewed)

### Percentile Method
- Compare current volume to historical percentile rank
- Thresholds: >90th percentile (elevated), >95th (high), >99th (extreme)
- Pros: Distribution-agnostic, intuitive interpretation
- Cons: Requires sufficient historical data

### Moving Average Comparison (Volume Ratio)
- Formula: `Ratio = Current Volume / SMA(Volume, N)`
- Common periods: 10, 20, 50-day SMA
- Industry standard thresholds:
  - 1.5x average: Moderately elevated
  - 2x average: Significantly elevated
  - 3x average: Volume spike/anomaly
- Pros: Simple, widely used, easy to interpret
- Cons: Lag in detection, sensitive to period selection

### Exponential Moving Average (EMA) Variant
- More weight to recent volume, faster response
- Formula: `Ratio = Current Volume / EMA(Volume, N)`
- Better for detecting emerging trends

## 2. Time-of-Day Volume Patterns

### U-Shaped Intraday Pattern
- **Opening hour**: Highest volume (30-40% of daily)
- **Midday**: Lowest volume ("lunch lull")
- **Closing hour**: Second peak (20-30% of daily)
- Pattern consistent across most markets globally

### Normalization Approaches
- Divide intraday volume by typical volume for that time slot
- Use time-weighted average volume (TWAP) as baseline
- Seasonal adjustment for day-of-week effects

### Key Considerations
- Monday/Friday patterns differ from mid-week
- Options expiration days show elevated volume
- Earnings announcements cause predictable spikes

## 3. Threshold Selection - Industry Standards

### Volume Multiplier Thresholds
| Multiplier | Classification | Use Case |
|------------|----------------|----------|
| 1.5x | Elevated | Early warning |
| 2x | High | Standard alert threshold |
| 3x | Very High | Significant event likely |
| 5x+ | Extreme | Major news/event |

### Adaptive Thresholds
- Adjust based on stock's historical volatility
- Low-volume stocks: use higher multipliers (3-4x)
- High-volume stocks: lower multipliers sufficient (1.5-2x)
- Consider market cap: small caps more volatile

### Best Practices
- Use rolling windows (20-day common for short-term)
- Exclude outliers from baseline calculation
- Combine with price action for confirmation

## 4. Spike Detection vs Sustained High Volume

### Spike Detection (Single-Bar Anomaly)
- **Definition**: Single period with volume >> average
- **Detection**: Z-score > 3 OR ratio > 3x average
- **Significance**: Often news-driven, may indicate:
  - Earnings surprise
  - M&A announcement
  - Analyst upgrade/downgrade

### Sustained High Volume Detection
- **Definition**: Multiple consecutive periods above threshold
- **Methods**:
  - Count bars where volume > 1.5x average in N periods
  - Rolling sum of volume vs rolling average
  - Cumulative volume deviation from expected
- **Thresholds**: 3+ consecutive bars above 1.5x average
- **Significance**: Indicates:
  - Accumulation/distribution phase
  - Trend confirmation
  - Institutional activity

### Hybrid Approach (Recommended)
```
Spike Alert: Single bar > 3x 20-day SMA
Sustained Alert: 3+ bars > 1.5x 20-day SMA within 5-bar window
Combined Score: Weight both for overall anomaly score
```

## 5. Implementation Recommendations

### Algorithm Priority
1. **Primary**: Volume Ratio (Current / 20-day SMA) - simple, effective
2. **Secondary**: Z-score for statistical rigor
3. **Tertiary**: Percentile rank for context

### Suggested Parameters
- Lookback: 20 days (short-term), 50 days (medium-term)
- Spike threshold: 2.5-3x average
- Sustained threshold: 1.5x for 3+ consecutive periods
- Update baseline: Rolling, exclude extreme outliers

### Alert Levels
- **Level 1** (Watch): 1.5-2x average
- **Level 2** (Alert): 2-3x average
- **Level 3** (Critical): >3x average

## Unresolved Questions
- Should baseline exclude corporate action days (splits, dividends)?
- Optimal decay factor for EMA-based detection?
- How to handle low-liquidity stocks with erratic volume?

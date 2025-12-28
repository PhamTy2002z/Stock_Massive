# Recharts Financial Visualization Research

## Key Findings

- **ComposedChart** is recommended for financial dashboards - combines Line/Bar/Area in single view
- **AreaChart** best for volume and cumulative values with `fillOpacity` for overlapping data
- **LineChart** ideal for price movements, use `dot={false}` for clean rendering with many points
- **ResponsiveContainer** required for responsive design - parent must have explicit height
- Performance degrades with >500 data points - use data sampling (LTTB algorithm)
- Custom tooltips essential for financial formatting (currency, percentages)
- Disable animations (`isAnimationActive={false}`) for real-time data
- Dual Y-axes pattern common: price (left) + volume (right)

## Recommended Chart Types

| Chart | Use Case | Best For | Notes |
|-------|----------|----------|-------|
| **ComposedChart** | Multi-metric dashboards | Revenue + Profit trends, Price + Volume | Combines Line/Bar/Area, dual Y-axes support |
| **AreaChart** | Cumulative values | Stock price ranges, Volume over time | Use gradient fills, `fillOpacity` for visibility |
| **LineChart** | Trend tracking | Price movements, Moving averages | `strokeWidth={2}` for clarity, disable dots |
| **RadarChart** | Multi-dimensional comparison | Financial ratios, Performance metrics | Good for 3-6 metrics comparison |

## Code Patterns

### Pattern 1: ComposedChart for Revenue + Profit

```tsx
import { ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const data = [
  { quarter: 'Q1 2024', revenue: 12500000, profit: 3200000 },
  { quarter: 'Q2 2024', revenue: 14200000, profit: 3800000 },
  { quarter: 'Q3 2024', revenue: 13800000, profit: 3500000 },
  { quarter: 'Q4 2024', revenue: 16000000, profit: 4200000 },
];

<ResponsiveContainer width="100%" height={400}>
  <ComposedChart data={data}>
    <XAxis dataKey="quarter" />
    <YAxis yAxisId="left" />
    <YAxis yAxisId="right" orientation="right" />
    <Tooltip content={<CustomFinancialTooltip />} />
    <Legend />
    <Bar yAxisId="left" dataKey="revenue" fill="#3b82f6" name="Revenue" />
    <Line yAxisId="right" dataKey="profit" stroke="#22c55e" strokeWidth={2} name="Profit" />
  </ComposedChart>
</ResponsiveContainer>
```

### Pattern 2: Custom Tooltip with Financial Formatting

```tsx
const CustomFinancialTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-white p-3 border rounded shadow-lg">
      <p className="font-semibold mb-2">{label}</p>
      {payload.map((entry: any, index: number) => (
        <p key={index} style={{ color: entry.color }}>
          {entry.name}: {formatCurrency(entry.value)}
        </p>
      ))}
    </div>
  );
};

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};
```

### Pattern 3: Responsive Design with Debounce

```tsx
<ResponsiveContainer
  width="100%"
  height={400}
  debounce={50}  // Reduces re-renders during resize
>
  <LineChart
    data={financialData}
    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
  >
    <XAxis
      dataKey="date"
      tickFormatter={(value) => new Date(value).toLocaleDateString()}
    />
    <YAxis
      tickFormatter={(value) => `$${(value / 1000000).toFixed(1)}M`}
    />
    <Tooltip content={<CustomFinancialTooltip />} />
    <Line
      type="monotone"
      dataKey="value"
      stroke="#8884d8"
      dot={false}
      isAnimationActive={false}
    />
  </LineChart>
</ResponsiveContainer>
```

### Pattern 4: Data Sampling for Performance

```tsx
import { useMemo } from 'react';

// LTTB downsampling function (simplified)
function downsampleData(data: any[], targetPoints: number) {
  if (data.length <= targetPoints) return data;

  const bucketSize = (data.length - 2) / (targetPoints - 2);
  const sampled = [data[0]]; // Keep first point

  for (let i = 0; i < targetPoints - 2; i++) {
    const bucketStart = Math.floor(i * bucketSize) + 1;
    const bucketEnd = Math.floor((i + 1) * bucketSize) + 1;
    const bucketData = data.slice(bucketStart, bucketEnd);

    // Get max value point in bucket (preserves peaks)
    const maxPoint = bucketData.reduce((max, p) =>
      p.value > max.value ? p : max
    );
    sampled.push(maxPoint);
  }

  sampled.push(data[data.length - 1]); // Keep last point
  return sampled;
}

// Usage in component
const FinancialChart = ({ rawData }: { rawData: any[] }) => {
  const optimizedData = useMemo(
    () => downsampleData(rawData, 200),
    [rawData]
  );

  return (
    <ResponsiveContainer width="100%" height={400}>
      <AreaChart data={optimizedData}>
        {/* chart config */}
      </AreaChart>
    </ResponsiveContainer>
  );
};
```

## Performance Tips

- **Limit data points**: Keep 100-500 points for smooth rendering, use downsampling for larger datasets
- **Disable animations**: Set `isAnimationActive={false}` for real-time or frequent updates
- **Memoize data**: Use `useMemo` to prevent unnecessary data transformations
- **Debounce resize**: Set `debounce={50}` on ResponsiveContainer to reduce re-renders
- **Remove dots**: Use `dot={false}` on Line charts with many data points
- **Implement shouldUpdate**: Wrap charts in `React.memo()` with custom comparison
- **Consider canvas**: For very large datasets (>1000 points), use canvas-based alternatives
- **Aggregate wisely**: Pre-aggregate data server-side for time-series (daily → weekly → monthly)

## Design Best Practices

- **Colors**: Green (#22c55e) for positive/gains, Red (#ef4444) for negative/losses, Blue (#3b82f6) neutral
- **Y-axis formatting**: Use K/M/B suffixes for large numbers (`$12.5M` vs `$12,500,000`)
- **Tooltip positioning**: Default `position={{ x: 0, y: 0 }}` prevents overflow on small screens
- **Legend placement**: Use `verticalAlign="top"` for horizontal layouts, saves vertical space
- **Grid lines**: Enable `<CartesianGrid strokeDasharray="3 3" />` for better readability
- **Margin adjustment**: Set margins to prevent label cutoff: `margin={{ top: 5, right: 30, left: 20, bottom: 5 }}`

## Sources

- Recharts official documentation: https://recharts.org/
- GitHub Recharts repository: https://github.com/recharts/recharts
- LTTB downsampling algorithm: https://github.com/sveinn-steinarsson/flot-downsample
- React performance optimization patterns

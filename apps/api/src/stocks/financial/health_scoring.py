"""Financial health scoring algorithms.

Implements simplified Piotroski F-Score and dimension-based health scoring
for Vietnam stock market.
"""

from typing import Optional

# Benchmark thresholds for Vietnam market
BENCHMARKS = {
    "roe": {"good": 0.15, "excellent": 0.20},
    "roa": {"good": 0.08, "excellent": 0.12},
    "net_margin": {"good": 0.10, "excellent": 0.15},
    "gross_margin": {"good": 0.20, "excellent": 0.30},
    "current_ratio": {"good": 1.5, "excellent": 2.0},
    "quick_ratio": {"good": 1.0, "excellent": 1.5},
    "de": {"good": 1.0, "excellent": 0.5},  # Lower is better
    "pe": {"good": 15, "excellent": 10},  # Lower is better
    "pb": {"good": 2.0, "excellent": 1.5},  # Lower is better
    "asset_turnover": {"good": 0.8, "excellent": 1.2},
}

# Weights for overall health score calculation
DIMENSION_WEIGHTS = {
    "profitability": 0.30,
    "liquidity": 0.20,
    "leverage": 0.20,
    "efficiency": 0.15,
    "valuation": 0.15,
}


def normalize_score(
    value: Optional[float],
    benchmark: dict,
    inverse: bool = False,
) -> int:
    """Normalize a metric value to 0-100 score.

    Args:
        value: The metric value to normalize
        benchmark: Dict with 'good' and 'excellent' thresholds
        inverse: If True, lower values are better (D/E, P/E, P/B)

    Returns:
        Score from 0 to 100
    """
    if value is None:
        return 50  # Neutral score for missing data

    good = benchmark["good"]
    excellent = benchmark["excellent"]

    if inverse:
        # Lower is better (D/E, P/E, P/B)
        if value <= excellent:
            return 100
        elif value <= good:
            # Linear interpolation between 70-100
            return 70 + int(30 * (good - value) / (good - excellent))
        else:
            # Below good threshold, scale down from 70
            return max(0, 70 - int(70 * (value - good) / good))
    else:
        # Higher is better (ROE, ROA, margins)
        if value >= excellent:
            return 100
        elif value >= good:
            # Linear interpolation between 70-100
            return 70 + int(30 * (value - good) / (excellent - good))
        else:
            # Below good threshold, scale from 0-70
            return max(0, int(70 * value / good)) if good > 0 else 50


def calculate_dimension_score(metrics: dict, dimension: str) -> tuple[int, dict]:
    """Calculate score for a dimension from multiple metrics.

    Args:
        metrics: Dict of metric name -> value
        dimension: One of profitability, liquidity, leverage, efficiency, valuation

    Returns:
        Tuple of (dimension_score, metrics_dict)
    """
    if dimension == "profitability":
        roe = metrics.get("roe")
        roa = metrics.get("roa")
        net_margin = metrics.get("net_margin")
        scores = [
            normalize_score(roe, BENCHMARKS["roe"]),
            normalize_score(roa, BENCHMARKS["roa"]),
            normalize_score(net_margin, BENCHMARKS["net_margin"]),
        ]
        return (
            int(sum(scores) / len(scores)),
            {"roe": roe, "roa": roa, "net_margin": net_margin},
        )

    elif dimension == "liquidity":
        current_ratio = metrics.get("current_ratio")
        quick_ratio = metrics.get("quick_ratio")
        scores = [
            normalize_score(current_ratio, BENCHMARKS["current_ratio"]),
        ]
        if quick_ratio is not None:
            scores.append(normalize_score(quick_ratio, BENCHMARKS["quick_ratio"]))
        return (
            int(sum(scores) / len(scores)),
            {"current_ratio": current_ratio, "quick_ratio": quick_ratio},
        )

    elif dimension == "leverage":
        de = metrics.get("debt_to_equity") or metrics.get("de")
        scores = [normalize_score(de, BENCHMARKS["de"], inverse=True)]
        return (int(sum(scores) / len(scores)), {"de": de})

    elif dimension == "efficiency":
        asset_turnover = metrics.get("asset_turnover")
        if asset_turnover is not None:
            score = normalize_score(asset_turnover, BENCHMARKS["asset_turnover"])
        else:
            score = 50  # Neutral if no data
        return (score, {"asset_turnover": asset_turnover})

    elif dimension == "valuation":
        pe = metrics.get("pe") or metrics.get("price_to_earning")
        pb = metrics.get("pb") or metrics.get("price_to_book")
        scores = []
        if pe is not None and pe > 0:
            scores.append(normalize_score(pe, BENCHMARKS["pe"], inverse=True))
        if pb is not None and pb > 0:
            scores.append(normalize_score(pb, BENCHMARKS["pb"], inverse=True))
        if not scores:
            return (50, {"pe": pe, "pb": pb})
        return (int(sum(scores) / len(scores)), {"pe": pe, "pb": pb})

    else:
        return (50, {})


def calculate_f_score(current: dict, prior: dict) -> tuple[int, dict]:
    """Calculate simplified Piotroski F-Score (6 criteria).

    Args:
        current: Current period financial metrics
        prior: Prior period financial metrics

    Returns:
        Tuple of (f_score, details_dict)
    """
    # Get CFO from cash flow data
    current_cfo = current.get("cfo") or current.get("net_cfo") or 0
    current_net_income = current.get("net_income") or current.get("net_profit") or 0

    details = {
        "positive_roa": (current.get("roa") or 0) > 0,
        "positive_cfo": current_cfo > 0,
        "roa_improving": (current.get("roa") or 0) > (prior.get("roa") or 0),
        "accrual_quality": current_cfo > current_net_income,
        "leverage_decreasing": (current.get("debt_to_equity") or current.get("de") or 1)
        < (prior.get("debt_to_equity") or prior.get("de") or 1),
        "liquidity_improving": (current.get("current_ratio") or 0)
        > (prior.get("current_ratio") or 0),
    }
    score = sum(1 for v in details.values() if v)
    return score, details


def calculate_health_score(dimension_scores: dict[str, int]) -> int:
    """Calculate overall health score from dimension scores.

    Args:
        dimension_scores: Dict of dimension_name -> score (0-100)

    Returns:
        Weighted average score (0-100)
    """
    total = 0
    for dim, weight in DIMENSION_WEIGHTS.items():
        score = dimension_scores.get(dim, 50)  # Default to neutral
        total += score * weight
    return int(total)


def build_health_score_response(
    symbol: str,
    ratio_data: dict,
    prior_ratio_data: dict,
    cash_flow_data: dict,
    period: Optional[str] = None,
) -> dict:
    """Build complete health score response.

    Args:
        symbol: Stock symbol
        ratio_data: Current period ratio metrics
        prior_ratio_data: Prior period ratio metrics
        cash_flow_data: Current period cash flow data
        period: Period label (e.g., "Q4/2024")

    Returns:
        Dict matching HealthScoreResponse schema
    """
    # Merge cash flow data into ratio data for F-Score calculation
    current_metrics = {**ratio_data, **cash_flow_data}

    # Calculate dimension scores
    dimensions = {}
    dimension_scores = {}
    for dim in DIMENSION_WEIGHTS.keys():
        score, metrics = calculate_dimension_score(current_metrics, dim)
        dimensions[dim] = {"score": score, "metrics": metrics}
        dimension_scores[dim] = score

    # Calculate F-Score
    f_score, f_score_details = calculate_f_score(current_metrics, prior_ratio_data)

    # Calculate overall health score
    health_score = calculate_health_score(dimension_scores)

    return {
        "symbol": symbol,
        "health_score": health_score,
        "dimensions": dimensions,
        "f_score": f_score,
        "f_score_details": f_score_details,
        "period": period,
    }

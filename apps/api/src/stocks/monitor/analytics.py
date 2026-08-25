"""Pure deterministic calculations for Market Monitor read models."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import mean, median

from src.stocks.providers.contracts import Exchange
from src.stocks.signals.bars import Bar

from .frames import PreparedSymbol, ValuationObservation


@dataclass(frozen=True)
class BreadthReading:
    eligible: int
    evaluated: int
    advancing: int | None
    declining: int | None
    unchanged: int | None
    advance_decline_ratio: float | None
    above_ma20_pct: float | None
    above_ma50_pct: float | None
    above_ma200_pct: float | None
    new_high_20: int | None
    new_low_20: int | None
    new_high_252: int | None
    new_low_252: int | None
    advancing_volume_share: float | None
    liquidity_ratio: float | None
    issues: tuple[str, ...]


@dataclass(frozen=True)
class SectorReading:
    code: str
    name: str
    exchange: Exchange
    eligible: int
    evaluated: int
    return_1d_pct: float | None
    return_5d_pct: float | None
    return_20d_pct: float | None
    relative_strength_1d_pct: float | None
    relative_strength_5d_pct: float | None
    relative_strength_20d_pct: float | None
    advancing_pct: float | None
    liquidity_ratio: float | None
    rotation: str


@dataclass(frozen=True)
class ValuationReading:
    as_of: date | None
    eligible: int
    evaluated: int
    market_pe: float | None
    market_pb: float | None
    pe_percentile: float | None
    pb_percentile: float | None
    history_sessions: int


@dataclass(frozen=True)
class IndexReading:
    symbol: str
    level: float | None
    change: float | None
    change_pct: float | None
    above_ma20: bool | None
    above_ma50: bool | None
    above_ma200: bool | None


@dataclass(frozen=True)
class AdvanceDeclinePoint:
    session_date: date
    advancing: int
    declining: int
    unchanged: int
    cumulative: int


@dataclass(frozen=True)
class StockReading:
    symbol: str
    name: str
    exchange: Exchange
    sector_code: str | None
    sector_name: str | None
    last_price_vnd: float | None
    return_1d_pct: float | None
    return_5d_pct: float | None
    return_20d_pct: float | None
    above_ma20: bool | None
    above_ma50: bool | None
    above_ma200: bool | None
    liquidity_ratio: float | None
    adtv20_vnd: float | None
    foreign_net_1d_vnd: float | None
    foreign_net_5d_vnd: float | None
    foreign_net_20d_vnd: float | None
    foreign_flow_over_adtv: float | None
    issues: tuple[str, ...]


def _usable_bars(symbol: PreparedSymbol) -> tuple[Bar, ...]:
    return tuple(bar for bar in symbol.frame.bars if bar.close is not None and bar.close > 0)


def _return_pct(symbol: PreparedSymbol, sessions: int) -> float | None:
    bars = _usable_bars(symbol)
    if len(bars) <= sessions:
        return None
    start = bars[-sessions - 1].close
    end = bars[-1].close
    if start is None or end is None or start <= 0:
        return None
    return (end / start - 1) * 100


def _above_average(symbol: PreparedSymbol, sessions: int) -> bool | None:
    bars = _usable_bars(symbol)
    if len(bars) < sessions:
        return None
    values = [bar.close for bar in bars[-sessions:] if bar.close is not None]
    if len(values) != sessions:
        return None
    return values[-1] > mean(values)


def _new_extreme(symbol: PreparedSymbol, sessions: int, *, high: bool) -> bool | None:
    bars = _usable_bars(symbol)
    if len(bars) < sessions:
        return None
    values = [bar.close for bar in bars[-sessions:] if bar.close is not None]
    if len(values) != sessions:
        return None
    previous = values[:-1]
    return values[-1] > max(previous) if high else values[-1] < min(previous)


def _liquidity_ratio(symbol: PreparedSymbol) -> float | None:
    bars = symbol.frame.bars
    if len(bars) < 21:
        return None
    current = bars[-1].total_value_vnd
    baseline = [bar.total_value_vnd for bar in bars[-21:-1]]
    if current is None or any(value is None for value in baseline):
        return None
    average = mean(float(value) for value in baseline if value is not None)
    if average <= 0:
        return None
    return current / average


def _foreign_sum(symbol: PreparedSymbol, sessions: int) -> float | None:
    bars = symbol.frame.bars
    if len(bars) < sessions:
        return None
    values = [bar.foreign_net_value_vnd for bar in bars[-sessions:]]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None)


def _adtv(symbol: PreparedSymbol, sessions: int = 20) -> float | None:
    bars = symbol.frame.bars
    if len(bars) < sessions:
        return None
    values = [bar.total_value_vnd for bar in bars[-sessions:]]
    if any(value is None for value in values):
        return None
    result = mean(float(value) for value in values if value is not None)
    return result if result > 0 else None


def index_pulse(symbol: PreparedSymbol) -> IndexReading:
    bars = _usable_bars(symbol)
    latest = bars[-1].close if bars else None
    prior = bars[-2].close if len(bars) >= 2 else None
    change = latest - prior if latest is not None and prior is not None else None
    change_pct = (
        change / prior * 100
        if change is not None and prior is not None and prior > 0
        else None
    )
    return IndexReading(
        symbol=symbol.symbol,
        level=latest,
        change=change,
        change_pct=change_pct,
        above_ma20=_above_average(symbol, 20),
        above_ma50=_above_average(symbol, 50),
        above_ma200=_above_average(symbol, 200),
    )


def advance_decline_line(
    symbols: tuple[PreparedSymbol, ...],
) -> tuple[AdvanceDeclinePoint, ...]:
    days = sorted(
        {bar.session_date for symbol in symbols for bar in symbol.frame.bars}
    )
    by_symbol = {
        symbol.symbol: {bar.session_date: bar.close for bar in symbol.frame.bars}
        for symbol in symbols
    }
    cumulative = 0
    points: list[AdvanceDeclinePoint] = []
    for previous_day, day in zip(days, days[1:], strict=False):
        advancing = declining = unchanged = 0
        for closes in by_symbol.values():
            previous = closes.get(previous_day)
            current = closes.get(day)
            if previous is None or current is None or previous <= 0:
                continue
            if current > previous:
                advancing += 1
            elif current < previous:
                declining += 1
            else:
                unchanged += 1
        cumulative += advancing - declining
        points.append(
            AdvanceDeclinePoint(
                session_date=day,
                advancing=advancing,
                declining=declining,
                unchanged=unchanged,
                cumulative=cumulative,
            )
        )
    return tuple(points)


def stock_readings(
    symbols: tuple[PreparedSymbol, ...],
    *,
    sector_code: str | None = None,
    sort_by: str = "symbol",
    descending: bool = False,
) -> tuple[StockReading, ...]:
    allowed_sorts = {
        "symbol",
        "return_1d_pct",
        "return_5d_pct",
        "return_20d_pct",
        "liquidity_ratio",
        "foreign_net_20d_vnd",
        "foreign_flow_over_adtv",
    }
    if sort_by not in allowed_sorts:
        raise ValueError(f"unsupported stock sort: {sort_by}")

    rows: list[StockReading] = []
    for symbol in symbols:
        if sector_code is not None and symbol.sector_code != sector_code:
            continue
        flow_1 = _foreign_sum(symbol, 1)
        flow_5 = _foreign_sum(symbol, 5)
        flow_20 = _foreign_sum(symbol, 20)
        adtv = _adtv(symbol)
        issues = [issue.value for issue in symbol.issues]
        latest = symbol.frame.bars[-1] if symbol.frame.bars else None
        if len(symbol.frame.bars) < 20:
            issues.append("insufficient_history")
        elif any(
            bar.foreign_net_value_vnd is None
            for bar in symbol.frame.bars[-20:]
        ):
            issues.append("foreign_flow_not_stored")
        rows.append(
            StockReading(
                symbol=symbol.symbol,
                name=symbol.name,
                exchange=symbol.exchange,
                sector_code=symbol.sector_code,
                sector_name=symbol.sector_name,
                last_price_vnd=(
                    symbol.frame.bars[-1].close if symbol.frame.bars else None
                ),
                return_1d_pct=_return_pct(symbol, 1),
                return_5d_pct=_return_pct(symbol, 5),
                return_20d_pct=_return_pct(symbol, 20),
                above_ma20=_above_average(symbol, 20),
                above_ma50=_above_average(symbol, 50),
                above_ma200=_above_average(symbol, 200),
                liquidity_ratio=_liquidity_ratio(symbol),
                adtv20_vnd=adtv,
                foreign_net_1d_vnd=flow_1,
                foreign_net_5d_vnd=flow_5,
                foreign_net_20d_vnd=flow_20,
                foreign_flow_over_adtv=(
                    flow_20 / adtv
                    if flow_20 is not None and adtv is not None
                    else None
                ),
                issues=tuple(dict.fromkeys(issues)),
            )
        )

    if sort_by == "symbol":
        return tuple(sorted(rows, key=lambda item: item.symbol, reverse=descending))

    def sort_key(item: StockReading) -> tuple[bool, float, str]:
        value = getattr(item, sort_by)
        ordered = -float(value) if descending and value is not None else float(value or 0)
        return value is None, ordered, item.symbol

    return tuple(sorted(rows, key=sort_key))


def breadth(
    symbols: tuple[PreparedSymbol, ...],
    *,
    eligible: int | None = None,
) -> BreadthReading:
    advancing = declining = unchanged = 0
    advancing_volume = declining_volume = 0
    evaluated = 0
    ma_counts = {20: 0, 50: 0, 200: 0}
    ma_evaluated = {20: 0, 50: 0, 200: 0}
    extreme_counts = {(20, True): 0, (20, False): 0, (252, True): 0, (252, False): 0}
    extreme_evaluated = {20: 0, 252: 0}
    liquidity: list[float] = []

    for symbol in symbols:
        one_day = _return_pct(symbol, 1)
        latest = symbol.frame.bars[-1] if symbol.frame.bars else None
        if one_day is not None:
            evaluated += 1
            volume = latest.volume if latest and latest.volume is not None else 0
            if one_day > 0:
                advancing += 1
                advancing_volume += volume
            elif one_day < 0:
                declining += 1
                declining_volume += volume
            else:
                unchanged += 1
        for window in ma_counts:
            reading = _above_average(symbol, window)
            if reading is not None:
                ma_evaluated[window] += 1
                ma_counts[window] += int(reading)
        for window in extreme_evaluated:
            high = _new_extreme(symbol, window, high=True)
            low = _new_extreme(symbol, window, high=False)
            if high is not None and low is not None:
                extreme_evaluated[window] += 1
                extreme_counts[(window, True)] += int(high)
                extreme_counts[(window, False)] += int(low)
        ratio = _liquidity_ratio(symbol)
        if ratio is not None:
            liquidity.append(ratio)

    issues: list[str] = []
    ad_ratio = advancing / declining if declining else None
    if declining == 0:
        issues.append("declining_zero")
    directional_volume = advancing_volume + declining_volume

    def pct(count: int, sample: int) -> float | None:
        return count / sample * 100 if sample else None

    return BreadthReading(
        eligible=len(symbols) if eligible is None else eligible,
        evaluated=evaluated,
        advancing=advancing if evaluated else None,
        declining=declining if evaluated else None,
        unchanged=unchanged if evaluated else None,
        advance_decline_ratio=ad_ratio,
        above_ma20_pct=pct(ma_counts[20], ma_evaluated[20]),
        above_ma50_pct=pct(ma_counts[50], ma_evaluated[50]),
        above_ma200_pct=pct(ma_counts[200], ma_evaluated[200]),
        new_high_20=(extreme_counts[(20, True)] if extreme_evaluated[20] else None),
        new_low_20=(extreme_counts[(20, False)] if extreme_evaluated[20] else None),
        new_high_252=(extreme_counts[(252, True)] if extreme_evaluated[252] else None),
        new_low_252=(extreme_counts[(252, False)] if extreme_evaluated[252] else None),
        advancing_volume_share=(advancing_volume / directional_volume * 100 if directional_volume else None),
        liquidity_ratio=mean(liquidity) if liquidity else None,
        issues=tuple(issues),
    )


def sector_rotation(
    symbols: tuple[PreparedSymbol, ...],
    indices: dict[Exchange, PreparedSymbol],
    eligible_counts: dict[tuple[Exchange, str, str], int] | None = None,
) -> tuple[SectorReading, ...]:
    grouped: dict[tuple[Exchange, str, str], list[PreparedSymbol]] = defaultdict(list)
    for symbol in symbols:
        if symbol.sector_code and symbol.sector_name:
            grouped[(symbol.exchange, symbol.sector_code, symbol.sector_name)].append(symbol)

    rows: list[SectorReading] = []
    keys = set(grouped)
    if eligible_counts is not None:
        keys.update(eligible_counts)
    for exchange, code, name in keys:
        members = grouped[(exchange, code, name)]
        returns = {
            horizon: [value for item in members if (value := _return_pct(item, horizon)) is not None]
            for horizon in (1, 5, 20)
        }
        one_day = returns[1]
        current = median(one_day) if one_day else None
        index_returns = {
            horizon: _return_pct(indices[exchange], horizon) if exchange in indices else None
            for horizon in (1, 5, 20)
        }
        sector_returns = {
            horizon: median(returns[horizon]) if returns[horizon] else None
            for horizon in (1, 5, 20)
        }
        relative = {
            horizon: (
                sector_returns[horizon] - index_returns[horizon]
                if sector_returns[horizon] is not None and index_returns[horizon] is not None
                else None
            )
            for horizon in (1, 5, 20)
        }
        advancing_pct = sum(value > 0 for value in one_day) / len(one_day) * 100 if one_day else None
        liquidity = [value for item in members if (value := _liquidity_ratio(item)) is not None]
        return_20 = median(returns[20]) if returns[20] else None
        if relative[20] is None or return_20 is None:
            rotation = "unavailable"
        elif relative[20] > 0 and return_20 > 0:
            rotation = "leading"
        elif relative[20] > 0:
            rotation = "improving"
        elif return_20 > 0:
            rotation = "weakening"
        else:
            rotation = "lagging"
        rows.append(
            SectorReading(
                code=code,
                name=name,
                exchange=exchange,
                eligible=(
                    eligible_counts.get((exchange, code, name), len(members))
                    if eligible_counts is not None
                    else len(members)
                ),
                evaluated=len(one_day),
                return_1d_pct=current,
                return_5d_pct=median(returns[5]) if returns[5] else None,
                return_20d_pct=return_20,
                relative_strength_1d_pct=relative[1],
                relative_strength_5d_pct=relative[5],
                relative_strength_20d_pct=relative[20],
                advancing_pct=advancing_pct,
                liquidity_ratio=median(liquidity) if liquidity else None,
                rotation=rotation,
            )
        )
    return tuple(sorted(rows, key=lambda item: (item.exchange.value, item.code)))


def _percentile(value: float | None, history: list[float]) -> float | None:
    if value is None or not history:
        return None
    return sum(item <= value for item in history) / len(history) * 100


def valuation_regime(
    points: tuple[ValuationObservation, ...],
    *,
    eligible: int | None = None,
    minimum_history_sessions: int = 20,
) -> ValuationReading:
    if not points:
        return ValuationReading(None, eligible or 0, 0, None, None, None, None, 0)
    by_day: dict[date, list[ValuationObservation]] = defaultdict(list)
    for point in points:
        by_day[point.session_date].append(point)
    as_of = max(by_day)
    latest = by_day[as_of]
    pe_values = [item.pe for item in latest if item.pe is not None and item.pe > 0]
    pb_values = [item.pb for item in latest if item.pb is not None and item.pb > 0]
    market_pe = median(pe_values) if pe_values else None
    market_pb = median(pb_values) if pb_values else None
    daily_pe = [median(values) for day in sorted(by_day) if (values := [item.pe for item in by_day[day] if item.pe is not None and item.pe > 0])]
    daily_pb = [median(values) for day in sorted(by_day) if (values := [item.pb for item in by_day[day] if item.pb is not None and item.pb > 0])]
    eligible_count = len({point.symbol for point in points}) if eligible is None else eligible
    evaluated = len({item.symbol for item in latest if (item.pe is not None and item.pe > 0) or (item.pb is not None and item.pb > 0)})
    return ValuationReading(
        as_of=as_of,
        eligible=eligible_count,
        evaluated=evaluated,
        market_pe=market_pe,
        market_pb=market_pb,
        pe_percentile=(
            _percentile(market_pe, daily_pe)
            if len(daily_pe) >= minimum_history_sessions
            else None
        ),
        pb_percentile=(
            _percentile(market_pb, daily_pb)
            if len(daily_pb) >= minimum_history_sessions
            else None
        ),
        history_sessions=len(by_day),
    )

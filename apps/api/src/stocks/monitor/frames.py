"""Immutable inputs consumed by Market Monitor calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from types import MappingProxyType

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers.contracts import (
    Capability,
    Exchange,
    ValuationSnapshot,
    main_source,
)
from src.stocks.providers.normalize import VN_TZ, day_in_vn
from src.stocks.providers.store import resolve_sessions
from src.stocks.signals.bars import (
    BarFrame,
    BarSeries,
    prepare_bars,
    prepare_bars_context,
)
from src.stocks.signals.issues import SignalIssue
from src.stocks.trading_day import latest_trading_day
from src.stocks.universe import build_universe

from .schemas import MonitorExchange


INDEX_BY_EXCHANGE: Mapping[Exchange, str] = MappingProxyType(
    {Exchange.HOSE: "VNINDEX", Exchange.HNX: "HNXINDEX"}
)


@dataclass(frozen=True)
class PreparedSymbol:
    symbol: str
    name: str
    exchange: Exchange
    sector_code: str | None
    sector_name: str | None
    frame: BarFrame
    issues: tuple[SignalIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValuationObservation:
    session_date: date
    symbol: str
    sector_code: str | None
    pe: float | None
    pb: float | None


@dataclass(frozen=True)
class FrameRefusal:
    symbol: str
    issues: tuple[SignalIssue, ...]


@dataclass(frozen=True)
class MonitorFrameSet:
    exchange: MonitorExchange
    as_of: date | None
    eligible_symbols: tuple[str, ...]
    symbols: tuple[PreparedSymbol, ...]
    indices: Mapping[Exchange, PreparedSymbol]
    valuations: tuple[ValuationObservation, ...]
    sector_eligible_counts: Mapping[tuple[Exchange, str, str], int]
    refusals: tuple[FrameRefusal, ...]
    index_refusals: Mapping[Exchange, SignalIssue]

    @property
    def eligible(self) -> int:
        return len(self.eligible_symbols)

    @property
    def evaluated(self) -> int:
        return len(self.symbols)


class MarketFrameLoader:
    """Build one immutable monitor input from bounded stored-data reads."""

    def __init__(
        self,
        session: Session,
        *,
        universe_symbols: Sequence[str] | None = None,
    ) -> None:
        self.session = session
        self._universe_symbols = (
            None
            if universe_symbols is None
            else tuple(sorted({symbol.upper() for symbol in universe_symbols}))
        )

    def load(
        self,
        exchange: MonitorExchange,
        *,
        as_of: date | None = None,
        window_days: int = 253,
    ) -> MonitorFrameSet:
        if window_days < 2:
            raise ValueError("monitor windows require at least two sessions")
        resolved_as_of = as_of or latest_trading_day(self.session)
        identities = self._identities(exchange)
        eligible_symbols = tuple(item.symbol for item in identities)
        if resolved_as_of is None or not eligible_symbols:
            return MonitorFrameSet(
                exchange=exchange,
                as_of=resolved_as_of,
                eligible_symbols=eligible_symbols,
                symbols=(),
                indices=MappingProxyType({}),
                valuations=(),
                sector_eligible_counts=MappingProxyType(
                    self._sector_counts(identities)
                ),
                refusals=tuple(
                    FrameRefusal(
                        symbol=symbol,
                        issues=(SignalIssue.INSUFFICIENT_HISTORY,),
                    )
                    for symbol in eligible_symbols
                ),
                index_refusals=MappingProxyType(
                    {
                        board: SignalIssue.INSUFFICIENT_HISTORY
                        for board in INDEX_BY_EXCHANGE
                    }
                ),
            )

        by_symbol = {item.symbol: item for item in identities}
        context = prepare_bars_context(
            self.session,
            eligible_symbols,
            window_days,
            end=resolved_as_of,
        )
        prepared: list[PreparedSymbol] = []
        refusals: list[FrameRefusal] = []
        for symbol in eligible_symbols:
            frame, health = prepare_bars(
                self.session,
                symbol,
                window_days,
                min_sessions=2,
                end=resolved_as_of,
                peers=eligible_symbols,
                context=context,
            )
            if frame is None:
                refusals.append(
                    FrameRefusal(
                        symbol=symbol,
                        issues=(health.refusal or SignalIssue.UNAVAILABLE,),
                    )
                )
                continue
            if health.last_session != resolved_as_of:
                refusals.append(
                    FrameRefusal(
                        symbol=symbol,
                        issues=(SignalIssue.MISSING_TARGET_SESSION,),
                    )
                )
                continue
            identity = by_symbol[symbol]
            prepared.append(
                PreparedSymbol(
                    symbol=symbol,
                    name=identity.company_name or symbol,
                    exchange=Exchange(identity.exchange),
                    sector_code=identity.icb_code,
                    sector_name=identity.icb_name,
                    frame=frame,
                    issues=health.degradations,
                )
            )

        indices, index_refusals = self._indices(
            exchange,
            resolved_as_of,
            window_days=window_days,
        )
        valuations = self._valuations(
            eligible_symbols,
            by_symbol,
            resolved_as_of,
            window_days=window_days,
        )
        return MonitorFrameSet(
            exchange=exchange,
            as_of=resolved_as_of,
            eligible_symbols=eligible_symbols,
            symbols=tuple(prepared),
            indices=MappingProxyType(indices),
            valuations=valuations,
            sector_eligible_counts=MappingProxyType(self._sector_counts(identities)),
            refusals=tuple(refusals),
            index_refusals=MappingProxyType(index_refusals),
        )

    def _identities(self, exchange: MonitorExchange) -> tuple[ListingRoster, ...]:
        universe = (
            self._universe_symbols
            if self._universe_symbols is not None
            else build_universe(self.session).symbols
        )
        if not universe:
            return ()
        boards = (
            (Exchange.HOSE.value, Exchange.HNX.value)
            if exchange is MonitorExchange.ALL
            else (exchange.value,)
        )
        rows = self.session.execute(
            select(ListingRoster)
            .where(
                ListingRoster.symbol.in_(universe),
                ListingRoster.exchange.in_(boards),
                ListingRoster.is_listed.is_(True),
            )
            .order_by(ListingRoster.symbol.asc())
        ).scalars()
        return tuple(rows)

    @staticmethod
    def _sector_counts(
        identities: Sequence[ListingRoster],
    ) -> dict[tuple[Exchange, str, str], int]:
        counts: dict[tuple[Exchange, str, str], int] = {}
        for identity in identities:
            if not identity.icb_code or not identity.icb_name:
                continue
            key = (Exchange(identity.exchange), identity.icb_code, identity.icb_name)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _indices(
        self,
        exchange: MonitorExchange,
        as_of: date,
        *,
        window_days: int,
    ) -> tuple[dict[Exchange, PreparedSymbol], dict[Exchange, SignalIssue]]:
        boards = (
            tuple(INDEX_BY_EXCHANGE)
            if exchange is MonitorExchange.ALL
            else (Exchange(exchange.value),)
        )
        names = tuple(INDEX_BY_EXCHANGE[board] for board in boards)
        context = prepare_bars_context(
            self.session,
            names,
            window_days,
            end=as_of,
            series=BarSeries.MARKET_INDEX,
        )
        prepared: dict[Exchange, PreparedSymbol] = {}
        refused: dict[Exchange, SignalIssue] = {}
        for board in boards:
            symbol = INDEX_BY_EXCHANGE[board]
            frame, health = prepare_bars(
                self.session,
                symbol,
                window_days,
                min_sessions=2,
                end=as_of,
                series=BarSeries.MARKET_INDEX,
                context=context,
            )
            if frame is None:
                refused[board] = health.refusal or SignalIssue.UNAVAILABLE
                continue
            if health.last_session != as_of:
                refused[board] = SignalIssue.MISSING_TARGET_SESSION
                continue
            prepared[board] = PreparedSymbol(
                symbol=symbol,
                name="VN-Index" if board is Exchange.HOSE else "HNX-Index",
                exchange=board,
                sector_code=None,
                sector_name=None,
                frame=frame,
                issues=health.degradations,
            )
        return prepared, refused

    def _valuations(
        self,
        symbols: tuple[str, ...],
        identities: Mapping[str, ListingRoster],
        as_of: date,
        *,
        window_days: int,
    ) -> tuple[ValuationObservation, ...]:
        if not symbols:
            return ()
        start = as_of - timedelta(days=max(window_days * 2, 366))
        sources = [main_source(Capability.VALUATION).value]
        lower = datetime.combine(start, time.min, tzinfo=VN_TZ)
        upper = datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=VN_TZ)
        rows = self.session.execute(
            select(ProviderSnapshot)
            .where(
                ProviderSnapshot.capability == Capability.VALUATION.value,
                ProviderSnapshot.symbol.in_(symbols),
                ProviderSnapshot.source.in_(sources),
                ProviderSnapshot.effective_at >= lower,
                ProviderSnapshot.effective_at < upper,
            )
            .order_by(
                ProviderSnapshot.symbol.asc(),
                ProviderSnapshot.effective_at.asc(),
                ProviderSnapshot.observed_at.asc(),
            )
        ).scalars()
        grouped: dict[str, list[ProviderSnapshot]] = {}
        for row in rows:
            grouped.setdefault(row.symbol, []).append(row)

        observations: list[ValuationObservation] = []
        for symbol in symbols:
            resolved = resolve_sessions(
                grouped.get(symbol, ()),
                Capability.VALUATION,
            )
            for effective_at, row in sorted(resolved.items()):
                snapshot = ValuationSnapshot.model_validate(row.payload)
                observations.append(
                    ValuationObservation(
                        session_date=day_in_vn(effective_at),
                        symbol=symbol,
                        sector_code=identities[symbol].icb_code,
                        pe=snapshot.provider_pe,
                        pb=snapshot.provider_pb,
                    )
                )
        return tuple(observations)

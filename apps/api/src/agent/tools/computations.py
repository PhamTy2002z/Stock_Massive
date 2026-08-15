"""The five model-facing computation clusters over the Signal Registry."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.orm import Session

from src.core.database import sync_session_factory
from src.stocks.shared import validate_symbol
from src.stocks.signals import (
    ADTV_MONEY,
    ADTV_SHARES,
    AMIHUD_ILLIQUIDITY,
    BAND_PRESSURE,
    BOLLINGER_PERCENT_B,
    BOOK_YIELD_PERCENTILE,
    DRAWDOWN_VERSUS_BENCHMARK,
    EARNINGS_YIELD_PERCENTILE,
    FOREIGN_FLOW_PERSISTENCE,
    FOREIGN_FLOW_PRESSURE,
    MACD,
    MEAN_REVERSION_Z,
    MOMENTUM_RANK,
    REALIZED_VOLATILITY,
    RELATIVE_STRENGTH,
    ROE_PERCENTILE,
    RSI,
    SHARPE,
    SIZE_PERCENTILE,
    SORTINO,
    TREND_SIGNAL,
    VOLATILITY_REGIME_Z,
    FieldValue,
    SignalField,
    SignalIssue,
    fractional_kelly_sizing,
    serve_cross_section,
    serve_field,
)
from src.stocks.universe import build_universe

from .catalog import ToolCatalog, ToolContext, ToolSpec
from .data import SessionFactory, UniverseFactory, _object_schema
from .fields import (
    REGISTERED_FIELD_VALUES_KEY,
    SHARED_WINDOW_HEALTH_KEY,
    RefusedRegisteredField,
)
from .scope import structured_universe_refusal

RISK_FIELDS = (
    REALIZED_VOLATILITY,
    DRAWDOWN_VERSUS_BENCHMARK,
    SHARPE,
    SORTINO,
)
MARKET_BEHAVIOR_TOOL_FIELDS = (
    VOLATILITY_REGIME_Z,
    ADTV_MONEY,
    ADTV_SHARES,
    AMIHUD_ILLIQUIDITY,
    BAND_PRESSURE,
    # The fitted half-life, its interval and the T+2 actionability bit travel in
    # this field's registered details, so returning the twin primary value would
    # repeat one gauge under the 4 KB result ceiling.
    MEAN_REVERSION_Z,
)
CROSS_SECTIONAL_TOOL_FIELDS = (
    MOMENTUM_RANK,
    TREND_SIGNAL,
    RELATIVE_STRENGTH,
    EARNINGS_YIELD_PERCENTILE,
    BOOK_YIELD_PERCENTILE,
    ROE_PERCENTILE,
    SIZE_PERCENTILE,
)
FOREIGN_FLOW_TOOL_FIELDS = (
    FOREIGN_FLOW_PRESSURE,
    FOREIGN_FLOW_PERSISTENCE,
)
INDICATOR_FIELDS = (RSI, MACD, BOLLINGER_PERCENT_B)


class ComputationTools:
    """Choose registered outputs; every number is still computed in signals."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory = sync_session_factory,
        universe_factory: UniverseFactory = build_universe,
    ) -> None:
        self._session_factory = session_factory
        self._universe_factory = universe_factory

    def catalog(self, *, trace_writer) -> ToolCatalog:
        return ToolCatalog(self.registrations(), trace_writer=trace_writer)

    def registrations(self) -> tuple[ToolSpec, ...]:
        symbol = {"type": "string", "description": "Vietnamese equity symbol."}
        return (
            self._registration(
                "risk_metrics",
                "Read registered realized-volatility, drawdown and risk-adjusted-return fields.",
                RISK_FIELDS,
                _object_schema({"symbol": symbol}, ("symbol",)),
            ),
            self._registration(
                "market_behavior",
                (
                    "Read registered volatility-regime, liquidity, band-pressure "
                    "and mean-reversion fields."
                ),
                MARKET_BEHAVIOR_TOOL_FIELDS,
                _object_schema({"symbol": symbol}, ("symbol",)),
            ),
            self._registration(
                "cross_sectional",
                (
                    "Read registered momentum, trend, relative-strength and "
                    "factor positions within the Universe."
                ),
                CROSS_SECTIONAL_TOOL_FIELDS,
                _object_schema({"symbol": symbol}, ("symbol",)),
            ),
            self._registration(
                "foreign_flow",
                "Read registered net foreign-buy pressure and persistence fields.",
                FOREIGN_FLOW_TOOL_FIELDS,
                _object_schema({"symbol": symbol}, ("symbol",)),
            ),
            self._registration(
                "indicator_pack",
                (
                    "Read descriptive RSI, MACD and Bollinger vocabulary, "
                    "optionally with a fractional-Kelly scenario from user inputs."
                ),
                INDICATOR_FIELDS,
                _object_schema(
                    {
                        "symbol": symbol,
                        "edge_decimal": {
                            "type": "number",
                            "minimum": 0,
                            "description": "User-supplied expected edge as a decimal fraction.",
                        },
                        "variance_decimal_squared": {
                            "type": "number",
                            "exclusiveMinimum": 0,
                            "description": (
                                "User-supplied return variance in decimal-squared "
                                "units."
                            ),
                        },
                    },
                    ("symbol",),
                ),
            ),
        )

    def _registration(
        self,
        name: str,
        description: str,
        fields: Sequence[SignalField],
        parameters: Mapping[str, Any],
    ) -> ToolSpec:
        async def call(
            context: ToolContext, arguments: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            return await asyncio.to_thread(
                self._serve_cluster,
                name,
                tuple(fields),
                context,
                dict(arguments),
            )

        return ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            callable=call,
            registered_fields=tuple(field.name for field in fields),
            shared_window_health=True,
        )

    def _serve_cluster(
        self,
        name: str,
        fields: tuple[SignalField, ...],
        context: ToolContext,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        symbol = validate_symbol(str(arguments["symbol"]))
        with self._session_factory() as session:
            refusal = structured_universe_refusal(
                session,
                self._universe_factory,
                symbol,
                context.trading_day,
            )
            if refusal is not None:
                return refusal
            universe = self._universe_factory(session)
            answers = self._serve_fields(
                session,
                symbol,
                fields,
                universe.symbols,
                context,
            )

        healthy_answers = [
            answer for answer in answers.values() if isinstance(answer, FieldValue)
        ]
        if not healthy_answers:
            raise ValueError(f"{name} produced no Window Health")
        shared = max(
            healthy_answers,
            key=lambda answer: (answer.health.sessions_used, answer.field.min_sessions),
        ).health
        result: dict[str, Any] = {
            "symbol": symbol,
            "as_of": context.trading_day.isoformat(),
            REGISTERED_FIELD_VALUES_KEY: answers,
            SHARED_WINDOW_HEALTH_KEY: shared,
        }
        if name == "indicator_pack":
            result["fractional_kelly"] = self._kelly(arguments)
        return result

    @staticmethod
    def _serve_fields(
        session: Session,
        symbol: str,
        fields: Sequence[SignalField],
        universe_symbols: Sequence[str],
        context: ToolContext,
    ) -> dict[str, FieldValue | RefusedRegisteredField]:
        answers: dict[str, FieldValue | RefusedRegisteredField] = {}
        for field in fields:
            if field.ranked is None:
                answers[field.name] = serve_field(
                    session,
                    symbol,
                    field,
                    end=context.trading_day,
                    peers=universe_symbols,
                )
                continue
            cross_section = serve_cross_section(
                session,
                universe_symbols,
                field,
                end=context.trading_day,
            )
            answer = cross_section.values.get(symbol)
            if answer is not None:
                answers[field.name] = answer
                continue
            reason = (
                cross_section.excluded.get(symbol)
                or cross_section.refusal
                or SignalIssue.INSUFFICIENT_CROSS_SECTION
            )
            answers[field.name] = RefusedRegisteredField(field=field, refusal=reason)
        return answers

    @staticmethod
    def _kelly(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        has_edge = arguments.get("edge_decimal") is not None
        has_variance = arguments.get("variance_decimal_squared") is not None
        if not has_edge and not has_variance:
            return {"status": "not_requested"}
        if has_edge != has_variance:
            return {
                "status": "refused",
                "reason": "edge_and_variance_required_together",
            }
        edge = float(arguments["edge_decimal"])
        variance = float(arguments["variance_decimal_squared"])
        sizing = fractional_kelly_sizing(edge=edge, variance=variance)
        return {
            "provenance": "user_input",
            "scenario_only": True,
            "assumptions": {
                "edge_decimal": sizing.edge_input,
                "variance_decimal_squared": sizing.variance_input,
            },
            "quarter_kelly_fraction": sizing.quarter_kelly,
            "half_kelly_fraction": sizing.half_kelly,
            "full_kelly_ceiling_fraction": sizing.full_kelly_ceiling,
            "half_kelly_sensitivity_fraction": sizing.input_sensitivity_range,
        }


__all__ = [
    "CROSS_SECTIONAL_TOOL_FIELDS",
    "ComputationTools",
    "FOREIGN_FLOW_TOOL_FIELDS",
    "INDICATOR_FIELDS",
    "MARKET_BEHAVIOR_TOOL_FIELDS",
    "RISK_FIELDS",
]

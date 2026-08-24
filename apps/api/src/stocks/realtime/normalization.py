"""Versioned DNSE-to-canonical unit normalization rules."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from pydantic import Field

from .contracts import ProductGroup, RealtimeContract


class NormalizationMeasure(str, Enum):
    CASH_PRICE = "cash_price"
    FUTURES_PRICE = "futures_price"
    TRADE_QUANTITY = "trade_quantity"
    BAR_VOLUME = "bar_volume"
    FOREIGN_VOLUME = "foreign_volume"
    GROSS_TRADE_VALUE = "gross_trade_value"
    FOREIGN_VALUE = "foreign_value"


class NormalizationRule(RealtimeContract):
    """One audited conversion for a product, board, and field family."""

    product_group: ProductGroup
    board: str = Field(pattern=r"^(\*|[A-Z0-9_-]{1,32})$")
    measure: NormalizationMeasure
    multiplier: Decimal = Field(gt=0)
    integral_output: bool
    canonical_unit: str = Field(pattern=r"^(VND|share|contract|index_point)$")


_ANY_BOARD = "*"

# Version 1 contains only rules proven by the August 24, 2026 DNSE audit.  In
# particular, quote quantity is absent until a market-hours probe proves it.
_V1_RULES = (
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board=_ANY_BOARD,
        measure=NormalizationMeasure.CASH_PRICE,
        multiplier=Decimal("1000"),
        integral_output=False,
        canonical_unit="VND",
    ),
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board="G1",
        measure=NormalizationMeasure.TRADE_QUANTITY,
        multiplier=Decimal("10"),
        integral_output=True,
        canonical_unit="share",
    ),
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board="G4",
        measure=NormalizationMeasure.TRADE_QUANTITY,
        multiplier=Decimal("1"),
        integral_output=True,
        canonical_unit="share",
    ),
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board=_ANY_BOARD,
        measure=NormalizationMeasure.BAR_VOLUME,
        multiplier=Decimal("1"),
        integral_output=True,
        canonical_unit="share",
    ),
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board=_ANY_BOARD,
        measure=NormalizationMeasure.FOREIGN_VOLUME,
        multiplier=Decimal("1"),
        integral_output=True,
        canonical_unit="share",
    ),
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board=_ANY_BOARD,
        measure=NormalizationMeasure.GROSS_TRADE_VALUE,
        multiplier=Decimal("1000000000"),
        integral_output=False,
        canonical_unit="VND",
    ),
    NormalizationRule(
        product_group=ProductGroup.EQUITY,
        board=_ANY_BOARD,
        measure=NormalizationMeasure.FOREIGN_VALUE,
        multiplier=Decimal("1"),
        integral_output=False,
        canonical_unit="VND",
    ),
    NormalizationRule(
        product_group=ProductGroup.FUTURES,
        board=_ANY_BOARD,
        measure=NormalizationMeasure.FUTURES_PRICE,
        multiplier=Decimal("1"),
        integral_output=False,
        canonical_unit="index_point",
    ),
)


def _rule_map(
    rules: tuple[NormalizationRule, ...],
) -> Mapping[tuple[str, str, str], NormalizationRule]:
    indexed: dict[tuple[str, str, str], NormalizationRule] = {}
    for rule in rules:
        key = (rule.product_group.value, rule.board, rule.measure.value)
        if key in indexed:
            raise ValueError(f"duplicate normalization rule: {key}")
        indexed[key] = rule
    return MappingProxyType(indexed)


NORMALIZATION_RULES: Mapping[int, Mapping[tuple[str, str, str], NormalizationRule]] = (
    MappingProxyType({1: _rule_map(_V1_RULES)})
)


def normalization_rule(
    *,
    version: int,
    product_group: ProductGroup,
    board: str,
    measure: NormalizationMeasure,
) -> NormalizationRule:
    """Resolve one rule or refuse an unproven version/board combination."""
    rules = NORMALIZATION_RULES.get(version)
    if rules is None:
        raise ValueError(f"unknown normalization version: {version}")
    normalized_board = board.strip().upper()
    if re.fullmatch(r"[A-Z0-9_-]{1,32}", normalized_board) is None:
        raise ValueError(f"invalid board identity: {board!r}")
    key = (product_group.value, normalized_board, measure.value)
    wildcard = (product_group.value, _ANY_BOARD, measure.value)
    rule = rules.get(key) or rules.get(wildcard)
    if rule is None:
        raise ValueError(
            "no audited normalization rule for "
            f"version={version}, product_group={product_group.value}, "
            f"board={normalized_board}, measure={measure.value}"
        )
    return rule


def normalize_dnse_value(
    value: Decimal | int | str,
    *,
    version: int,
    product_group: ProductGroup,
    board: str,
    measure: NormalizationMeasure,
) -> Decimal | int:
    """Normalize an admitted numeric field exactly once through its rule."""
    rule = normalization_rule(
        version=version,
        product_group=product_group,
        board=board,
        measure=measure,
    )
    try:
        normalized = Decimal(str(value)) * rule.multiplier
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("provider value must be a canonical decimal") from exc
    if not normalized.is_finite():
        raise ValueError("normalized values must be finite")
    if normalized < 0:
        raise ValueError("normalized values cannot be negative")
    if rule.integral_output:
        integral = normalized.to_integral_value()
        if normalized != integral:
            raise ValueError("normalization must produce a whole canonical count")
        return int(integral)
    return normalized

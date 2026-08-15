"""The versioned list of **Signal Field**s an Analysis is allowed to carry.

The model does not choose freely from the **Signal Registry**. It is handed a
bundle the backend fixed in advance, capped at six fields per axis, so that the
input to a generation is stable, reviewable and bounded (``CONTEXT.md``,
spec 0003 §8.4). This module is that list, and nothing else: it names fields,
it does not read them.

Three rules hold it together, and each is checked at import rather than left to
a reviewer:

**The four axes are fixed and ordered.** ``technical → fundamental →
money_flow → news``. Section order is not the model's to choose, so it is
declared once here and every reader takes it from ``AXIS_ORDER``.

**Six per axis, whatever the industry.** The cap is what keeps a generation's
input bounded. Banks add three fundamentals to the three every industry gets,
which is exactly six; anything that would take an axis past it fails at import.

**A field the profile names is emitted even when nothing computes it.** In v1
that covers every ``bank_metrics.*``, ``developer_metrics.*`` and
``retail_metrics.*`` field and both news counts — none of them has a durable
store behind it (spec 0003 §13). They are still named, because a profile that
silently dropped them would make two Analyses carrying the same
``fieldProfileVersion`` mean two different things, and nothing downstream could
tell. The envelope emits them ``refused`` with reason ``unavailable``.

The price-zone field is deliberately not in the Technical block. It is core
artifact evidence — the artifact requires it, and a refused one fails the run —
so it travels beside the axes rather than inside one, and it does not consume a
Technical slot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from src.stocks.signals.registry import REGISTRY

# Stamped on every Analysis payload. A reader meeting two Analyses has to be
# able to ask whether they were built from the same list of fields, and the
# answer is this string rather than a diff of their contents.
FIELD_PROFILE_VERSION = "v1"

# What keeps one generation's input bounded. Six is the spec's number and it is
# enforced below rather than described: an axis grown to seven is a prompt that
# costs more on every symbol, every night, for a change nobody priced.
MAX_FIELDS_PER_AXIS = 6

# The registered field the artifact is built around: a ±1 realized Yang-Zhang σ
# half-width in percent, with the two prices beside it.
PRICE_ZONE_FIELD_ID = "price_zone.ordinary_range_pct"


class Axis(str, Enum):
    """The four sections of an Analysis, in the only order they may appear."""

    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MONEY_FLOW = "money_flow"
    NEWS = "news"


AXIS_ORDER: tuple[Axis, ...] = (
    Axis.TECHNICAL,
    Axis.FUNDAMENTAL,
    Axis.MONEY_FLOW,
    Axis.NEWS,
)


class AnalysisIndustry(str, Enum):
    """Which per-industry fundamentals a symbol's profile adds, if any.

    Five values rather than three. ``OTHER`` is a symbol this system has
    classified and that is none of the three the profile has metrics for;
    ``UNCLASSIFIED`` is a symbol nothing has classified at all. They select the
    same (empty) industry block today, and they are still different facts: one
    says the profile has nothing extra to offer this business, the other says
    the store does not yet know what business it is. Folded together, the day
    ICB classification is persisted would look like the day every symbol changed
    industry.
    """

    BANKS = "banks"
    REAL_ESTATE = "real_estate"
    RETAIL = "retail"
    OTHER = "other"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class ProfileField:
    """One field the profile names, registered or not.

    ``description`` is what the envelope says about a field that has no registry
    declaration to quote. A registered field's sanctioned reading comes from the
    registry and is never restated here — two copies of an interpretation are
    two interpretations as soon as one of them is edited.
    """

    field_id: str
    label: str
    description: str

    @property
    def registered(self) -> bool:
        """Whether the **Signal Registry** has a computation behind this id."""
        return self.field_id in REGISTRY


def _registered(field_id: str, label: str) -> ProfileField:
    """A profile entry whose reading the registry already owns."""
    return ProfileField(
        field_id=field_id,
        label=label,
        # Never displayed for a registered field: the envelope quotes the
        # registry's `interpretation` instead. Present so that the two kinds of
        # entry are one type, and so a field losing its registration degrades to
        # an honest sentence rather than to an empty one.
        description=f"{label}, as the Signal Registry declares it.",
    )


TECHNICAL_FIELDS: tuple[ProfileField, ...] = (
    _registered(
        "realized_volatility.yang_zhang_annualized_pct", "Realized volatility"
    ),
    _registered("volatility_regime.gk_variance_robust_z", "Volatility regime"),
    _registered("drawdown_stats.current_drawdown_pct", "Current drawdown"),
    _registered("band_pressure.limit_days_in_window", "Limit-lock days"),
    _registered("momentum_rank.percentile_12_2", "Momentum percentile"),
    _registered("indicator_pack.rsi_14", "RSI (14)"),
)

# Every industry gets these three, which is why they are not in the block below.
SHARED_FUNDAMENTAL_FIELDS: tuple[ProfileField, ...] = (
    _registered("factor_percentiles.roe_percentile", "Return on equity percentile"),
    _registered(
        "factor_percentiles.earnings_yield_percentile", "Earnings yield percentile"
    ),
    _registered("factor_percentiles.book_yield_percentile", "Book yield percentile"),
)

# None of these has a durable store behind it in v1 (spec 0003 §13.4): bank,
# developer and retail metrics are live quota-bound reads today, and the
# pipeline may not make one. They are named anyway and emitted `refused`.
INDUSTRY_FUNDAMENTAL_FIELDS: Mapping[AnalysisIndustry, tuple[ProfileField, ...]] = (
    MappingProxyType(
        {
            AnalysisIndustry.BANKS: (
                ProfileField(
                    "bank_metrics.nim_pct",
                    "Net interest margin",
                    "Net interest income over average earning assets, in percent.",
                ),
                ProfileField(
                    "bank_metrics.npl_ratio_pct",
                    "Non-performing loan ratio",
                    "Group 3-5 loans as a percentage of gross loans.",
                ),
                ProfileField(
                    "bank_metrics.llr_coverage_pct",
                    "Loan-loss coverage",
                    "Loan-loss reserves as a percentage of non-performing loans.",
                ),
            ),
            AnalysisIndustry.REAL_ESTATE: (
                ProfileField(
                    "developer_metrics.net_debt_to_ebitda",
                    "Net debt to EBITDA",
                    "Net interest-bearing debt over trailing EBITDA, as a ratio.",
                ),
                ProfileField(
                    "developer_metrics.inventory_share_of_assets_pct",
                    "Inventory share of assets",
                    "Property inventory as a percentage of total assets.",
                ),
            ),
            AnalysisIndustry.RETAIL: (
                ProfileField(
                    "retail_metrics.gross_margin_pct",
                    "Gross margin",
                    "Gross profit as a percentage of revenue.",
                ),
                ProfileField(
                    "retail_metrics.inventory_turnover_x",
                    "Inventory turnover",
                    "Cost of goods sold over average inventory, in turns.",
                ),
                ProfileField(
                    "retail_metrics.store_count",
                    "Store count",
                    "How many stores the chain operated at the period end.",
                ),
            ),
        }
    )
)

MONEY_FLOW_FIELDS: tuple[ProfileField, ...] = (
    _registered("foreign_flow_pressure.net_value_over_adtv", "Foreign flow pressure"),
    _registered(
        "foreign_flow_pressure.persistence_run_days", "Foreign flow persistence"
    ),
    _registered("liquidity_profile.adtv_vnd", "Average daily traded value"),
    _registered("company_profile.foreign_room_pct", "Foreign ownership room"),
)

# Approved-source counts, not headlines. V1 never asks the model to synthesise
# what a headline means, and until approved-source news is persisted these two
# have no inputs at all — so the whole News section is `refused/unavailable` and
# the pipeline does not call the live news service to fill it (spec 0003 §8.5).
NEWS_FIELDS: tuple[ProfileField, ...] = (
    ProfileField(
        "news_flow.approved_item_count_7_sessions",
        "Approved news items, 7 sessions",
        "How many approved-source news items mentioned this symbol over the "
        "last 7 Trading Days.",
    ),
    ProfileField(
        "news_flow.approved_item_count_30_sessions",
        "Approved news items, 30 sessions",
        "How many approved-source news items mentioned this symbol over the "
        "last 30 Trading Days.",
    ),
)


def _build(industry: AnalysisIndustry) -> Mapping[Axis, tuple[ProfileField, ...]]:
    return MappingProxyType(
        {
            Axis.TECHNICAL: TECHNICAL_FIELDS,
            Axis.FUNDAMENTAL: SHARED_FUNDAMENTAL_FIELDS
            + INDUSTRY_FUNDAMENTAL_FIELDS.get(industry, ()),
            Axis.MONEY_FLOW: MONEY_FLOW_FIELDS,
            Axis.NEWS: NEWS_FIELDS,
        }
    )


_PROFILES: Mapping[AnalysisIndustry, Mapping[Axis, tuple[ProfileField, ...]]] = (
    MappingProxyType({industry: _build(industry) for industry in AnalysisIndustry})
)


def profile_for(
    industry: AnalysisIndustry,
) -> Mapping[Axis, tuple[ProfileField, ...]]:
    """Every field this industry's Analysis carries, by axis and in axis order.

    Built once per industry at import, so two calls cannot disagree and no
    caller can be handed a list it is able to edit.
    """
    return _PROFILES[industry]


def _check_the_profile_holds() -> None:
    """Refuse to import a profile that breaks its own three rules.

    At import rather than in a test, for the reason every declaration in the
    signals package validates itself: a rule proven only by a test is a rule a
    new industry block can be written past in a branch that never ran it.
    """
    for industry, axes in _PROFILES.items():
        if tuple(axes) != AXIS_ORDER:
            raise ValueError(f"{industry.value} does not carry the four axes in order")
        named: list[str] = []
        for axis, fields in axes.items():
            if len(fields) > MAX_FIELDS_PER_AXIS:
                raise ValueError(
                    f"the {axis.value} axis names {len(fields)} fields for "
                    f"{industry.value}, past the cap of {MAX_FIELDS_PER_AXIS}"
                )
            named.extend(entry.field_id for entry in fields)
        if len(named) != len(set(named)):
            raise ValueError(f"{industry.value} names a field on two axes")
        if PRICE_ZONE_FIELD_ID in named:
            raise ValueError(
                f"{PRICE_ZONE_FIELD_ID} is core evidence and does not consume an "
                "axis slot"
            )

    if PRICE_ZONE_FIELD_ID not in REGISTRY:
        raise ValueError(
            f"{PRICE_ZONE_FIELD_ID} is the artifact's core evidence and has to be "
            "a registered field"
        )


_check_the_profile_holds()


__all__ = [
    "AXIS_ORDER",
    "FIELD_PROFILE_VERSION",
    "INDUSTRY_FUNDAMENTAL_FIELDS",
    "MAX_FIELDS_PER_AXIS",
    "MONEY_FLOW_FIELDS",
    "NEWS_FIELDS",
    "PRICE_ZONE_FIELD_ID",
    "SHARED_FUNDAMENTAL_FIELDS",
    "TECHNICAL_FIELDS",
    "AnalysisIndustry",
    "Axis",
    "ProfileField",
    "profile_for",
]

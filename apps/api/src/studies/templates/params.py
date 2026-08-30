"""What a model fills in, for every template, in one place.

Together rather than one per template module, because ``run_study`` holds a rule
across all of them: a key that appears in two templates has to mean the same
thing in both (``agent/tools/studies.py::_check_the_parameters_agree``). A
reader checking that rule against four files was checking it against four files.

Every window clamps rather than refuses. A model that asks for a year of
sessions has asked a sensible question with an unusable number, and one round
trip spent on "60 is the maximum" buys nothing a clamp plus an honest
``sessionsUsed`` does not already say.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Metric = Literal["volume", "value"]
Universe = Literal["market", "declared"]

#: The intraday window, in closed sessions.
SESSIONS_FLOOR = 10
SESSIONS_CEILING = 60

#: The 52-week band, which is also the shortest line worth drawing it against.
RANGE_SESSIONS = 250
HORIZON_FLOOR = RANGE_SESSIONS
HORIZON_CEILING = 500

#: How many sessions of a price ladder may be folded together, and into how many
#: rungs.
LADDER_SESSIONS_FLOOR = 1
LADDER_SESSIONS_CEILING = 5
BINS_FLOOR = 6
BINS_CEILING = 24

#: The screen's defaults and the width of its table.
DEFAULT_MIN_PROFIT_GROWTH_PCT = 20.0
DEFAULT_MAX_PRICE_CHANGE_PCT = 5.0
DEFAULT_TOP_N = 10
TOP_N_FLOOR = 1
TOP_N_CEILING = 20

#: How many sessions the price reaction is measured over.
REACTION_SESSIONS = 20

PERIOD_PATTERN = re.compile(r"^\d{4}-Q[1-4]$")


class LiquidityParams(BaseModel):
    """Which symbol, how many sessions, and shares or money."""

    symbol: str = Field(description="Mã chứng khoán trong Universe, vd STB")
    sessions: int = Field(
        default=30,
        description=(
            f"Số phiên gần nhất đã đóng, {SESSIONS_FLOOR}–{SESSIONS_CEILING}; "
            "ngoài khoảng sẽ được kẹp về biên"
        ),
    )
    metric: Metric = Field(
        default="volume",
        description="volume = số cổ phiếu, value = giá trị tiền theo giá đóng bucket",
    )

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("sessions")
    @classmethod
    def _clamp(cls, value: int) -> int:
        return max(SESSIONS_FLOOR, min(SESSIONS_CEILING, value))


class ConditionReviewParams(BaseModel):
    """Which symbol, and how long a price line to draw beside the band.

    The floor is the 52-week band itself — the horizon is what the line draws,
    and a line shorter than the band it is drawn against would leave the band's
    edges off the picture. The store's own reader caps a daily read at 250
    sessions (``agent/tools/query.py::MAX_WINDOW``), so a longer horizon draws
    250 and says so through ``sessionsUsed`` rather than through a refusal.
    """

    symbol: str = Field(description="Mã chứng khoán, vd STB")
    horizon_sessions: int = Field(
        default=RANGE_SESSIONS,
        description=(
            f"Số phiên đã đóng vẽ trên đường giá, {HORIZON_FLOOR}–"
            f"{HORIZON_CEILING}; ngoài khoảng sẽ được kẹp về biên. Dải 52 tuần, "
            "vùng tích luỹ và RSI luôn tính trên cửa sổ riêng của chúng."
        ),
    )

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("horizon_sessions")
    @classmethod
    def _clamp(cls, value: int) -> int:
        return max(HORIZON_FLOOR, min(HORIZON_CEILING, value))


class VolumeAtPriceParams(BaseModel):
    """Which symbol, how many sessions folded together, and how many rungs.

    ``price_sessions`` defaults to one because the question that reaches this
    template is almost always about a single session — *phiên hôm nay* — and a
    default of several would answer a different question without saying so.
    """

    symbol: str = Field(description="Mã chứng khoán trong Universe, vd VCB")
    price_sessions: int = Field(
        default=1,
        description=(
            f"Số phiên gần nhất gộp lại, {LADDER_SESSIONS_FLOOR}–"
            f"{LADDER_SESSIONS_CEILING}; mặc định 1, tức phiên gần nhất, kể cả "
            "phiên đang diễn ra. Ngoài khoảng sẽ được kẹp về biên."
        ),
    )
    bins: int = Field(
        default=BINS_CEILING,
        description=(
            f"Số mức giá tối đa vẽ trên thang, {BINS_FLOOR}–{BINS_CEILING}; "
            "thang dài hơn sẽ được gộp thành đúng chừng này vùng đều nhau"
        ),
    )

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("price_sessions")
    @classmethod
    def _clamp_sessions(cls, value: int) -> int:
        return max(LADDER_SESSIONS_FLOOR, min(LADDER_SESSIONS_CEILING, value))

    @field_validator("bins")
    @classmethod
    def _clamp_bins(cls, value: int) -> int:
        return max(BINS_FLOOR, min(BINS_CEILING, value))


class EarningsDislocationParams(BaseModel):
    """Which quarter, which thresholds, how many names, and how wide a net.

    ``period`` is optional because the answer to "which quarter has the market
    reported" is a fact about the store, and a model guessing at it would ask
    for a quarter half the market has not filed.
    """

    period: str | None = Field(
        default=None,
        description=(
            "Kỳ báo cáo dạng 2026-Q2. Bỏ trống để dùng quý gần nhất mà store đã "
            "có đủ báo cáo."
        ),
    )
    min_profit_growth_pct: float = Field(
        default=DEFAULT_MIN_PROFIT_GROWTH_PCT,
        description=(
            "Sàn tăng trưởng lợi nhuận sau thuế so với cùng kỳ năm trước, tính "
            "theo phần trăm"
        ),
    )
    max_price_change_pct: float = Field(
        default=DEFAULT_MAX_PRICE_CHANGE_PCT,
        description=(
            f"Trần lợi suất {REACTION_SESSIONS} phiên so với VN-Index, tính theo "
            "phần trăm; mã vượt trần là mã giá đã theo"
        ),
    )
    top_n: int = Field(
        default=DEFAULT_TOP_N,
        description=(
            f"Số mã trong bảng xếp hạng, {TOP_N_FLOOR}–{TOP_N_CEILING}; ngoài "
            "khoảng sẽ được kẹp về biên"
        ),
    )
    universe: Universe = Field(
        default="market",
        description=(
            "market = toàn bộ mã đang niêm yết, declared = 30 mã Universe khai báo"
        ),
    )

    @field_validator("period")
    @classmethod
    def _period_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().upper()
        if not PERIOD_PATTERN.match(text):
            raise ValueError("period must look like 2026-Q2")
        return text

    @field_validator("top_n")
    @classmethod
    def _clamp(cls, value: int) -> int:
        return max(TOP_N_FLOOR, min(TOP_N_CEILING, value))


__all__ = [
    "ConditionReviewParams",
    "EarningsDislocationParams",
    "LiquidityParams",
    "Metric",
    "Universe",
    "VolumeAtPriceParams",
]

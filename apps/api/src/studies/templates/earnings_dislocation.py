"""Which companies' quarterly profit jumped while their price has not followed.

The question a reader asks is *mã nào lợi nhuận tăng mạnh mà giá chưa phản
ánh?*, and it is a screen rather than a query: the answer is a distribution over
the whole market with a handful of names standing out of it. Four decisions make
the difference between a screen and a recommendation engine, and each of them is
load-bearing here.

**"Giá chưa tăng" is measured against the market, not against zero.** A quarter
in which every symbol fell 8% and this one fell 6% is not a symbol whose price
has not moved. So the price axis is the twenty-session return minus VN-Index's
return over the same span, and the raw return travels beside it in the ranking
so a reader can see both.

**The composite is named after what it measures.** ``dislocation_rank`` is the
growth percentile times the percentile of the *negated* relative return, taken
over the symbols this run could actually measure. It says "far apart on these
two axes within this sample" and nothing else — no target, no horizon, no view
on what a reader should do with it. The earlier name for a number of this shape
was "opportunity score", and a reader cannot help but read that as advice.

**Every symbol the screen dropped is counted and named.** A screener that
answers "12 mã" out of a market of 1.522 without saying what happened to the
other 1.510 is a screener nobody can check. Each symbol is counted at the first
gate it fails, in the fixed order of :data:`GATES`, so the exclusions plus the
survivors add up to the universe exactly.

**The liquidity floor is a gate, not a factor.** ``adtv ≥ 3 tỷ đồng/phiên``
removes what cannot be traded before any percentile is taken; as a multiplier it
would be a multiplication by one for everything that survived it, and the
percentiles would be ranks against a population including symbols nobody can
buy.

## What the data forced, measured 2026-08-27

**There is no traded-value column.** ``bar_daily`` carries ``open, high, low,
close, volume`` and nothing else, so the liquidity floor is the median of
``close × volume`` across the window. That is an approximation of traded value —
the real figure is matched price times matched quantity, bar by bar — and the
provenance says so rather than letting the number pass as turnover.

**There is no publication date.** The provider returns statements by period and
never says when a filing was released, so a window anchored to the release date
cannot be built from this store. The reaction window is therefore the last
:data:`REACTION_SESSIONS` closed sessions, which for a quarter's screen is
roughly the month after the filing season — and the provenance states the
limitation instead of implying a date nobody has.

**Price basis does not disturb the price axis.** Every ``bar_daily`` row is
``adjusted_at_source``; a return and a return-minus-index are ratios, so they
survive adjustment except on the one session an ex-date falls in the window. The
guard against a window that mixes bases is still here, and it is a guard: no row
in the store has ever carried a second basis.

**Survivorship is the current roster.** ``listing_roster`` is refreshed to now,
so a company delisted last year is absent from a screen of last year's quarter.
Reconstructing the roster as it stood at a past period is out of scope for this
version, and the provenance records it.

## What the port changed, and why the reads are reads

Three of the plan's steps read the store directly rather than through ``query``,
and each is a *fact about the store's shape* rather than a calculation:

*Which quarter to screen* is the newest one the store has filed widely enough,
which nothing but the store can answer. *A filer's own profit line* is resolved
per statement template (``financial/templates.py``) — a bank and an industrial
file different item ids for the same concept, and picking between them is
reading, not arithmetic. *A month of the whole market's closes* is a screen
wider than the query layer hands anybody: ``MAX_QUERY_ROWS`` is five thousand
and a market scope is fifteen hundred symbols across thirty sessions.

Everything after that is arithmetic and goes through the sandbox on the same
terms a model's ``compute`` call does — the gates, the returns, the median
traded value, the two percentiles, the composite, the quadrants, the thresholds
and the funnel counts. The regression fixture holds ``scatter``, ``ranking`` and
``filters`` equal to the cell.

The ``tiles`` frame is gone. It existed to feed a v1 ``stat_tiles`` block, and
the board's KPI strip is that block's replacement: the quarter, the symbols
screened, the symbols measured and the symbols matched are now four references
into frames a picture also draws.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta

from sqlalchemy import func, select

from src.stocks.financial import reads as financial_reads, templates
from src.stocks.financial.templates import Concept
from src.stocks.listing_roster import ListingRosterStore
from src.stocks.models import BarDaily, FinancialStatementLine
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.fields import PERCENTILE_ABSOLUTE_FLOOR
from src.stocks.signals.issues import SignalIssue

from ..contracts import (
    ComputeStep,
    Frame,
    Provenance,
    ReadStep,
    StudyContext,
    StudyDefinition,
    StudyRefused,
)
from ..reads_daily import (
    INDEX_SYMBOL,
    SERIES_EQUITY,
    SERIES_INDEX,
    SESSION_SETTLED_AT,
)
from ..registry import register
from .params import EarningsDislocationParams, REACTION_SESSIONS

NAME = "earnings_dislocation_screener"
VERSION = 2

#: The price reaction window, in closed sessions. A return over ``n`` sessions is
#: measured between ``n + 1`` closes, which is what :data:`WINDOW_CLOSES` is.
#: Twenty because that is about the month a quarter's filings land in, and fixed
#: rather than parameterised: two runs of this screen must not disagree about
#: what "giá chưa theo" was measured over. The twenty itself lives in
#: ``templates/params.py``, where the parameter description quotes it.
WINDOW_CLOSES = REACTION_SESSIONS + 1

#: How far back the market-wide price read reaches, in calendar days. Twenty-one
#: sessions is about thirty calendar days; the extra fortnight covers a Tết week
#: and the ordinary holidays without loading a quarter of the market's history
#: for a window of one month.
CALENDAR_LOOKBACK_DAYS = 45

#: The liquidity floor, in dong of median daily traded value. Three billion is
#: roughly what a retail-sized position can leave without moving the price, and
#: below it a "dislocation" is a symbol nobody traded rather than a symbol the
#: market has not repriced.
LIQUIDITY_FLOOR_VND = 3_000_000_000.0

#: How many ranked rows reach the model. The Signal Desk draws ``top_n``; the
#: headline is budgeted at roughly three hundred tokens, and ten rows of four
#: figures is already most of it.
HEADLINE_TOP = 10

#: How the default period is chosen. The newest quarter is always half-filed —
#: the market reports over weeks — so the default is the newest quarter holding
#: at least this share of what the store's fullest recent quarter holds. Measured
#: against the store rather than against the market: a scan still walking the
#: roster would otherwise make every quarter look empty.
PERIOD_COVERAGE_SHARE = 0.8
PERIODS_CONSIDERED = 8

#: Below this share of the universe carrying a filing for the period, the strip
#: says the screen is thinner than a screen of the market. The plan's own line:
#: a screener run over a store with sparse coverage reports a fact about the
#: store, and a reader has to be told which one they are looking at.
HEALTHY_FILING_COVERAGE = 0.85

#: How wide an answer the sandbox may hand back here. The model-facing ceiling is
#: five hundred rows, which is the right number for a calculation a person reads
#: and the wrong one for a screen: the market roster is over fifteen hundred
#: symbols and every one of them is a row of the funnel's arithmetic.
MAX_SCREEN_ROWS = 2_500

#: The gates, in the order every symbol meets them. A symbol is counted at the
#: first one it fails and never twice, which is what makes the exclusions plus
#: the survivors equal to the universe.
GATE_NO_FILING = "no_filing"
GATE_CONCEPT_UNKNOWN = "concept_unknown"
GATE_NO_PRIOR_FILING = "no_prior_filing"
GATE_PRIOR_CONCEPT_UNKNOWN = "prior_concept_unknown"
GATE_NON_POSITIVE_PROFIT = "non_positive_profit"
GATE_NON_POSITIVE_PRIOR_PROFIT = "non_positive_prior_profit"
GATE_INSUFFICIENT_PRICE_HISTORY = "insufficient_price_history"
GATE_PRICE_WINDOW_UNUSABLE = "price_window_unusable"
GATE_THIN_LIQUIDITY = "thin_liquidity"
GATE_BELOW_GROWTH_THRESHOLD = "below_growth_threshold"
GATE_ABOVE_PRICE_CHANGE = "above_price_change"

#: The gates a symbol has to pass to be *measurable*: after these it has both
#: coordinates and can be plotted, whatever the thresholds then say about it.
MEASUREMENT_GATES = (
    GATE_NO_FILING,
    GATE_CONCEPT_UNKNOWN,
    GATE_NO_PRIOR_FILING,
    GATE_PRIOR_CONCEPT_UNKNOWN,
    GATE_NON_POSITIVE_PROFIT,
    GATE_NON_POSITIVE_PRIOR_PROFIT,
    GATE_INSUFFICIENT_PRICE_HISTORY,
    GATE_PRICE_WINDOW_UNUSABLE,
    GATE_THIN_LIQUIDITY,
)

#: The two gates that are the reader's question rather than the store's limits.
THRESHOLD_GATES = (GATE_BELOW_GROWTH_THRESHOLD, GATE_ABOVE_PRICE_CHANGE)

GATES = MEASUREMENT_GATES + THRESHOLD_GATES

#: What the ladder's first row is called: everything the screen started from,
#: before any gate ran.
START_ROW_LABEL = "Tổng số mã xét"

#: What each gate removed, in the words a reader sees under the table. Every one
#: of them describes a state of the data or of the measurement — none of them
#: describes what the symbol is worth.
GATE_LABELS: Mapping[str, str] = {
    GATE_NO_FILING: "Chưa có báo cáo kỳ này",
    GATE_CONCEPT_UNKNOWN: "Báo cáo không có dòng lợi nhuận sau thuế",
    GATE_NO_PRIOR_FILING: "Chưa có báo cáo cùng kỳ năm trước",
    GATE_PRIOR_CONCEPT_UNKNOWN: "Báo cáo cùng kỳ không có dòng lợi nhuận",
    GATE_NON_POSITIVE_PROFIT: "Lợi nhuận kỳ này không dương",
    GATE_NON_POSITIVE_PRIOR_PROFIT: "Lợi nhuận cùng kỳ không dương",
    GATE_INSUFFICIENT_PRICE_HISTORY: "Không đủ phiên giá đã đóng trong cửa sổ",
    GATE_PRICE_WINDOW_UNUSABLE: "Cửa sổ giá không so được",
    GATE_THIN_LIQUIDITY: "Thanh khoản dưới sàn",
    GATE_BELOW_GROWTH_THRESHOLD: "Tăng trưởng lợi nhuận dưới ngưỡng",
    GATE_ABOVE_PRICE_CHANGE: "Giá đã tăng quá ngưỡng so với thị trường",
}

#: The four regions of the scatter, named for what is true in them. Descriptive
#: on purpose: a quadrant labelled "rất hấp dẫn" is a verdict drawn on a chart,
#: and the whole point of drawing two axes is that the reader compares them.
QUADRANT_HIGH_GROWTH_LOW_PRICE = "Tăng trưởng cao, giá chưa theo"
QUADRANT_HIGH_GROWTH_HIGH_PRICE = "Tăng trưởng cao, giá đã theo"
QUADRANT_LOW_GROWTH_LOW_PRICE = "Tăng trưởng thấp, giá giảm so với thị trường"
QUADRANT_LOW_GROWTH_HIGH_PRICE = "Tăng trưởng thấp, giá tăng so với thị trường"

#: Which group hue each region is drawn in. Four interchangeable colours rather
#: than a scale, because the four regions are not ordered: "tăng trưởng cao, giá
#: chưa theo" is not *more* of anything than the region beside it, and a ramp
#: from pale to dark would rank them on the reader's behalf. Assigned here so the
#: same region is the same colour in every run of this Study.
QUADRANT_ROLES: Mapping[str, str] = {
    QUADRANT_HIGH_GROWTH_LOW_PRICE: "category:1",
    QUADRANT_HIGH_GROWTH_HIGH_PRICE: "category:2",
    QUADRANT_LOW_GROWTH_LOW_PRICE: "category:3",
    QUADRANT_LOW_GROWTH_HIGH_PRICE: "category:4",
}

#: What the numbers are and are not, one limitation per sentence, in the words a
#: reader uses. Every clause here is a limit this Study cannot design away.
#:
#: They used to be joined onto the health reason and printed as a single line
#: above the picture, so somebody who wanted to know whether the scan covered the
#: market got five clauses of methodology instead, with the code name of the
#: ranking formula in the middle of it. Method is a second question and now has a
#: second field.
METHOD_NOTES = (
    "Thanh khoản ước bằng trung vị của giá đóng cửa nhân khối lượng mỗi phiên, "
    "vì nguồn dữ liệu không cung cấp giá trị giao dịch.",
    f"Phản ứng giá đo trên {REACTION_SESSIONS} phiên gần nhất, không tính từ "
    "ngày công bố báo cáo — nguồn dữ liệu không cho biết ngày công bố.",
    "Thứ hạng lệch pha ghép phân vị tăng trưởng lợi nhuận với phân vị lợi suất "
    "so với thị trường, đảo dấu, chỉ trên các mã qua sàn thanh khoản "
    f"{LIQUIDITY_FLOOR_VND / 1e9:.0f} tỷ đồng một phiên.",
    "Giá đã điều chỉnh cho sự kiện quyền; lợi suất là tỷ số nên không đổi, trừ "
    "đúng phiên giao dịch không hưởng quyền.",
    "Danh sách mã lấy theo niêm yết hiện hành, không dựng lại danh sách của quá "
    "khứ.",
)

#: Quarters the way a Vietnamese reader writes them, keyed by the code the
#: provider files them under.
_QUARTER_WORDS: Mapping[str, str] = {"1": "I", "2": "II", "3": "III", "4": "IV"}


# -- the universe, the period, and the three reads -------------------------


def _period_words(period: str) -> str:
    """``2026-Q2`` as *quý II/2026*, or unchanged where it is not that shape.

    The code is what the filings are keyed by and what the model asks for; it is
    not what a person calls a quarter. Left alone rather than guessed at when it
    does not parse, since a mangled date is worse than an unfamiliar one.
    """
    year, _, quarter = period.partition("-Q")
    word = _QUARTER_WORDS.get(quarter)
    return f"quý {word}/{year}" if word and year.isdigit() else period


def _count(value: int) -> str:
    """A count grouped the way Vietnamese groups one: 1.523, not 1,523."""
    return f"{value:,}".replace(",", ".")


def _prior_period(period: str) -> str:
    """The same quarter one year earlier, which is what a YoY reading needs."""
    year, quarter = period.split("-Q")
    return f"{int(year) - 1}-Q{quarter}"


def _default_period(context: StudyContext) -> str | None:
    """The newest quarter the store has filed widely enough to screen.

    Counted on the one line every gate below depends on rather than on any row
    of the period: a symbol whose balance sheet arrived and whose income
    statement did not is a symbol this screen cannot use, and counting it would
    make a quarter look ready before it is.

    Periods sort correctly as text (``2026-Q2`` > ``2026-Q1`` > ``2025-Q4``), so
    "newest" needs no parsing — the same property ``financial/reads.py`` rests on.
    """
    rows = context.session.execute(
        select(
            FinancialStatementLine.period,
            func.count(func.distinct(FinancialStatementLine.symbol)),
        )
        .where(
            FinancialStatementLine.statement == templates.NET_PROFIT_ITEM[0],
            FinancialStatementLine.item_id == templates.NET_PROFIT_ITEM[1],
            FinancialStatementLine.item_seq == financial_reads.PRIMARY_SEQ,
        )
        .group_by(FinancialStatementLine.period)
        .order_by(FinancialStatementLine.period.desc())
        .limit(PERIODS_CONSIDERED)
    ).all()
    if not rows:
        return None

    fullest = max(count for _, count in rows)
    # Newest first, and the fullest quarter satisfies its own share, so this
    # always answers.
    return next(
        period for period, count in rows if count >= PERIOD_COVERAGE_SHARE * fullest
    )


#: Where the quarter this run screens is kept once it has been resolved.
_PERIOD_MEMO = "earnings_dislocation.periods"


def _periods(context: StudyContext) -> tuple[str, str]:
    """The quarter this run screens and the year-ago quarter it compares against.

    Resolved once per run and kept in ``context.scratch``. Four steps need it,
    and asking the store four times is not only a grouped count paid four times:
    each statement is its own snapshot, so a quarterly scan committing between
    two of them would let the ``period`` frame name one quarter while ``filings``
    was read for another — a board whose heading and whose numbers describe
    different quarters, with nothing on it saying so.

    The memo is per run and dies with it, so it can never answer a later
    question from a store it had already stopped describing.
    """
    held = context.scratch.get(_PERIOD_MEMO)
    if held is not None:
        return held

    declared = context.params.period
    if declared:
        resolved = (declared, _prior_period(declared))
    else:
        period = _default_period(context)
        if period is None:
            raise StudyRefused(
                SignalIssue.FUNDAMENTAL_NOT_STORED,
                "the store holds no quarterly statement line, so there is no "
                "period to screen",
            )
        resolved = (period, _prior_period(period))

    context.scratch[_PERIOD_MEMO] = resolved
    return resolved


def _universe(context: StudyContext) -> tuple[str, ...]:
    """Which symbols the screen starts from, alphabetically.

    The market roster rather than the declared Universe by default: a screen
    over thirty names is a table, and the question this Study answers is which
    of the market's companies stand out.
    """
    if context.params.universe == "declared":
        return tuple(sorted(context.universe))
    return ListingRosterStore(context.session).listed_symbols()


def _read_period(context: StudyContext) -> tuple[Frame, Provenance]:
    """The quarter under screen, in the three spellings the rest of the run needs.

    A frame of one row rather than a constant, because the two consumers are the
    headline and the KPI strip, and both are held to the rule that every figure
    they carry came out of a cell.
    """
    period, prior = _periods(context)
    return (
        Frame(
            kind="table",
            columns=("period", "prior_period", "words"),
            rows=((period, prior, _period_words(period)),),
            unit=None,
            labels={
                "period": "Kỳ báo cáo",
                "prior_period": "Cùng kỳ năm trước",
                "words": "Kỳ",
            },
        ),
        Provenance(
            source="store",
            as_of=context.as_of,
            sessions_used=0,
            health="normal",
            reason=None,
            method_notes=(),
            query={"period": period, "prior_period": prior},
        ),
    )


def _read_filings(context: StudyContext) -> tuple[Frame, Provenance]:
    """Each symbol's profit for both quarters, resolved through its own template.

    The resolution is why this is a read the query layer cannot serve: a bank
    and an industrial file the same concept under different item ids, and
    ``financial/templates.py`` is the one place that decides which stored line
    answers "lợi nhuận sau thuế". A raw ``statement`` read would hand the
    sandbox item ids and ask it to guess.

    Two flags travel beside the two figures because the gates below distinguish
    four states a single ``None`` would collapse into one: a symbol with no
    filing at all, and a symbol whose filing arrived without the line.
    """
    period, prior = _periods(context)
    symbols = _universe(context)
    if not symbols:
        raise StudyRefused(
            SignalIssue.RANKING_UNAVAILABLE,
            f"the {context.params.universe} universe is empty, so there is "
            "nothing to screen",
        )

    current = financial_reads.concepts_for_period(
        context.session, period, symbols=symbols
    )
    previous = financial_reads.concepts_for_period(
        context.session, prior, symbols=symbols
    )

    rows: list[tuple[object, ...]] = []
    resolved = 0
    for symbol in symbols:
        now_filed = current.get(symbol)
        then_filed = previous.get(symbol)
        net = None if now_filed is None else now_filed[Concept.NET_PROFIT].value
        base = None if then_filed is None else then_filed[Concept.NET_PROFIT].value
        if net is not None:
            resolved += 1
        rows.append(
            (
                symbol,
                1 if now_filed is not None else 0,
                None if net is None else float(net),
                1 if then_filed is not None else 0,
                None if base is None else float(base),
            )
        )

    # Coverage counts the symbols whose profit line actually resolved, not the
    # ones with a row of some kind for the period: a balance sheet stored
    # without an income statement is a symbol this screen cannot use, and
    # counting it would make the store look readier than it is.
    coverage = resolved / len(symbols)
    healthy = coverage >= HEALTHY_FILING_COVERAGE
    return (
        Frame(
            kind="table",
            columns=(
                "symbol",
                "filed",
                "net_profit_vnd",
                "prior_filed",
                "prior_net_profit_vnd",
            ),
            rows=tuple(rows),
            unit=None,
            labels={
                "symbol": "Mã",
                "filed": "Có báo cáo kỳ này",
                "net_profit_vnd": "Lợi nhuận sau thuế kỳ này (VND)",
                "prior_filed": "Có báo cáo cùng kỳ",
                "prior_net_profit_vnd": "Lợi nhuận sau thuế cùng kỳ (VND)",
            },
        ),
        Provenance(
            source="store",
            as_of=context.as_of,
            sessions_used=0,
            health="normal" if healthy else "degraded",
            # One sentence, and only when there is something to say. A screen run
            # over a quarter half the market has not reported is a fact about the
            # coverage, and the count is what lets a reader weigh it.
            reason=(
                None
                if healthy
                else (
                    f"Mới có báo cáo {_period_words(period)} cho "
                    f"{_count(resolved)}/{_count(len(symbols))} mã"
                )
            ),
            # The whole Study's limitations hang here rather than being split
            # across the reads: they describe the screen, the merge that reaches
            # the artifact is a union, and this is the first step that has any.
            method_notes=METHOD_NOTES,
            query={
                "period": period,
                "prior_period": prior,
                "symbols": len(symbols),
                "resolved": resolved,
            },
        ),
    )


def _read_closes(context: StudyContext) -> tuple[Frame, Provenance]:
    """The market's recent closed sessions, plus VN-Index over the same span.

    One query for the whole universe. Per symbol it would be fifteen hundred
    round trips for a screen that has to answer inside a tool round, and the
    ``query`` layer's own ceiling is five thousand rows — a month of the market
    is some forty thousand. That width is the read privilege this template
    holds, and it is why the two scopes behave the same way.

    The closed-session rule is the same one every reader in this system keeps:
    today's half-finished session is excluded until the market has settled, so a
    twenty-session return does not change under the reader.

    The index travels in the same frame under its own ``series``, because the
    two are one read of one table and the relative return needs both. Splitting
    them costs a second round trip and a second cutoff rule to keep in step.
    """
    symbols = _universe(context)
    local = context.as_of.astimezone(VN_TZ)
    floor = local.date() - timedelta(days=CALENDAR_LOOKBACK_DAYS)

    def _window(statement):
        if local.time() < SESSION_SETTLED_AT:
            statement = statement.where(BarDaily.trading_day < local.date())
        return statement.where(BarDaily.trading_day >= floor)

    index_rows = context.session.execute(
        _window(
            select(BarDaily.trading_day, BarDaily.close, BarDaily.price_basis).where(
                BarDaily.series == SERIES_INDEX,
                BarDaily.symbol == INDEX_SYMBOL,
            )
        ).order_by(BarDaily.trading_day.asc())
    ).all()
    if len(index_rows) < WINDOW_CLOSES:
        # Without the index there is no relative return, and an absolute return
        # presented in its place would answer a different question than the one
        # asked.
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS,
            f"the store holds {len(index_rows)} closed {INDEX_SYMBOL} sessions "
            f"in the last {CALENDAR_LOOKBACK_DAYS} days, {WINDOW_CLOSES} needed "
            f"to measure a {REACTION_SESSIONS}-session return against the market",
        )

    rows: list[tuple[object, ...]] = [
        (SERIES_INDEX, INDEX_SYMBOL, day.isoformat(), float(close), 0, basis)
        for day, close, basis in index_rows
    ]
    equity_rows = context.session.execute(
        _window(
            select(
                BarDaily.symbol,
                BarDaily.trading_day,
                BarDaily.close,
                BarDaily.volume,
                BarDaily.price_basis,
            ).where(
                BarDaily.series == SERIES_EQUITY,
                BarDaily.symbol.in_(list(symbols)),
            )
        ).order_by(BarDaily.symbol.asc(), BarDaily.trading_day.asc())
    ).all()
    rows.extend(
        (SERIES_EQUITY, symbol, day.isoformat(), float(close), int(volume), basis)
        for symbol, day, close, volume, basis in equity_rows
    )

    return (
        Frame(
            kind="table",
            columns=("series", "symbol", "session", "close", "volume", "price_basis"),
            rows=tuple(rows),
            unit=None,
            labels={
                "series": "Nhóm",
                "symbol": "Mã",
                "session": "Phiên",
                "close": "Giá đóng cửa",
                "volume": "Khối lượng",
                "price_basis": "Cơ sở giá",
            },
        ),
        Provenance(
            source="store",
            as_of=context.as_of,
            # The window every return is measured over, rather than the calendar
            # span read to find it: the read reaches back far enough to hold a
            # month of sessions, and the measurement is these closes.
            sessions_used=WINDOW_CLOSES,
            health="normal",
            reason=None,
            method_notes=(),
            query={
                "symbols": len(symbols),
                "lookback_days": CALENDAR_LOOKBACK_DAYS,
                "index": INDEX_SYMBOL,
            },
        ),
    )


# -- the checks that end a run ---------------------------------------------


def _enough_to_rank(frame: Frame, context: StudyContext) -> None:
    """A percentile needs a sample, and this says so before one is taken.

    The floor is the absolute one the Signal Field pack uses
    (``signals/fields.py``) and not ``min_sample_for``: that function takes a
    share of the sample asked for, which assumes every member is expected to
    answer. Here exclusion is the screen's own product — most of a market of
    1.522 legitimately fails a liquidity floor — so a share of the roster would
    refuse every honest run.
    """
    position = frame.columns.index("gate")
    measurable = sum(1 for row in frame.rows if not row[position])
    if measurable < PERCENTILE_ABSOLUTE_FLOOR:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_CROSS_SECTION,
            f"{measurable} of {len(frame.rows)} symbols carry a "
            f"{_periods(context)[0]} filing, its year-ago comparison and a "
            f"{REACTION_SESSIONS}-session price window "
            f"above the liquidity floor; {PERCENTILE_ABSOLUTE_FLOOR} are needed "
            "before a percentile over them means anything",
        )


# -- what the sandbox is told -----------------------------------------------


def _screen_figures(context: StudyContext) -> dict[str, object]:
    return {
        "series_equity": SERIES_EQUITY,
        "series_index": SERIES_INDEX,
        "window_closes": WINDOW_CLOSES,
        "liquidity_floor_vnd": LIQUIDITY_FLOOR_VND,
        "gate_names": list(MEASUREMENT_GATES),
        "reaction_words": f"Lợi suất {REACTION_SESSIONS} phiên (%)",
        "relative_words": f"Lợi suất {REACTION_SESSIONS} phiên so VN-Index (%)",
        "index_words": f"VN-Index {REACTION_SESSIONS} phiên (%)",
    }


def _ranking_figures(context: StudyContext) -> dict[str, object]:
    return {
        "min_profit_growth_pct": context.params.min_profit_growth_pct,
        "max_price_change_pct": context.params.max_price_change_pct,
        "top_n": context.params.top_n,
        "gate_below_growth": GATE_BELOW_GROWTH_THRESHOLD,
        "gate_above_price": GATE_ABOVE_PRICE_CHANGE,
        "reaction_words": f"Lợi suất {REACTION_SESSIONS} phiên (%)",
        "relative_words": f"Lợi suất {REACTION_SESSIONS} phiên so VN-Index (%)",
        "index_words": f"VN-Index {REACTION_SESSIONS} phiên (%)",
    }


def _quadrant_figures(context: StudyContext) -> dict[str, object]:
    return {
        "quadrant_high_high": QUADRANT_HIGH_GROWTH_HIGH_PRICE,
        "quadrant_high_low": QUADRANT_HIGH_GROWTH_LOW_PRICE,
        "quadrant_low_high": QUADRANT_LOW_GROWTH_HIGH_PRICE,
        "quadrant_low_low": QUADRANT_LOW_GROWTH_LOW_PRICE,
        "quadrant_roles": dict(QUADRANT_ROLES),
        "relative_words": f"Lợi suất {REACTION_SESSIONS} phiên so VN-Index (%)",
    }


def _funnel_figures(context: StudyContext) -> dict[str, object]:
    """Every gate's row of the ladder, written out where the words belong.

    The requirement sentences carry the run's own thresholds and the quarter it
    screened, so they are built here — in Python, from parameters — rather than
    inside the calculation, which may not type a figure of any kind.
    """
    period, prior = _periods(context)
    params = context.params
    requirements = {
        GATE_NO_FILING: f"có báo cáo kỳ {period}",
        GATE_CONCEPT_UNKNOWN: "đọc được lợi nhuận sau thuế",
        GATE_NO_PRIOR_FILING: f"có báo cáo kỳ {prior}",
        GATE_PRIOR_CONCEPT_UNKNOWN: f"đọc được lợi nhuận sau thuế kỳ {prior}",
        GATE_NON_POSITIVE_PROFIT: "lợi nhuận kỳ này > 0",
        GATE_NON_POSITIVE_PRIOR_PROFIT: "lợi nhuận cùng kỳ > 0",
        GATE_INSUFFICIENT_PRICE_HISTORY: (
            f"≥ {WINDOW_CLOSES} phiên đã đóng trong {CALENDAR_LOOKBACK_DAYS} ngày"
        ),
        GATE_PRICE_WINDOW_UNUSABLE: (
            "cửa sổ giá cùng một cơ sở giá và so được với VN-Index"
        ),
        GATE_THIN_LIQUIDITY: (
            f"trung vị giá × khối lượng ≥ {LIQUIDITY_FLOOR_VND / 1e9:.0f} tỷ "
            "đồng/phiên"
        ),
        GATE_BELOW_GROWTH_THRESHOLD: (
            f"tăng trưởng ≥ {round(params.min_profit_growth_pct, 2)}%"
        ),
        GATE_ABOVE_PRICE_CHANGE: (
            f"lợi suất so VN-Index ≤ {round(params.max_price_change_pct, 2)}%"
        ),
    }
    return {
        "start_label": START_ROW_LABEL,
        "universe_words": (
            "toàn bộ mã đang niêm yết"
            if params.universe == "market"
            else "danh sách mã đã khai báo sẵn"
        ),
        # No gate token in the table. Every row already carries the gate's own
        # Vietnamese sentence, and the code beside it was this system's spelling
        # of the same thing — read by nobody, and printed to a person the moment
        # they opened "xem dạng bảng". It travels in the key column only, which
        # the calculation counts by and the frame never shows.
        "gate_table": [
            [gate, GATE_LABELS[gate], requirements[gate]] for gate in GATES
        ],
    }


# -- the calculations -------------------------------------------------------


#: One row per symbol in the universe: the gate it first failed, or both
#: coordinates and every input they were built from.
#:
#: Vectorised rather than walked, because the walk is fifteen hundred symbols
#: and the sandbox has five CPU seconds. The order of :data:`MEASUREMENT_GATES`
#: is the order of ``np.select``'s conditions, which is what charges a symbol to
#: the *first* gate it fails and never to two.
#:
#: The index close is taken *at or before* each end of the window rather than on
#: it: a symbol trades on a subset of the market's sessions, and the backward
#: search is the guard for the day that stops being true.
_SCREEN_CODE = """
bars = f1[f1["series"] == series_equity].sort_values(["symbol", "session"])
kept = bars.groupby("symbol", sort=False).tail(window_closes).copy()
kept["amount"] = kept["close"] * kept["volume"]
groups = kept.groupby("symbol", sort=True)
stats = pd.DataFrame(
    {
        "sessions": groups["session"].size(),
        "first_session": groups["session"].first(),
        "last_session": groups["session"].last(),
        "first_close": groups["close"].first(),
        "last_close": groups["close"].last(),
        "bases": groups["price_basis"].nunique(),
        "adtv_vnd": groups["amount"].median(),
    }
).reset_index()

index = f1[f1["series"] == series_index].sort_values("session")
index_days = index["session"].to_numpy()
index_closes = index["close"].to_numpy()
opened = np.searchsorted(index_days, stats["first_session"].to_numpy(), side="right") - 1
closed = np.searchsorted(index_days, stats["last_session"].to_numpy(), side="right") - 1
stats["index_first"] = np.where(
    opened >= 0, index_closes[np.clip(opened, 0, None)], np.nan
)
stats["index_last"] = np.where(
    closed >= 0, index_closes[np.clip(closed, 0, None)], np.nan
)

base = f0.merge(stats, on="symbol", how="left")
net = base["net_profit_vnd"].astype("float64")
prior = base["prior_net_profit_vnd"].astype("float64")
sessions = base["sessions"].fillna(0)
bases = base["bases"].fillna(0)
first_close = base["first_close"]
index_first = base["index_first"]

growth_pct = (net / prior - 1) * 100
return_pct = (base["last_close"] / first_close - 1) * 100
index_return_pct = (base["index_last"] / index_first - 1) * 100

gate = np.select(
    [
        base["filed"] < 1,
        net.isna(),
        base["prior_filed"] < 1,
        prior.isna(),
        net <= 0,
        prior <= 0,
        sessions < window_closes,
        (bases > 1)
        | (first_close <= 0)
        | index_first.isna()
        | base["index_last"].isna()
        | (index_first <= 0),
        base["adtv_vnd"] < liquidity_floor_vnd,
    ],
    gate_names,
    default="",
)

result = pd.DataFrame(
    {
        "symbol": base["symbol"],
        "gate": gate,
        "growth_pct": growth_pct,
        "return_pct": return_pct,
        "index_return_pct": index_return_pct,
        "rel_return_pct": return_pct - index_return_pct,
        "adtv_vnd": base["adtv_vnd"],
        "net_profit_vnd": net,
        "prior_net_profit_vnd": prior,
        "window_end": base["last_session"],
    }
)
result.attrs["labels"] = {
    "symbol": "Mã",
    "gate": "Cửa lọc đầu tiên không qua",
    "growth_pct": "Tăng trưởng lợi nhuận so cùng kỳ (%)",
    "return_pct": reaction_words,
    "index_return_pct": index_words,
    "rel_return_pct": relative_words,
    "adtv_vnd": "Trung vị giá × khối lượng (VND/phiên)",
    "net_profit_vnd": "Lợi nhuận sau thuế kỳ này (VND)",
    "prior_net_profit_vnd": "Lợi nhuận sau thuế cùng kỳ (VND)",
    "window_end": "Phiên cuối cửa sổ",
}
"""

#: Every measurable symbol's standing on both axes, the product of the two, and
#: which threshold it then failed.
#:
#: The sample is every measurable symbol rather than the ones that passed the
#: thresholds. A percentile taken over the survivors of a filter is a percentile
#: of a group the filter defined: the top name would sit at 100 in every run
#: whatever the market did.
#:
#: The price axis ranks the *negated* relative return, so the highest percentile
#: belongs to the symbol whose price has followed least. Ties count as below on
#: both axes, which is the convention ``signals/cross_sectional.percentile_of``
#: fixed for this system, and ``rank(method="max")`` is that convention: the
#: rank it gives a value is the count of the sample at or below it.
#:
#: The standing is scaled to a hundred and back rather than divided once, which
#: is what ``percentile_of`` does and is not the same arithmetic: ``100 * 157 /
#: 174 / 100`` and ``157 / 174`` differ in the last bit of the float, and a
#: composite built from the second orders two symbols of the market scope
#: opposite to the way the hand-written screen ordered them.
#:
#: The thresholds are read in the gates' declared order — growth first — so a
#: symbol failing both is counted once, under the first. That is what keeps the
#: ladder in ``filters`` an arithmetic that adds up.
#:
#: Sorted by the composite, then by symbol. The tie-break is alphabetical rather
#: than arbitrary because two symbols with identical percentiles have to come
#: back in the same order on every run over the same store.
_RANKED_CODE = """
measured = f0[f0["gate"] == ""].reset_index(drop=True)
sample = len(measured)
growth_standing = measured["growth_pct"].rank(method="max") * 100 / sample / 100
price_standing = (-measured["rel_return_pct"]).rank(method="max") * 100 / sample / 100
measured["growth_percentile"] = growth_standing
measured["rel_return_percentile"] = price_standing
measured["dislocation_rank"] = growth_standing * price_standing
measured["threshold_gate"] = np.select(
    [
        measured["growth_pct"] < min_profit_growth_pct,
        measured["rel_return_pct"] > max_price_change_pct,
    ],
    [gate_below_growth, gate_above_price],
    default="",
)
ordered = measured.sort_values(
    ["dislocation_rank", "symbol"], ascending=[False, True]
).reset_index(drop=True)
result = ordered[
    [
        "symbol",
        "dislocation_rank",
        "growth_pct",
        "net_profit_vnd",
        "prior_net_profit_vnd",
        "rel_return_pct",
        "return_pct",
        "index_return_pct",
        "adtv_vnd",
        "growth_percentile",
        "rel_return_percentile",
        "threshold_gate",
        "window_end",
    ]
]
result.attrs["labels"] = {
    "symbol": "Mã",
    "dislocation_rank": "Thứ hạng lệch pha",
    "growth_pct": "Tăng trưởng lợi nhuận so cùng kỳ (%)",
    "net_profit_vnd": "Lợi nhuận sau thuế kỳ này (VND)",
    "prior_net_profit_vnd": "Lợi nhuận sau thuế cùng kỳ (VND)",
    "rel_return_pct": relative_words,
    "return_pct": reaction_words,
    "index_return_pct": index_words,
    "adtv_vnd": "Trung vị giá × khối lượng (VND/phiên)",
    "growth_percentile": "Phân vị tăng trưởng",
    "rel_return_percentile": "Phân vị lợi suất tương đối đảo dấu",
    "threshold_gate": "Ngưỡng không qua",
    "window_end": "Phiên cuối cửa sổ",
}
"""

#: Every measurable symbol on the two axes, with the region it falls in.
#:
#: The whole cloud rather than the matches: the shape of the market is what
#: makes a handful of names outliers, and a scatter of the winners is a picture
#: with nothing to be far from. The dividers are the medians of what is plotted,
#: which is where the widget draws its reference lines; computed here as well so
#: the region a point is in travels with the point in the artifact rather than
#: being a thing only the browser knows.
#:
#: Rounded through Python's own ``round`` rather than ``Series.round``. The two
#: disagree on a value whose scaled form lands a hair either side of a half —
#: ``round(0.145, 2)`` is 0,15 and ``np.round`` gives 0,14 — and this frame is
#: held equal to the pre-port fixture to the cell.
_SCATTER_CODE = """
mid_growth = f0["growth_pct"].median()
mid_rel = f0["rel_return_pct"].median()
high_growth = f0["growth_pct"] >= mid_growth
high_rel = f0["rel_return_pct"] >= mid_rel
quadrant = np.select(
    [high_growth & high_rel, high_growth & ~high_rel, ~high_growth & high_rel],
    [quadrant_high_high, quadrant_high_low, quadrant_low_high],
    default=quadrant_low_low,
)
result = pd.DataFrame(
    {
        "symbol": f0["symbol"],
        "growth_pct": f0["growth_pct"].map(lambda value: round(value, 2)),
        "rel_return_pct": f0["rel_return_pct"].map(lambda value: round(value, 2)),
        "quadrant": quadrant,
    }
)
result.attrs["unit"] = "%"
result.attrs["point_roles"] = [quadrant_roles[name] for name in quadrant]
result.attrs["labels"] = {
    "symbol": "Mã",
    "growth_pct": "Tăng trưởng lợi nhuận so cùng kỳ (%)",
    "rel_return_pct": relative_words,
    "quadrant": "Vùng",
}
"""

#: The rows that passed both thresholds, down to the width the question asked
#: for, with every input the composite was built from.
#:
#: Twelve columns because a ranking whose score cannot be recomputed from the
#: row is a ranking a reader has to take on trust. Only the leading name is
#: marked: a top ten with three accents is a shortlist this Study does not draw.
_RANKING_CODE = """
matched = f0[f0["threshold_gate"] == ""].reset_index(drop=True)
top = matched.head(top_n).reset_index(drop=True)
built = pd.DataFrame(
    {
        "symbol": top["symbol"],
        "dislocation_rank": top["dislocation_rank"].map(lambda value: round(value, 4)),
        "growth_pct": top["growth_pct"].map(lambda value: round(value, 2)),
        "net_profit_vnd": top["net_profit_vnd"].round(),
        "prior_net_profit_vnd": top["prior_net_profit_vnd"].round(),
        "rel_return_pct": top["rel_return_pct"].map(lambda value: round(value, 2)),
        "return_pct": top["return_pct"].map(lambda value: round(value, 2)),
        "index_return_pct": top["index_return_pct"].map(lambda value: round(value, 2)),
        "adtv_vnd": top["adtv_vnd"].round(),
        "growth_percentile": top["growth_percentile"].map(
            lambda value: round(value, 4)
        ),
        "rel_return_percentile": top["rel_return_percentile"].map(
            lambda value: round(value, 4)
        ),
    }
)
built.insert(0, "rank", built.index + 1)
result = built
result.attrs["point_roles"] = [
    "focus" if position == 1 else None for position in result["rank"]
]
result.attrs["labels"] = {
    "rank": "Hạng",
    "symbol": "Mã",
    "dislocation_rank": "Thứ hạng lệch pha",
    "growth_pct": "Tăng trưởng lợi nhuận so cùng kỳ (%)",
    "net_profit_vnd": "Lợi nhuận sau thuế kỳ này (VND)",
    "prior_net_profit_vnd": "Lợi nhuận sau thuế cùng kỳ (VND)",
    "rel_return_pct": relative_words,
    "return_pct": reaction_words,
    "index_return_pct": index_words,
    "adtv_vnd": "Trung vị giá × khối lượng (VND/phiên)",
    "growth_percentile": "Phân vị tăng trưởng",
    "rel_return_percentile": "Phân vị lợi suất tương đối đảo dấu",
}
"""

#: The ladder: what each gate asked for, what it removed, what was left.
#:
#: Every gate appears, including the ones that removed nothing, because a reader
#: checking a screen needs to see that a gate ran — a row missing from this
#: table reads as a gate nobody applied. The counts come from the two frames the
#: gates were charged on, so the exclusions plus the survivors equal the
#: universe by construction rather than by a second count agreeing with a first.
_FILTERS_CODE = """
tally = {}
for name in f0["gate"]:
    if name:
        tally[name] = tally.get(name, 0) + 1
for name in f1["threshold_gate"]:
    if name:
        tally[name] = tally.get(name, 0) + 1

screened = len(f0)
remaining = screened
built = [[start_label, universe_words, 0, screened]]
for entry in gate_table:
    excluded = tally.get(entry[0], 0)
    remaining = remaining - excluded
    built.append([entry[1], entry[2], excluded, remaining])

result = pd.DataFrame(
    built, columns=["gate", "requirement", "excluded", "remaining"]
)
result.attrs["unit"] = "mã"
result.attrs["labels"] = {
    "gate": "Cửa lọc",
    "requirement": "Điều kiện",
    "excluded": "Số mã bị loại",
    "remaining": "Số mã còn lại",
}
"""


PLAN = (
    ReadStep(
        name="period",
        title="Kỳ báo cáo được quét",
        read=_read_period,
    ),
    ReadStep(
        name="filings",
        title="Lợi nhuận sau thuế hai kỳ",
        read=_read_filings,
    ),
    ReadStep(
        name="closes",
        title="Phiên giá đã đóng và VN-Index",
        read=_read_closes,
    ),
    ComputeStep(
        name="screen",
        title="Từng mã qua các cửa lọc",
        code=_SCREEN_CODE,
        inputs=("filings", "closes"),
        constants=_screen_figures,
        output_kind="table",
        max_rows=MAX_SCREEN_ROWS,
        check=_enough_to_rank,
    ),
    ComputeStep(
        name="ranked",
        title="Phân vị hai trục trên các mã đo được",
        code=_RANKED_CODE,
        inputs=("screen",),
        constants=_ranking_figures,
        output_kind="table",
        max_rows=MAX_SCREEN_ROWS,
        # Thirteen because the ranking a reader sees is twelve and this frame
        # carries the threshold each symbol failed beside them.
        max_columns=13,
    ),
    ComputeStep(
        name="scatter",
        title="Tăng trưởng và lợi suất tương đối",
        code=_SCATTER_CODE,
        inputs=("ranked",),
        constants=_quadrant_figures,
        output_kind="table",
        max_rows=MAX_SCREEN_ROWS,
    ),
    ComputeStep(
        name="ranking",
        title="Xếp hạng lệch pha",
        code=_RANKING_CODE,
        inputs=("ranked",),
        constants=_ranking_figures,
        output_kind="table",
    ),
    ComputeStep(
        name="filters",
        title="Các cửa lọc đã chạy",
        code=_FILTERS_CODE,
        inputs=("screen", "ranked"),
        constants=_funnel_figures,
        output_kind="table",
    ),
)


#: The ranking is the answer, the scatter is the evidence, the ladder is the
#: appendix.
#:
#: The old panel put the cloud above the list, on the argument that a top-ten
#: read alone is a recommendation. The board keeps the argument and inverts the
#: order, because the archetype is ``screen`` and a screen's first section is
#: the names: the scatter is a section of its own directly under it, so the ten
#: names are still read against the four hundred points before a reader leaves
#: the panel.
#:
#: The ladder stays, and it is not a footnote — it is the block that answers
#: "why is my symbol not here", which is the first question any screen gets. It
#: sits in the appendix because a plain table is the appendix's job and because
#: no chart of eleven gates says more than the eleven rows do.
BOARD = {
    "title": "Lợi nhuận tăng, giá chưa theo",
    "archetype": "screen",
    "kpis": [
        {
            "label": "Kỳ báo cáo",
            "value": {"frame_id": "period", "column": "words"},
        },
        {
            "label": "Số mã quét",
            "value": {
                "frame_id": "filters",
                "column": "remaining",
                "row_where": f"gate={START_ROW_LABEL}",
            },
        },
        {
            "label": "Đo được cả hai trục",
            "value": {
                "frame_id": "filters",
                "column": "remaining",
                # The last measurement gate's row: what is left after it is
                # exactly the sample the percentiles were taken over.
                "row_where": f"gate={GATE_LABELS[MEASUREMENT_GATES[-1]]}",
            },
        },
        {
            "label": "Qua cả hai ngưỡng",
            "value": {
                "frame_id": "filters",
                "column": "remaining",
                "row_where": f"gate={GATE_LABELS[THRESHOLD_GATES[-1]]}",
            },
            "role": "focus",
        },
    ],
    "sections": [
        {
            "heading": "Xếp hạng",
            "blocks": [
                {
                    "kind": "visual",
                    "frame_id": "ranking",
                    "widget": "ranked_bars",
                    "columns": ["symbol", "dislocation_rank"],
                }
            ],
        },
        {
            "heading": "Toàn bộ mã đo được",
            "blocks": [
                {
                    "kind": "visual",
                    "frame_id": "scatter",
                    "widget": "scatter_quadrant",
                    "columns": ["symbol", "growth_pct", "rel_return_pct"],
                }
            ],
        },
    ],
    "appendix_frame_id": "filters",
}


def headline(params, frames):
    """The three hundred tokens the model reads, out of the frames and nothing else.

    The exclusions are counted off the two frames the gates were charged on
    rather than off the ladder, because the ladder carries each gate's
    Vietnamese sentence and the model reads the gate's name. Zero reasons are
    left out; the whole ordered ladder, zeros included, is the frame a reader
    gets.
    """
    period = _rows(frames["period"])[0]
    screen = _rows(frames["screen"])
    ranked = _rows(frames["ranked"])
    ranking = _rows(frames["ranking"])

    tally: dict[str, int] = {}
    for row in screen:
        _charge(tally, row["gate"])
    for row in ranked:
        _charge(tally, row["threshold_gate"])

    return {
        "period": period["period"],
        "priorPeriod": period["prior_period"],
        "asOfSession": max(row["window_end"] for row in ranked),
        "screened": len(screen),
        # The population the percentiles were taken over, and the cloud the
        # scatter draws. Without it "afterFilters" is a count out of a universe
        # most of whose members were never measurable.
        "measured": len(ranked),
        "afterFilters": sum(1 for row in ranked if not row["threshold_gate"]),
        "excluded": {gate: tally[gate] for gate in GATES if tally.get(gate)},
        "top": [
            {
                "symbol": row["symbol"],
                "growthPct": row["growth_pct"],
                "relReturnPct": row["rel_return_pct"],
                "dislocationRank": row["dislocation_rank"],
            }
            for row in ranking[:HEADLINE_TOP]
        ],
    }


def _rows(frame: Mapping[str, object]) -> list[dict[str, object]]:
    columns = list(frame["columns"])  # type: ignore[arg-type]
    return [dict(zip(columns, row)) for row in frame["rows"]]  # type: ignore[arg-type]


def _charge(tally: dict[str, int], gate: object) -> None:
    if gate:
        name = str(gate)
        tally[name] = tally.get(name, 0) + 1


DEFINITION = register(
    StudyDefinition(
        name=NAME,
        version=VERSION,
        question=(
            "Mã nào có lợi nhuận quý tăng mạnh so với cùng kỳ mà giá "
            f"{REACTION_SESSIONS} phiên gần nhất chưa theo thị trường?"
        ),
        display_name="Lợi nhuận tăng, giá chưa theo",
        params_model=EarningsDislocationParams,
        # Nothing to warm. Every input is a market-wide store read: the filings
        # the quarterly scan writes and the daily bars the backfill writes. A
        # screen that fetched what it was missing would spend a tool round on
        # fifteen hundred provider calls, so a thin store is reported as a thin
        # store instead.
        requires=(),
        archetype="screen",
        plan=PLAN,
        board=BOARD,
        headline=headline,
    )
)


__all__ = [
    "BOARD",
    "CALENDAR_LOOKBACK_DAYS",
    "DEFINITION",
    "GATES",
    "GATE_ABOVE_PRICE_CHANGE",
    "GATE_BELOW_GROWTH_THRESHOLD",
    "GATE_CONCEPT_UNKNOWN",
    "GATE_INSUFFICIENT_PRICE_HISTORY",
    "GATE_LABELS",
    "GATE_NON_POSITIVE_PRIOR_PROFIT",
    "GATE_NON_POSITIVE_PROFIT",
    "GATE_NO_FILING",
    "GATE_NO_PRIOR_FILING",
    "GATE_PRICE_WINDOW_UNUSABLE",
    "GATE_PRIOR_CONCEPT_UNKNOWN",
    "GATE_THIN_LIQUIDITY",
    "HEADLINE_TOP",
    "HEALTHY_FILING_COVERAGE",
    "LIQUIDITY_FLOOR_VND",
    "MAX_SCREEN_ROWS",
    "MEASUREMENT_GATES",
    "METHOD_NOTES",
    "NAME",
    "PERIODS_CONSIDERED",
    "PERIOD_COVERAGE_SHARE",
    "PLAN",
    "QUADRANT_HIGH_GROWTH_HIGH_PRICE",
    "QUADRANT_HIGH_GROWTH_LOW_PRICE",
    "QUADRANT_LOW_GROWTH_HIGH_PRICE",
    "QUADRANT_LOW_GROWTH_LOW_PRICE",
    "QUADRANT_ROLES",
    "REACTION_SESSIONS",
    "START_ROW_LABEL",
    "THRESHOLD_GATES",
    "VERSION",
    "WINDOW_CLOSES",
    "headline",
]

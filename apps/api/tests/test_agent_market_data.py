"""What the market read refuses, what it normalises, and what a claim can cite.

The provider is never called here. Every test drives a fake frame whose *shape*
is the one the live probe of 2026-09-04 recorded — prices in thousands, daily
stamps at 07:00, intraday stamps at the bar's opening minute, one upstream
source that ignores the requested ``start``. The values are invented, because a
fixture holding a real quote would be a financial claim no test could source.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from src.agent.evidence.contracts import (
    ClaimKind,
    ClaimLedger,
    EvidenceKind,
    SourceClass,
    VerificationVerdict,
    VerifiedClaim,
    VerifierOutcome,
)
from src.agent.evidence.ledger import validate_claim_ledger
from src.agent.evidence.pipeline import LEDGER_VERSION, evidence_from_calls
from src.agent.evidence.source_policy import POLICY_VERSION
from src.agent.messages import ToolCallStatus, TurnToolCall
from src.agent.registry import ToolContext
from src.agent.tools import market_data
from src.core.config import Settings

NOW = datetime(2026, 9, 4, 17, 0, tzinfo=market_data.ICT)
CONTEXT = ToolContext(user_id=11, now=NOW)


class FakeFrame:
    """The two attributes this tool reads off a provider result."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records
        self.columns = list(records[0]) if records else []

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        assert orient == "records"
        return [dict(record) for record in self._records]


def daily(*days: int, price: float = 72.5, volume: int = 4_611_900) -> FakeFrame:
    """Daily bars stamped the way the provider stamps them: 07:00, naive."""
    return FakeFrame(
        [
            {
                "time": datetime(2026, 8, day, 7, 0),
                "open": price,
                "high": price + 0.2,
                "low": price - 1.1,
                "close": price - 1.1,
                "volume": volume,
            }
            for day in days
        ]
    )


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "deployment_profile": market_data.INTERNAL_PROFILE,
        "market_data_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


def tools_returning(frame: Any, **overrides: Any) -> market_data.MarketDataTools:
    tools = market_data.MarketDataTools(settings=settings(**overrides))
    # The package probe and the one provider operation, both replaced. Nothing
    # in these tests may reach a network.
    tools._package = True
    tools._history = lambda *_args, **_kwargs: frame  # type: ignore[method-assign]
    return tools


def read(
    tools: market_data.MarketDataTools,
    *,
    symbol: str = "FPT",
    start: str = "2026-08-24",
    end: str = "2026-08-28",
    interval: str = "1D",
    context: ToolContext = CONTEXT,
) -> Any:
    return tools.get_market_data(
        context,
        {"symbol": symbol, "start": start, "end": end, "interval": interval},
    )


# -- the request the model may make ---------------------------------------


def test_a_valid_range_comes_back_sorted_bounded_and_in_whole_dong():
    result = read(tools_returning(daily(24, 25, 26)))

    assert result["row_count"] == 3
    assert result["currency"] == "VND"
    assert result["price_scale_applied"] == market_data.PRICE_SCALE
    assert result["timezone"] == "Asia/Ho_Chi_Minh"
    # 72.5 thousand dong is 72,500 dong, and the answer that cites it says so.
    assert result["rows"][0]["open"] == 72_500
    assert [row["bar_closed_at"] for row in result["rows"]] == sorted(
        row["bar_closed_at"] for row in result["rows"]
    )
    # A daily bar is knowable when the session closes, not at the 07:00 the
    # provider stamps on it.
    assert result["rows"][0]["bar_closed_at"] == "2026-08-24T15:00:00+07:00"


def test_a_row_outside_the_requested_range_is_dropped_by_the_host():
    # One upstream source has been observed answering a five-day request with a
    # hundred rows. A caller that believed the argument would hand the model
    # ninety-five sessions nobody asked about.
    result = read(tools_returning(daily(3, 4, 24, 25)), start="2026-08-24")

    assert result["row_count"] == 2
    assert result["actual"]["start"].startswith("2026-08-24")


def test_a_bar_that_has_not_closed_yet_is_not_evidence():
    frame = daily(24, 25)
    frame._records[-1]["time"] = datetime(2026, 9, 4, 7, 0)

    result = read(tools_returning(frame), end="2026-09-04", context=ToolContext(
        user_id=11, now=datetime(2026, 9, 4, 11, 0, tzinfo=market_data.ICT)
    ))

    assert result["row_count"] == 1
    assert result["rows_dropped_after_horizon"] == 1
    assert result["quality"] == "partial"


def test_the_as_of_the_question_named_bounds_the_rows_too():
    result = read(
        tools_returning(daily(24, 25, 26, 27)),
        context=ToolContext(
            user_id=11,
            now=NOW,
            as_of=datetime(2026, 8, 25, 23, 59, tzinfo=market_data.ICT),
        ),
    )

    assert result["row_count"] == 2
    assert result["rows_dropped_after_horizon"] == 2


def test_an_intraday_bar_closes_at_its_own_width():
    frame = FakeFrame(
        [
            {
                "time": datetime(2026, 9, 3, 9, 15),
                "open": 73.0,
                "high": 73.0,
                "low": 72.5,
                "close": 72.9,
                "volume": 502_000,
            }
        ]
    )

    result = read(
        tools_returning(frame), start="2026-09-03", end="2026-09-03", interval="15m"
    )

    assert result["rows"][0]["bar_opened_at"] == "2026-09-03T09:15:00+07:00"
    assert result["rows"][0]["bar_closed_at"] == "2026-09-03T09:30:00+07:00"


def test_a_result_wider_than_the_row_cap_keeps_its_recent_end():
    frame = FakeFrame(
        [
            {
                "time": datetime(2026, 1, 5, 7, 0) + timedelta(days=index),
                "open": 70.0,
                "high": 70.5,
                "low": 69.5,
                "close": 70.1,
                "volume": 1_000_000,
            }
            for index in range(market_data.MAX_ROWS + 40)
        ]
    )

    result = read(
        tools_returning(frame),
        start="2026-01-05",
        end="2026-12-31",
        # Far enough past the window that no bar is still unfinished; this test
        # is about the row cap and not about the horizon.
        context=ToolContext(user_id=11, now=datetime(2027, 6, 1, tzinfo=market_data.ICT)),
    )

    assert result["row_count"] == market_data.MAX_ROWS
    assert result["truncated"] is True
    assert result["quality"] == "partial"


# -- the requests it refuses ----------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"start": "2026-08-28", "end": "2026-08-24"}, market_data.INVALID_REQUEST),
        ({"start": "28/08/2026"}, market_data.INVALID_REQUEST),
        ({"symbol": "not a symbol!"}, market_data.INVALID_REQUEST),
        ({"interval": "1s"}, market_data.INVALID_REQUEST),
        ({"start": "2020-01-01", "end": "2026-08-28"}, market_data.INVALID_REQUEST),
    ],
)
def test_a_malformed_request_is_refused_with_a_stable_code(arguments, code):
    tools = tools_returning(daily(24))

    with pytest.raises(market_data.MarketDataError) as raised:
        read(tools, **arguments)

    assert raised.value.code == code


def test_a_payload_missing_a_promised_column_fails_closed():
    frame = FakeFrame([{"time": datetime(2026, 8, 24, 7, 0), "open": 72.5}])

    with pytest.raises(market_data.MarketDataError) as raised:
        read(tools_returning(frame))

    assert raised.value.code == market_data.SCHEMA_DRIFT


def test_a_range_the_provider_has_no_rows_for_says_so_once():
    with pytest.raises(market_data.MarketDataError) as raised:
        read(tools_returning(FakeFrame([])))

    assert raised.value.code == market_data.NO_DATA


def test_the_provider_is_asked_for_one_day_past_the_range_it_was_given():
    """The provider's ``end`` is exclusive, so the last session asked for is
    only returned when the call reaches past it. Asking for a single day this
    way is what the provider answers with an error rather than that day."""
    tools = market_data.MarketDataTools(settings=settings())
    tools._package = True
    seen: dict[str, Any] = {}

    class Quote:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def history(self, **kwargs: Any) -> Any:
            seen.update(kwargs)
            return daily(28)

    monkey = market_data._import_vnstock
    try:
        market_data._import_vnstock = lambda: type(  # type: ignore[assignment]
            "Module", (), {"Quote": Quote}
        )
        tools._history(
            "FPT", date(2026, 8, 28), date(2026, 8, 28), "1D"
        )
    finally:
        market_data._import_vnstock = monkey  # type: ignore[assignment]

    assert seen["start"] == "2026-08-28"
    assert seen["end"] == "2026-08-29"


def test_a_provider_failure_becomes_this_tools_own_vocabulary():
    tools = market_data.MarketDataTools(settings=settings())
    tools._package = True

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("RetryError: HTTP 429 rate limit exceeded, upgrade your plan")

    tools._history = market_data.MarketDataTools._history.__get__(tools)  # type: ignore[method-assign]
    monkey = market_data._import_vnstock
    try:
        market_data._import_vnstock = lambda: type(  # type: ignore[assignment]
            "Module", (), {"Quote": staticmethod(explode)}
        )
        with pytest.raises(market_data.MarketDataError) as raised:
            read(tools)
    finally:
        market_data._import_vnstock = monkey  # type: ignore[assignment]

    assert raised.value.code == market_data.RATE_LIMITED
    # The provider's own sentence never reaches the model as if it were advice.
    assert "upgrade your plan" not in str(raised.value)


# -- who may have it at all -----------------------------------------------


def test_the_tool_is_unavailable_outside_the_internal_profile():
    tools = market_data.MarketDataTools(settings=settings(deployment_profile="production"))
    tools._package = True

    assert tools.available() is False


def test_the_tool_is_unavailable_when_the_flag_is_off():
    tools = market_data.MarketDataTools(settings=settings(market_data_enabled=False))
    tools._package = True

    assert tools.available() is False


def test_the_tool_is_unavailable_when_the_package_is_not_installed():
    tools = market_data.MarketDataTools(settings=settings())
    tools._package = False

    assert tools.available() is False


def test_a_disabled_deployment_refuses_the_call_and_not_only_the_schema():
    tools = market_data.MarketDataTools(settings=settings(deployment_profile="staging"))
    tools._package = True

    with pytest.raises(market_data.MarketDataError) as raised:
        read(tools)

    assert raised.value.code == market_data.PROVIDER_UNAVAILABLE


def test_no_credential_reaches_the_schema_or_the_result():
    tools = tools_returning(daily(24))
    entry = tools.entries()[0]
    serialised = repr(entry.schema) + repr(read(tools))

    for secret in ("api_key", "apikey", "token", "password", "secret"):
        assert secret not in serialised.casefold()


# -- what the ledger makes of it ------------------------------------------


def ledger_for(
    evidence: Any,
    text: str,
    proposed: VerificationVerdict = VerificationVerdict.SINGLE_SOURCE,
) -> ClaimLedger:
    """One material claim resting on one market read, and nothing else."""
    return ClaimLedger(
        version=LEDGER_VERSION,
        policy_version=POLICY_VERSION,
        as_of=NOW,
        evidence=evidence,
        claims=(
            VerifiedClaim(
                claim_id="c1",
                text=text,
                kind=ClaimKind.FACT,
                material=True,
                unit="đồng",
                currency="VND",
                # The model's own label. It carries no authority over the
                # verdict — the report recomputes that from the evidence — but
                # a label the recomputation disagrees with is itself an error,
                # so the default is the one a market-only claim can reach.
                verdict=proposed,
                supporting_evidence_ids=(evidence[0].evidence_id,),
                contradicting_evidence_ids=(),
            ),
        ),
        gaps=(),
        assumptions=("Không phải khuyến nghị cá nhân hóa.",),
        verifier_outcome=VerifierOutcome.VERIFIED,
    )


def market_call(result: Any) -> TurnToolCall:
    import json

    return TurnToolCall(
        id="call_1",
        name="get_market_data",
        arguments={},
        status=ToolCallStatus.OK,
        result_text=json.dumps(result, ensure_ascii=False),
    )


def test_a_market_read_becomes_one_store_figure_with_a_publication_time():
    result = read(tools_returning(daily(24, 25, 26)))

    evidence = evidence_from_calls([market_call(result)])

    assert len(evidence) == 1
    item = evidence[0]
    assert item.kind is EvidenceKind.STORE_FIGURE
    assert item.source_class is SourceClass.STORE
    # Without this, every material claim resting on it is TEMPORALLY_INVALID.
    assert item.published_at is not None
    assert item.publisher == market_data.PUBLISHER
    # The figures are in the excerpt in the unit a claim would write them in,
    # which is what `_numbers_supported` reads.
    assert "72.500 đồng" in item.excerpt


def test_a_material_claim_on_market_numbers_settles_at_single_source():
    result = read(tools_returning(daily(24, 25, 26)))
    evidence = evidence_from_calls([market_call(result)])

    # No bare date in the claim: see the test below for why one would sink it.
    ledger = ledger_for(evidence, "FPT mở cửa ở 72.500 đồng.")

    report = validate_claim_ledger(ledger)
    assessment = report.claims[0]

    # Not UNSUPPORTED — the number is in the excerpt with its unit and the bar
    # close is a publication time. Not VERIFIED either, and deliberately: the
    # figure came from a securities company's feed, so one feed is one source.
    assert assessment.accepted_verdict is VerificationVerdict.SINGLE_SOURCE
    assert assessment.numeric_failures == ()
    assert report.valid is True


def test_claiming_verified_on_market_numbers_alone_invalidates_the_ledger():
    """The other half of the same rule, and the one the model has to be told.

    The host recomputing ``SINGLE_SOURCE`` is not enough on its own: a model
    that labelled the claim ``VERIFIED`` is recorded as disagreeing with policy,
    and that disagreement invalidates the whole report rather than being
    quietly corrected. So the Signal Desk planning note has to say what a
    market-only claim may be labelled.
    """
    result = read(tools_returning(daily(24, 25, 26)))
    evidence = evidence_from_calls([market_call(result)])

    report = validate_claim_ledger(
        ledger_for(evidence, "FPT mở cửa ở 72.500 đồng.", VerificationVerdict.VERIFIED)
    )

    assert report.valid is False
    assert "verdict_not_supported_by_policy" in report.claims[0].errors


def test_a_number_no_bar_reports_is_refused_by_the_ledger():
    result = read(tools_returning(daily(24, 25, 26)))
    evidence = evidence_from_calls([market_call(result)])

    ledger = ledger_for(evidence, "FPT mở cửa ở 81.300 đồng.")

    assessment = validate_claim_ledger(ledger).claims[0]

    assert assessment.accepted_verdict is VerificationVerdict.UNSUPPORTED
    assert assessment.numeric_failures != ()


def test_a_date_written_into_a_claim_no_longer_sinks_it():
    """The numeric rule is about quantities, and a calendar date is not one.

    ``numbers.occurrences`` reads ``24/08/2026`` as the numbers 24, 8 and 2026,
    and ``contains`` accepts a value under three significant digits only where
    the claim's unit is printed beside it — no excerpt prints "đồng" after a day
    number. Read that way every dated fact in an answer was refused, which is
    how the concrete sentences ended up in the unverified list while only the
    vague ones survived. The date is stripped before the figures are read; when
    a date is wrong it is wrong about time, which the temporal gate decides.
    """
    result = read(tools_returning(daily(24, 25, 26)))
    evidence = evidence_from_calls([market_call(result)])

    ledger = ledger_for(evidence, "FPT mở phiên 24/08/2026 ở 72.500 đồng.")
    assessment = validate_claim_ledger(ledger).claims[0]

    assert assessment.accepted_verdict is VerificationVerdict.SINGLE_SOURCE
    assert assessment.numeric_failures == ()


def test_a_figure_the_excerpt_does_not_print_still_sinks_the_claim():
    """The rule the date carve-out must not have loosened: a figure still has to
    be printed in the evidence, digit for digit, and a rounded one is not."""
    result = read(tools_returning(daily(24, 25, 26)))
    evidence = evidence_from_calls([market_call(result)])

    ledger = ledger_for(evidence, "FPT khớp 4,61 triệu cổ phiếu phiên 24/08/2026.")
    assessment = validate_claim_ledger(ledger).claims[0]

    assert assessment.accepted_verdict is VerificationVerdict.UNSUPPORTED
    assert assessment.numeric_failures != ()


def test_a_failed_market_call_produces_no_evidence():
    call = TurnToolCall(
        id="call_1",
        name="get_market_data",
        arguments={},
        status=ToolCallStatus.ERROR,
        result_text="invalid_request: start must not be after end",
    )

    assert evidence_from_calls([call]) == ()


def test_the_declared_result_cap_is_wide_enough_for_a_full_result():
    import json

    result = read(tools_returning(daily(*range(3, 29))))
    entry = tools_returning(daily(24)).entries()[0]

    assert len(json.dumps(result, ensure_ascii=False)) <= entry.max_result_size_chars


# -- the window the host picks, and what leads the result -------------------


def test_no_dates_means_the_host_reads_the_three_months_ending_today():
    """A question about now cannot start in the model's remembered year."""
    seen: dict[str, Any] = {}
    tools = tools_returning(daily(24, 25, 26))

    def history(symbol: str, start: date, end: date, interval: str) -> FakeFrame:
        seen.update(start=start, end=end, interval=interval)
        return daily(24, 25, 26)

    tools._history = history  # type: ignore[method-assign]
    result = tools.get_market_data(CONTEXT, {"symbol": "FPT", "start": None, "end": ""})

    assert seen["end"] == NOW.date()
    assert seen["start"] == NOW.date() - timedelta(days=market_data.DEFAULT_SPAN_DAYS["1D"])
    assert seen["interval"] == "1D"
    assert result["date_note"] is None


def test_the_latest_session_leads_the_payload_and_the_excerpt():
    frame = FakeFrame(
        [
            {"time": datetime(2026, 8, 27, 7, 0), "open": 70, "high": 71, "low": 69, "close": 70, "volume": 100},
            {"time": datetime(2026, 8, 28, 7, 0), "open": 70, "high": 72, "low": 70, "close": 71.4, "volume": 2_500},
        ]
    )
    result = read(tools_returning(frame), start="2026-08-20", end="2026-09-04")

    latest = result["latest"]
    assert latest["session_date"] == "2026-08-28"
    assert latest["close"] == 71_400
    assert latest["previous_close"] == 70_000
    assert latest["change"] == 1_400
    assert latest["change_pct"] == 2.0
    # 4 September had no bar yet at 17:00 in this fixture: today is not a session.
    assert latest["session_today"] is False
    lines = result["excerpt"].splitlines()
    assert "PHIÊN GẦN NHẤT 28/08/2026" in lines[1]
    assert "đóng 71.400 đồng" in lines[1]
    assert "thay đổi +1.400 đồng (+2,00%)" in lines[1]
    assert "chưa có phiên đóng cửa" in lines[1]


def test_a_window_ending_long_before_today_says_what_today_is():
    result = read(tools_returning(daily(24, 25, 26)), start="2026-08-01", end="2026-08-26")

    assert result["date_note"].startswith("Hôm nay là 04/09/2026")
    assert result["excerpt"].splitlines()[1].startswith("LƯU Ý: Hôm nay là 04/09/2026")


def test_a_window_ending_inside_the_last_week_carries_no_note():
    result = read(tools_returning(daily(24, 25, 26)), start="2026-08-20", end="2026-08-28")

    assert result["date_note"] is None


def test_an_index_is_read_in_points_and_never_scaled_like_a_price():
    frame = FakeFrame(
        [
            {"time": datetime(2026, 8, 27, 7, 0), "open": 1775.09, "high": 1790, "low": 1770, "close": 1775.09, "volume": 500_000_000},
            {"time": datetime(2026, 8, 28, 7, 0), "open": 1776, "high": 1790.5, "low": 1771.2, "close": 1785.11, "volume": 624_262_395},
        ]
    )
    result = read(tools_returning(frame), symbol="VNINDEX", start="2026-08-20", end="2026-09-04")

    assert market_data.is_index("VNINDEX") and market_data.is_index("VN30")
    assert not market_data.is_index("STB")
    assert result["rows"][-1]["close"] == 1785.11
    assert result["price_unit"] == "điểm"
    assert result["price_scale_applied"] == 1
    lines = result["excerpt"].splitlines()
    assert "đơn vị điểm" in lines[0]
    assert "đóng 1.785,11 điểm" in lines[1]
    assert "thay đổi +10,02 điểm (+0,56%)" in lines[1]
    assert "đồng" not in result["excerpt"]


def test_a_repeated_read_is_served_from_memory_and_keeps_its_fetch_time() -> None:
    tools = tools_returning(daily(24, 25, 26, 27, 28))
    asked: list[tuple[Any, ...]] = []
    frame = tools._history
    tools._history = lambda *args, **kwargs: asked.append(args) or frame(*args, **kwargs)  # type: ignore[method-assign]

    first = read(tools)
    later = ToolContext(user_id=11, now=NOW + timedelta(minutes=30))
    second = read(tools, context=later)
    other = read(tools, symbol="VNM", context=later)

    assert len(asked) == 2  # FPT once, VNM once
    assert second["rows"] == first["rows"]
    # The bars were sent when the first call ran, not when the second read them.
    assert second["retrieved_at"] == first["retrieved_at"] == NOW.isoformat()
    assert other["retrieved_at"] == later.now.isoformat()

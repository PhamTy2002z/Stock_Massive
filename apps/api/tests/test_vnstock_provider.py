"""Tests for the vnstock reference and fundamental adapters.

Every frame here mirrors a shape measured against the live VCI provider, so the
normalization is exercised without touching the network. The numbers are HPG's
2026-Q2 figures, kept whole rather than rounded: a unit slip is the failure
these adapters exist to prevent, and it only shows up at full scale.
"""

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    Capability,
    PriceBasis,
    ProviderSource,
    ShareType,
    main_source,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.providers.vnstock_provider import (
    VnstockCorporateActionProvider,
    VnstockFundamentalProvider,
    VnstockMarketHistoryProvider,
    VnstockListingRosterProvider,
    VnstockProviderError,
    VnstockReadFailed,
    VnstockReferenceProvider,
)
from src.stocks.shared import StockServiceError


NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


class FakeListing:
    def symbols_by_industries(self):
        return pd.DataFrame(
            [
                {"symbol": "AAA", "industry_code": "10", "industry_name": "Banks"},
                {"symbol": "BBB", "industry_code": "20", "industry_name": "Retail"},
            ]
        )

    def symbols_by_exchange(self, exchange: str):
        if exchange == "HOSE":
            return pd.DataFrame(
                [
                    {
                        "symbol": "AAA",
                        "type": "STOCK",
                        "organ_short_name": "AAA Bank",
                    }
                ]
            )
        if exchange == "HNX":
            return pd.DataFrame(
                [
                    {
                        "symbol": "BBB",
                        "type": "STOCK",
                        "organ_short_name": "BBB Retail",
                    }
                ]
            )
        return pd.DataFrame(
            [{"symbol": "CW1", "type": "CW", "organ_short_name": "Not equity"}]
        )


def test_listing_roster_carries_icb_into_the_durable_contract():
    provider = VnstockListingRosterProvider(listing_factory=lambda _source: FakeListing())

    entries = provider.fetch_listing_roster()

    assert [(entry.symbol, entry.industry_code) for entry in entries] == [
        ("AAA", "10"),
        ("BBB", "20"),
    ]


def price_board(rows: list[dict]) -> pd.DataFrame:
    """The columns of a flattened VCI price board this adapter reads."""
    return pd.DataFrame(rows)


def hpg_board_row(**overrides) -> dict:
    row = {
        "symbol": "HPG",
        "listed_share": 8_442_964_520,
        "current_room": 2_299_133_934,
        "total_room": 4_137_052_614,
    }
    row.update(overrides)
    return row


class FakeTrading:
    """Stands in for ``Trading(source=...)``, recording what was asked for."""

    def __init__(self, frame: pd.DataFrame | Exception):
        self.frame = frame
        self.calls: list[list[str]] = []

    def price_board(self, symbols_list, **kwargs):
        self.calls.append(list(symbols_list))
        if isinstance(self.frame, Exception):
            raise self.frame
        return self.frame


class FakeQuote:
    """Stands in for ``Quote(symbol=..., source=...)``, recording its windows."""

    def __init__(self, frame: pd.DataFrame | Exception):
        self.frame = frame
        self.windows: list[tuple[str, str, str]] = []

    def history(self, start, end, interval="1D", **kwargs):
        self.windows.append((start, end, interval))
        if isinstance(self.frame, Exception):
            raise self.frame
        return self.frame


def history_frame(rows: list[dict]) -> pd.DataFrame:
    """The columns a VCI quote history comes back with, prices in thousands."""
    return pd.DataFrame(rows)


def hpg_history() -> pd.DataFrame:
    return history_frame(
        [
            {
                "time": "2018-03-01",
                "open": 21.9,
                "high": 22.1,
                "low": 21.8,
                "close": 21.85,
                "volume": 20_000_000,
            },
            {
                "time": "2018-03-02",
                "open": 22.35,
                "high": 22.6,
                "low": 21.95,
                "close": 22.0,
                "volume": 28_003_806,
            },
        ]
    )


def history_provider(quote: FakeQuote) -> VnstockMarketHistoryProvider:
    return VnstockMarketHistoryProvider(
        quote_factory=lambda symbol, source: quote,
        now=lambda: NOW,
    )


class TestMarketHistoryNormalization:
    def test_a_session_becomes_a_market_snapshot_in_plain_vnd(self):
        """Quote history quotes thousands of VND while the price board quotes
        plain VND. Normalizing here is what keeps a chart drawn across the two
        sources from stepping by a factor of a thousand at the seam."""
        provider = history_provider(FakeQuote(hpg_history()))

        snapshots = provider.fetch_market_history(
            "hpg", date(2018, 3, 1), date(2018, 3, 2)
        )

        assert [snapshot.symbol for snapshot in snapshots] == ["HPG", "HPG"]
        latest = snapshots[-1]
        assert latest.open_price == 22_350
        assert latest.high_price == 22_600
        assert latest.low_price == 21_950
        assert latest.last_price == 22_000
        assert latest.volume == 28_003_806
        assert latest.metadata.source is ProviderSource.VNSTOCK

    def test_every_session_says_the_provider_had_already_adjusted_it(self):
        """The Cover Source era declares itself, so it can be refused later.

        There is no raw option on this endpoint: what comes back was rescaled
        for every corporate action up to ``observed_at``, and that basis cannot
        be recomputed from what is stored. A window lying wholly here is refused
        for that reason rather than for being mixed — which only works if the
        rows say which era they belong to (``docs/adr/0006``).
        """
        provider = history_provider(FakeQuote(hpg_history()))

        snapshots = provider.fetch_market_history(
            "HPG", date(2018, 3, 1), date(2018, 3, 2)
        )

        assert [snapshot.price_basis for snapshot in snapshots] == [
            PriceBasis.ADJUSTED_AT_SOURCE
        ] * 2
        assert all(
            snapshot.metadata.schema_version == MARKET_SCHEMA_VERSION
            for snapshot in snapshots
        )

    def test_a_session_is_dated_by_the_session_rather_than_by_the_read(self):
        provider = history_provider(FakeQuote(hpg_history()))

        snapshots = provider.fetch_market_history(
            "HPG", date(2018, 3, 1), date(2018, 3, 2)
        )

        assert snapshots[0].metadata.effective_at == datetime(
            2018, 3, 1, tzinfo=VN_TZ
        )
        assert snapshots[0].metadata.observed_at == NOW

    def test_the_change_is_measured_against_the_session_before_it(self):
        """Only where that session is in the same answer. The first row of a
        window has no predecessor here, and inventing one from the row itself
        would report every chunk boundary as a flat day."""
        provider = history_provider(FakeQuote(hpg_history()))

        first, second = provider.fetch_market_history(
            "HPG", date(2018, 3, 1), date(2018, 3, 2)
        )

        assert first.reference_price is None
        assert first.change_pct is None
        assert second.reference_price == 21_850
        assert second.change_pct == pytest.approx(0.686, abs=0.001)

    def test_a_session_with_no_close_is_left_out_rather_than_zeroed(self):
        provider = history_provider(
            FakeQuote(
                history_frame(
                    [
                        {
                            "time": "2018-03-01",
                            "open": None,
                            "high": None,
                            "low": None,
                            "close": None,
                            "volume": 0,
                        }
                    ]
                )
            )
        )

        assert provider.fetch_market_history("HPG", date(2018, 3, 1), date(2018, 3, 1)) == ()

    def test_an_empty_history_is_a_symbol_with_no_sessions_not_an_error(self):
        """A window before a company listed is genuinely empty, and a backfill
        walks straight through those years."""
        provider = history_provider(FakeQuote(history_frame([])))

        assert provider.fetch_market_history("HPG", date(2001, 1, 1), date(2001, 12, 31)) == ()

    def test_a_backwards_window_is_refused_before_the_provider_is_called(self):
        quote = FakeQuote(hpg_history())
        provider = history_provider(quote)

        with pytest.raises(ValueError):
            provider.fetch_market_history("HPG", date(2018, 3, 2), date(2018, 3, 1))
        assert quote.windows == []

    def test_upstream_failure_text_never_reaches_the_caller(self):
        provider = history_provider(FakeQuote(RuntimeError("VCI said no")))

        with pytest.raises(VnstockReadFailed) as raised:
            provider.fetch_market_history("HPG", date(2018, 3, 1), date(2018, 3, 2))
        assert "VCI said no" not in str(raised.value)


def reference_provider(trading: FakeTrading) -> VnstockReferenceProvider:
    return VnstockReferenceProvider(
        trading_factory=lambda source: trading,
        now=lambda: NOW,
    )


class TestReferenceNormalization:
    def test_one_symbol_yields_a_reference_snapshot(self):
        provider = reference_provider(FakeTrading(price_board([hpg_board_row()])))

        (snapshot,) = provider.fetch_reference(["HPG"])

        assert snapshot.symbol == "HPG"
        assert snapshot.current_foreign_room == 2_299_133_934
        assert snapshot.total_foreign_room == 4_137_052_614
        assert snapshot.metadata.source is ProviderSource.VNSTOCK
        assert snapshot.metadata.observed_at == NOW

    def test_the_board_is_dated_by_the_session_it_was_read_in(self):
        """The board carries no period of its own, so the session it was read in
        is the only honest date for it. Stamping it with the minute instead
        would make every re-run of a cycle a fresh Snapshot of facts that have
        not changed — and re-running after a bad day is the operator's normal
        repair, not an event worth a second Snapshot."""
        provider = reference_provider(FakeTrading(price_board([hpg_board_row()])))

        (snapshot,) = provider.fetch_reference(["HPG"])

        assert snapshot.metadata.effective_at == datetime(
            2026, 8, 7, 0, 0, tzinfo=VN_TZ
        )

    def test_the_share_count_keeps_the_meaning_the_provider_gave_it(self):
        """VCI publishes a listed count, so it is stored as listed.

        Nothing converts it into an outstanding count. The two differ by
        treasury shares, and a snapshot that quietly relabels one as the other
        makes every per-share number computed from it wrong by that gap.
        """
        provider = reference_provider(FakeTrading(price_board([hpg_board_row()])))

        (snapshot,) = provider.fetch_reference(["HPG"])

        assert len(snapshot.shares) == 1
        (shares,) = snapshot.shares
        assert shares.share_type is ShareType.LISTED
        assert shares.value == 8_442_964_520

    def test_the_listed_count_is_what_canonical_shares_falls_back_to(self):
        """No outstanding count exists, so the contract's preference falls through.

        VCI publishes no trustworthy outstanding figure — its ``ratio_summary``
        still answers with 2018 counts — so this capability carries listed only,
        and consumers of ``canonical_shares`` get listed shares by design rather
        than by accident.
        """
        provider = reference_provider(FakeTrading(price_board([hpg_board_row()])))

        (snapshot,) = provider.fetch_reference(["HPG"])

        canonical = snapshot.canonical_shares()
        assert canonical.share_type is ShareType.LISTED
        assert canonical.value == 8_442_964_520

    def test_symbols_are_normalized_before_the_board_is_asked(self):
        trading = FakeTrading(price_board([hpg_board_row()]))
        provider = reference_provider(trading)

        provider.fetch_reference([" hpg "])

        assert trading.calls == [["HPG"]]

    def test_a_malformed_symbol_is_refused_before_any_call(self):
        trading = FakeTrading(price_board([hpg_board_row()]))
        provider = reference_provider(trading)

        with pytest.raises(StockServiceError):
            provider.fetch_reference(["VN-INDEX"])

        assert trading.calls == []

    def test_an_empty_request_asks_the_provider_for_nothing(self):
        trading = FakeTrading(price_board([hpg_board_row()]))
        provider = reference_provider(trading)

        assert provider.fetch_reference([]) == ()
        assert trading.calls == []


class TestReferenceQuota:
    def test_a_whole_batch_costs_one_request(self):
        """The board is batched, so the Universe costs one call, not a hundred.

        This is the quota contract for this capability: at 20 requests a minute
        without an API key, a per-symbol read would spend five minutes on what
        one read covers.
        """
        trading = FakeTrading(
            price_board(
                [
                    hpg_board_row(),
                    hpg_board_row(symbol="FPT", listed_share=1_703_507_121),
                    hpg_board_row(symbol="VCB", listed_share=8_355_675_094),
                ]
            )
        )
        provider = reference_provider(trading)

        snapshots = provider.fetch_reference(["HPG", "FPT", "VCB"])

        assert len(snapshots) == 3
        assert len(trading.calls) == 1


class TestReferenceRefusal:
    def test_a_room_above_the_room_it_sits_inside_is_never_recorded(self, caplog):
        """A room larger than its own total is a unit slip between the two.

        The contract refuses it outright and nothing here downgrades that to a
        stored figure with a caveat — it would be a plausible-looking ownership
        number nobody re-checks.
        """
        provider = reference_provider(
            FakeTrading(
                price_board(
                    [hpg_board_row(current_room=4_200_000_000, total_room=4_137_052_614)]
                )
            )
        )

        with caplog.at_level("ERROR"):
            assert provider.fetch_reference(["HPG"]) == ()

        assert "HPG" in caplog.text

    def test_a_contradictory_row_does_not_cost_the_rest_of_the_batch(self):
        """The response is well formed and every other row in it is fine.

        Failing the call would lose ninety-nine good symbols to one bad one.
        """
        provider = reference_provider(
            FakeTrading(
                price_board(
                    [
                        hpg_board_row(current_room=4_200_000_000),
                        hpg_board_row(symbol="FPT"),
                    ]
                )
            )
        )

        snapshots = provider.fetch_reference(["HPG", "FPT"])

        assert [snapshot.symbol for snapshot in snapshots] == ["FPT"]

    def test_a_wholly_empty_board_is_an_error(self):
        provider = reference_provider(FakeTrading(price_board([])))

        with pytest.raises(VnstockProviderError):
            provider.fetch_reference(["HPG"])

    def test_a_board_missing_a_field_is_an_error(self):
        provider = reference_provider(
            FakeTrading(
                price_board([{"symbol": "HPG", "listed_share": 8_442_964_520}])
            )
        )

        with pytest.raises(VnstockProviderError) as error:
            provider.fetch_reference(["HPG"])

        assert "current_room" in str(error.value)

    def test_an_upstream_failure_becomes_a_provider_error(self):
        provider = reference_provider(FakeTrading(TimeoutError("gateway gone")))

        with pytest.raises(VnstockProviderError):
            provider.fetch_reference(["HPG"])


class TestReferenceIsolation:
    def test_a_symbol_absent_from_the_board_does_not_cost_the_others(self):
        provider = reference_provider(
            FakeTrading(price_board([hpg_board_row(), hpg_board_row(symbol="FPT")]))
        )

        snapshots = provider.fetch_reference(["HPG", "DELISTED", "FPT"])

        assert [snapshot.symbol for snapshot in snapshots] == ["HPG", "FPT"]

    def test_a_symbol_with_nothing_in_its_row_is_skipped(self):
        provider = reference_provider(
            FakeTrading(
                price_board(
                    [
                        hpg_board_row(),
                        hpg_board_row(
                            symbol="NEW",
                            listed_share=None,
                            current_room=None,
                            total_room=None,
                        ),
                    ]
                )
            )
        )

        snapshots = provider.fetch_reference(["HPG", "NEW"])

        assert [snapshot.symbol for snapshot in snapshots] == ["HPG"]

    def test_a_symbol_missing_only_its_share_count_keeps_its_rooms(self):
        provider = reference_provider(
            FakeTrading(price_board([hpg_board_row(listed_share=None)]))
        )

        (snapshot,) = provider.fetch_reference(["HPG"])

        assert snapshot.shares == ()
        assert snapshot.total_foreign_room == 4_137_052_614


def statement(items: dict[str, dict[str, float]], periods: list[str]) -> pd.DataFrame:
    """The item-per-row, period-per-column layout VCI returns for statements."""
    rows = []
    for item_id, by_period in items.items():
        row = {"item": item_id, "item_en": item_id, "item_id": item_id}
        row.update({period: by_period.get(period) for period in periods})
        rows.append(row)
    return pd.DataFrame(rows, columns=["item", "item_en", "item_id", *periods])


QUARTERS = ["2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3"]

HPG_INCOME = statement(
    {
        "net_sales": dict(zip(QUARTERS, [5.51589e13, 5.0e13, 4.9e13, 4.8e13])),
        "attributable_to_parent_company": dict(
            zip(QUARTERS, [6_371_019_000_000, 3_100_000_000_000, 2_900_000_000_000, 3_000_000_000_000])
        ),
    },
    QUARTERS,
)

HPG_BALANCE = statement(
    {
        "total_assets": dict(zip(QUARTERS, [278_929_786_015_406, 0, 0, 0])),
        "owners_equity": dict(zip(QUARTERS, [141_516_026_558_331, 0, 0, 0])),
        "minority_interests": dict(zip(QUARTERS, [658_176_389_940, 0, 0, 0])),
    },
    QUARTERS,
)


class FakeFinance:
    """Stands in for ``Finance(symbol=..., source=...)``."""

    def __init__(self, income, balance):
        self.income = income
        self.balance = balance

    def income_statement(self, **kwargs):
        if isinstance(self.income, Exception):
            raise self.income
        return self.income

    def balance_sheet(self, **kwargs):
        if isinstance(self.balance, Exception):
            raise self.balance
        return self.balance


def fundamental_provider(by_symbol: dict) -> VnstockFundamentalProvider:
    def factory(symbol: str, source: str):
        if symbol not in by_symbol:
            raise AssertionError(f"unexpected symbol asked for: {symbol}")
        return by_symbol[symbol]

    return VnstockFundamentalProvider(
        finance_factory=factory,
        now=lambda: NOW,
    )


class TestFundamentalNormalization:
    def test_one_symbol_yields_a_snapshot_with_an_explicit_period(self):
        provider = fundamental_provider(
            {"HPG": FakeFinance(HPG_INCOME, HPG_BALANCE)}
        )

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.symbol == "HPG"
        assert snapshot.period_end == date(2026, 6, 30)
        assert snapshot.metadata.source is ProviderSource.VNSTOCK

    def test_the_latest_period_wins_regardless_of_column_order(self):
        shuffled = HPG_INCOME[["item", "item_en", "item_id", *reversed(QUARTERS)]]
        provider = fundamental_provider({"HPG": FakeFinance(shuffled, HPG_BALANCE)})

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.period_end == date(2026, 6, 30)

    def test_net_income_trails_four_quarters_of_parent_profit(self):
        provider = fundamental_provider(
            {"HPG": FakeFinance(HPG_INCOME, HPG_BALANCE)}
        )

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.trailing_12_month_net_income_vnd == pytest.approx(
            6_371_019_000_000 + 3_100_000_000_000 + 2_900_000_000_000 + 3_000_000_000_000
        )

    def test_parent_equity_excludes_the_minority_interest_inside_it(self):
        """Circular 200 puts minority interest inside owner's equity.

        Measured on HPG: liabilities plus owners_equity equals total assets
        exactly, so the minority line is a part of that equity rather than a
        sibling of it, and parent equity is what remains.
        """
        provider = fundamental_provider(
            {"HPG": FakeFinance(HPG_INCOME, HPG_BALANCE)}
        )

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.parent_equity_vnd == pytest.approx(
            141_516_026_558_331 - 658_176_389_940
        )

    def test_equity_with_no_minority_line_is_taken_as_reported(self):
        balance = statement(
            {"owners_equity": {"2026-Q2": 141_516_026_558_331}}, ["2026-Q2"]
        )
        provider = fundamental_provider({"HPG": FakeFinance(HPG_INCOME, balance)})

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.parent_equity_vnd == pytest.approx(141_516_026_558_331)

    def test_fewer_than_four_quarters_reports_no_trailing_figure(self):
        """Three quarters summed is not a trailing twelve months.

        The period is still worth recording, so the snapshot survives with the
        figure left absent rather than filled with a shorter window wearing a
        twelve-month name.
        """
        short = statement(
            {
                "attributable_to_parent_company": {
                    "2026-Q2": 6_371_019_000_000,
                    "2026-Q1": 3_100_000_000_000,
                }
            },
            ["2026-Q2", "2026-Q1"],
        )
        provider = fundamental_provider({"HPG": FakeFinance(short, HPG_BALANCE)})

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.period_end == date(2026, 6, 30)
        assert snapshot.trailing_12_month_net_income_vnd is None

    def test_a_quarter_with_a_gap_breaks_the_trailing_figure(self):
        holed = statement(
            {
                "attributable_to_parent_company": {
                    "2026-Q2": 6_371_019_000_000,
                    "2026-Q1": None,
                    "2025-Q4": 2_900_000_000_000,
                    "2025-Q3": 3_000_000_000_000,
                }
            },
            QUARTERS,
        )
        provider = fundamental_provider({"HPG": FakeFinance(holed, HPG_BALANCE)})

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.trailing_12_month_net_income_vnd is None

    def test_every_quarter_end_maps_to_the_last_day_of_its_quarter(self):
        for period, expected in [
            ("2026-Q1", date(2026, 3, 31)),
            ("2026-Q2", date(2026, 6, 30)),
            ("2025-Q3", date(2025, 9, 30)),
            ("2025-Q4", date(2025, 12, 31)),
        ]:
            income = statement(
                {"attributable_to_parent_company": {period: 1_000_000_000}}, [period]
            )
            balance = statement({"owners_equity": {period: 2_000_000_000}}, [period])
            provider = fundamental_provider({"HPG": FakeFinance(income, balance)})

            (snapshot,) = provider.fetch_fundamentals(["HPG"])

            assert snapshot.period_end == expected


class TestFundamentalIsolation:
    def test_a_symbol_with_no_statements_does_not_cost_the_others(self):
        provider = fundamental_provider(
            {
                "HPG": FakeFinance(HPG_INCOME, HPG_BALANCE),
                "NEW": FakeFinance(pd.DataFrame(), pd.DataFrame()),
                "FPT": FakeFinance(HPG_INCOME, HPG_BALANCE),
            }
        )

        snapshots = provider.fetch_fundamentals(["HPG", "NEW", "FPT"])

        assert [snapshot.symbol for snapshot in snapshots] == ["HPG", "FPT"]

    def test_a_symbol_whose_read_fails_does_not_cost_the_others(self):
        provider = fundamental_provider(
            {
                "HPG": FakeFinance(HPG_INCOME, HPG_BALANCE),
                "DELISTED": FakeFinance(TimeoutError("gone"), HPG_BALANCE),
                "FPT": FakeFinance(HPG_INCOME, HPG_BALANCE),
            }
        )

        snapshots = provider.fetch_fundamentals(["HPG", "DELISTED", "FPT"])

        assert [snapshot.symbol for snapshot in snapshots] == ["HPG", "FPT"]

    def test_a_period_the_company_has_not_reached_is_skipped(self):
        """A period ending after now would date the snapshot into the future.

        ``effective_at`` may not be later than ``observed_at``, so this is a
        broken row for one symbol rather than something to store.
        """
        future = statement(
            {"attributable_to_parent_company": {"2027-Q1": 1_000_000_000}}, ["2027-Q1"]
        )
        balance = statement({"owners_equity": {"2027-Q1": 2_000_000_000}}, ["2027-Q1"])
        provider = fundamental_provider(
            {
                "HPG": FakeFinance(future, balance),
                "FPT": FakeFinance(HPG_INCOME, HPG_BALANCE),
            }
        )

        snapshots = provider.fetch_fundamentals(["HPG", "FPT"])

        assert [snapshot.symbol for snapshot in snapshots] == ["FPT"]


class TestFundamentalRefusal:
    def test_an_unrecognised_layout_stops_the_batch(self):
        """The older wide layout labels its figures in billions of dong.

        Reading it as if it were the VND layout would be wrong by a factor of a
        billion in a way nothing downstream could detect, so an unfamiliar
        shape fails loudly instead of being interpreted.
        """
        wide = pd.DataFrame(
            [{"ticker": "HPG", "yearReport": 2026, "Revenue (Bn. VND)": 55_158.9}]
        )
        provider = fundamental_provider({"HPG": FakeFinance(wide, HPG_BALANCE)})

        with pytest.raises(VnstockProviderError) as error:
            provider.fetch_fundamentals(["HPG"])

        assert "item_id" in str(error.value)

    def test_a_layout_with_no_recognisable_period_stops_the_batch(self):
        undated = pd.DataFrame(
            [{"item": "x", "item_en": "x", "item_id": "owners_equity", "latest": 1}]
        )
        provider = fundamental_provider({"HPG": FakeFinance(HPG_INCOME, undated)})

        with pytest.raises(VnstockProviderError):
            provider.fetch_fundamentals(["HPG"])


class FakeCompany:
    """Stands in for ``Company(symbol=..., source=...)``, counting its reads."""

    def __init__(self, frame: pd.DataFrame | Exception):
        self.frame = frame
        self.calls = 0

    def events(self):
        self.calls += 1
        if isinstance(self.frame, Exception):
            raise self.frame
        return self.frame


def event_frame(rows: list[dict]) -> pd.DataFrame:
    """The columns a VCI event feed comes back with, as measured in Aug 2026."""
    return pd.DataFrame(rows)


def acb_events() -> pd.DataFrame:
    """ACB's 2025 ex-date beside two rows that are not corporate actions.

    The two extras are the point of the fixture: the same feed answers with
    annual general meetings and director dealings, and a table whose whole
    purpose is that everything in it may be reasoned about must not hold them.
    """
    return event_frame(
        [
            {
                "event_code": "DIV",
                "event_title_en": "Cash Dividend - Year 2024 - 1,000 VND",
                "public_date": "2025-05-16",
                "record_date": "2025-05-26",
                "exright_date": "2025-05-23",
                "value_per_share": 1000.0,
                "exercise_ratio": 0.10,
                "category": "DIVIDEND",
            },
            {
                "event_code": "ISS",
                "event_title_en": "Share Issue - Stock dividend ratio 15.0%",
                "public_date": "2025-05-16",
                "record_date": "2025-05-26",
                "exright_date": "2025-05-23",
                "value_per_share": float("nan"),
                "exercise_ratio": 0.15,
                "category": "DIVIDEND",
            },
            {
                "event_code": "AGME",
                "event_title_en": "ACB - Holds 2026 AGM",
                "public_date": "2026-03-06",
                "record_date": "2026-03-24",
                "exright_date": "2026-03-23",
                "value_per_share": float("nan"),
                "exercise_ratio": float("nan"),
                "category": "SHAREHOLDER_MEETING",
            },
            {
                "event_code": "DDIND",
                "event_title_en": "Nguyen Thu Lan - Subscribe to Buy 800,000 ACB shares",
                "public_date": "2025-11-04",
                "record_date": float("nan"),
                "exright_date": float("nan"),
                "value_per_share": float("nan"),
                "exercise_ratio": float("nan"),
                "category": "MAJOR_SHAREHOLDER_TRADING",
            },
        ]
    )


def action_provider(company: FakeCompany) -> VnstockCorporateActionProvider:
    return VnstockCorporateActionProvider(
        company_factory=lambda symbol, source: company,
        now=lambda: NOW,
    )


class TestCorporateActionNormalization:
    def test_only_the_rows_that_move_a_price_are_kept(self):
        company = FakeCompany(acb_events())

        events = action_provider(company).fetch_corporate_actions("ACB")

        assert [event.event_code for event in events] == ["DIV", "ISS"]

    def test_the_declared_terms_arrive_unchanged(self):
        """Both columns, exactly as given, with nothing reconciled here.

        The cash row's 0.10 is 1,000 VND against the 10,000 VND par rather than a
        share ratio, and this adapter is deliberately not the place that knows
        it: interpreting here would put the provider's wording and the system's
        arithmetic in two files that can drift apart.
        """
        company = FakeCompany(acb_events())

        cash, stock = action_provider(company).fetch_corporate_actions("ACB")

        assert (cash.exercise_ratio, cash.value_per_share) == (0.10, 1000.0)
        assert (stock.exercise_ratio, stock.value_per_share) == (0.15, None)
        assert cash.ex_date == date(2025, 5, 23)

    def test_a_null_ex_date_is_carried_rather_than_refused(self):
        """TCB's real 2026 bonus issue: a ratio, a public date, and no ex-date.

        Dropping it would be the tidier table and the worse answer — an action
        nobody knows the date of is exactly what makes a window unadjustable.
        """
        company = FakeCompany(
            event_frame(
                [
                    {
                        "event_code": "ISS",
                        "event_title_en": "Share Issue - Bonus Issue ratio 60.0%",
                        "public_date": "2026-05-14",
                        "record_date": float("nan"),
                        "exright_date": float("nan"),
                        "value_per_share": float("nan"),
                        "exercise_ratio": 0.6,
                        "category": "DIVIDEND",
                    }
                ]
            )
        )

        (event,) = action_provider(company).fetch_corporate_actions("TCB")

        assert event.ex_date is None
        assert event.public_date == date(2026, 5, 14)
        assert event.exercise_ratio == 0.6

    def test_a_company_with_no_events_is_not_a_failed_read(self):
        company = FakeCompany(pd.DataFrame())

        assert action_provider(company).fetch_corporate_actions("ACB") == ()

    def test_a_layout_without_the_identifying_fields_is_refused_outright(self):
        """No dates and no title is a frame nothing can be stored or read from.

        Refused rather than skipped row by row: it would otherwise end in an
        empty table that reads like a market with no corporate actions in it.
        """
        company = FakeCompany(event_frame([{"event_code": "DIV", "category": "DIVIDEND"}]))

        with pytest.raises(VnstockProviderError, match="missing fields"):
            action_provider(company).fetch_corporate_actions("ACB")

    def test_a_feed_with_no_terms_column_at_all_is_still_read(self):
        """This frame's schema follows its contents, and absence is ordinary.

        A company whose history holds no cash dividend comes back with no
        ``value_per_share`` column — five of the thirty symbols in the configured
        Universe did on the first live run. Demanding the column refuses that
        company's share issues, which are perfectly readable, over the absence of
        a kind of event it has never had. Stored without the term, an action
        already has an honest answer: it refuses to produce a factor.
        """
        company = FakeCompany(
            event_frame(
                [
                    {
                        "event_code": "ISS",
                        "event_title_en": "Share Issue - Stock dividend ratio 20.0%",
                        "public_date": "2025-08-08",
                        "exright_date": "2025-08-13",
                        "exercise_ratio": 0.20,
                        "category": "DIVIDEND",
                    }
                ]
            )
        )

        (event,) = action_provider(company).fetch_corporate_actions("STB")

        assert event.exercise_ratio == 0.20
        assert event.value_per_share is None

    def test_the_feed_is_read_once_per_symbol(self):
        """One request per symbol is what makes a Universe pass affordable."""
        company = FakeCompany(acb_events())

        action_provider(company).fetch_corporate_actions("ACB")

        assert company.calls == 1


class TestSourceOwnership:
    """Each adapter serves the capability the Main/Cover table grants it."""

    def test_reference_is_served_by_the_source_it_claims(self):
        assert VnstockReferenceProvider.source is main_source(Capability.REFERENCE)

    def test_corporate_actions_come_from_the_reference_source(self):
        """The only source with a corporate action feed at all, and it is named.

        The FiinQuant free tier has no such feed, so there is no source choice
        here — but leaving that implicit would make a later fallback look
        available.
        """
        assert VnstockCorporateActionProvider.source is main_source(Capability.REFERENCE)

    def test_fundamental_is_served_by_the_source_it_claims(self):
        assert VnstockFundamentalProvider.source is main_source(Capability.FUNDAMENTAL)


class TestTheAllowanceIsNotThisModuleS:
    """The pace belongs to the account, so it is not kept here any more.

    What replaced it is one Redis arbiter over every live vnstock path
    (``src/core/quota.py``, ``docs/adr/0014``), and its own tests live in
    ``tests/test_vnstock_quota.py``. This class stays as the pointer, because
    the obvious place to look for the pacing is the module that used to do it.
    """

    def test_no_adapter_carries_an_allowance_of_its_own(self):
        import src.stocks.providers.vnstock_provider as module

        assert not hasattr(module, "RequestPacer")
        assert not hasattr(module, "process_pacer")
        assert not hasattr(VnstockReferenceProvider(), "_pacer")


class TestAgainstTheLiveProvider:
    """Pin the shapes the fake frames above are copied from.

    Excluded from the default run. When vnstock changes its layout these fail
    while every test above still passes, which is the only signal that the
    fakes have drifted away from the thing they stand in for.
    """

    @pytest.mark.network
    def test_the_price_board_still_carries_reference_data(self):
        provider = VnstockReferenceProvider()

        (snapshot,) = provider.fetch_reference(["HPG"])

        (shares,) = snapshot.shares
        assert shares.share_type is ShareType.LISTED
        assert shares.value > 1_000_000_000
        assert snapshot.current_foreign_room <= snapshot.total_foreign_room

    @pytest.mark.network
    def test_the_event_feed_still_carries_the_terms_of_an_action(self):
        """The columns every fake event frame above is copied from.

        ACB pays a cash dividend and a stock dividend on one ex-date every year,
        so this is the shape that has to keep arriving: two rows, one with a
        payment and one with a ratio.
        """
        provider = VnstockCorporateActionProvider()

        events = provider.fetch_corporate_actions("ACB")

        assert events
        assert {event.event_code for event in events} <= {"DIV", "ISS"}
        cash = [event for event in events if event.event_code == "DIV"]
        assert cash and all(event.value_per_share for event in cash)
        issues = [event for event in events if event.event_code == "ISS"]
        assert issues and all(event.exercise_ratio for event in issues)

    @pytest.mark.network
    def test_statements_still_arrive_in_the_layout_this_adapter_reads(self):
        provider = VnstockFundamentalProvider()

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.period_end.month in (3, 6, 9, 12)
        # Whole dong: a quarter's parent profit for a company this size runs to
        # thousands of billions, so a billion-scaled layout would be tiny here.
        assert snapshot.trailing_12_month_net_income_vnd > 1e11
        assert snapshot.parent_equity_vnd > 1e13

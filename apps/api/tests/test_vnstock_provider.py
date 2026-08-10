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
    Capability,
    ProviderSource,
    ShareType,
    main_source,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.providers.vnstock_provider import (
    RequestPacer,
    VnstockFundamentalProvider,
    VnstockProviderError,
    VnstockReferenceProvider,
    quota_per_minute,
)
from src.stocks.shared import StockServiceError


NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


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


def reference_provider(trading: FakeTrading) -> VnstockReferenceProvider:
    return VnstockReferenceProvider(
        trading_factory=lambda source: trading,
        pacer=RequestPacer(quota_per_minute(""), sleep=lambda seconds: None),
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
        would make every re-run of a cycle a fresh record of facts that have not
        changed — and re-running after a bad day is the operator's normal
        repair, not an event worth a second row."""
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
        pacer=RequestPacer(quota_per_minute(""), sleep=lambda seconds: None),
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


class TestFundamentalQuota:
    def test_each_upstream_read_is_paced_to_the_configured_allowance(self):
        """Two statements per symbol, each spaced by the quota interval.

        Without an API key vnstock allows 20 requests a minute, so a Universe
        read has to spend three seconds between calls rather than discovering
        the limit by being cut off.
        """
        slept: list[float] = []
        elapsed = [0.0]

        def sleep(seconds: float) -> None:
            slept.append(seconds)
            elapsed[0] += seconds

        provider = VnstockFundamentalProvider(
            finance_factory=lambda symbol, source: FakeFinance(
                HPG_INCOME, HPG_BALANCE
            ),
            pacer=RequestPacer(
                quota_per_minute(""),
                clock=lambda: elapsed[0],
                sleep=sleep,
            ),
            now=lambda: NOW,
        )

        provider.fetch_fundamentals(["HPG", "FPT"])

        # Four reads, the first free and the rest each waiting a full interval.
        assert slept == pytest.approx([3.0, 3.0, 3.0])


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


class TestSourceOwnership:
    """Each adapter serves the capability the Main/Cover table grants it."""

    def test_reference_is_served_by_the_source_it_claims(self):
        assert VnstockReferenceProvider.source is main_source(Capability.REFERENCE)

    def test_fundamental_is_served_by_the_source_it_claims(self):
        assert VnstockFundamentalProvider.source is main_source(Capability.FUNDAMENTAL)


class TestQuota:
    def test_an_api_key_raises_the_allowance(self):
        assert quota_per_minute("") == 20
        assert quota_per_minute("a-key") == 60

    def test_the_allowance_is_read_from_the_variable_vnstock_itself_reads(
        self, monkeypatch
    ):
        """A key vnstock cannot see must not raise the pace this side keeps.

        vnstock decides the tier from the environment. Reading the key from
        anywhere else — a settings file it never loads, say — would pace at 60
        against an account still on 20, and it answers being cut off by calling
        sys.exit().
        """
        import src.stocks.providers.vnstock_provider as module

        monkeypatch.setattr(module, "_process_pacer", None)
        monkeypatch.delenv(module.API_KEY_ENV_VAR, raising=False)
        assert module.process_pacer().min_interval == pytest.approx(3.0)

        monkeypatch.setattr(module, "_process_pacer", None)
        monkeypatch.setenv(module.API_KEY_ENV_VAR, "a-key")
        assert module.process_pacer().min_interval == pytest.approx(1.0)

    def test_both_adapters_default_to_one_shared_allowance(self, monkeypatch):
        """The allowance belongs to the account, not to an adapter.

        A cycle reading both capabilities with a pacer each would run at twice
        the allowance and be cut off partway through.
        """
        import src.stocks.providers.vnstock_provider as module

        monkeypatch.setattr(module, "_process_pacer", None)

        reference = VnstockReferenceProvider()
        fundamental = VnstockFundamentalProvider()

        assert reference._pacer is fundamental._pacer


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
    def test_statements_still_arrive_in_the_layout_this_adapter_reads(self):
        provider = VnstockFundamentalProvider()

        (snapshot,) = provider.fetch_fundamentals(["HPG"])

        assert snapshot.period_end.month in (3, 6, 9, 12)
        # Whole dong: a quarter's parent profit for a company this size runs to
        # thousands of billions, so a billion-scaled layout would be tiny here.
        assert snapshot.trailing_12_month_net_income_vnd > 1e11
        assert snapshot.parent_equity_vnd > 1e13


class TestRequestPacer:
    def test_the_first_call_does_not_wait(self):
        slept: list[float] = []
        pacer = RequestPacer(20, clock=lambda: 0.0, sleep=slept.append)

        pacer.wait()

        assert slept == []

    def test_a_second_immediate_call_waits_out_the_interval(self):
        slept: list[float] = []
        pacer = RequestPacer(20, clock=lambda: 0.0, sleep=slept.append)

        pacer.wait()
        pacer.wait()

        assert slept == pytest.approx([3.0])

    def test_a_call_after_the_interval_does_not_wait(self):
        slept: list[float] = []
        ticks = iter([0.0, 10.0, 10.0])
        pacer = RequestPacer(20, clock=lambda: next(ticks), sleep=slept.append)

        pacer.wait()
        pacer.wait()

        assert slept == []

    def test_a_faster_allowance_waits_less(self):
        slept: list[float] = []
        pacer = RequestPacer(60, clock=lambda: 0.0, sleep=slept.append)

        pacer.wait()
        pacer.wait()

        assert slept == pytest.approx([1.0])

    def test_an_allowance_of_nothing_is_refused(self):
        with pytest.raises(ValueError):
            RequestPacer(0)

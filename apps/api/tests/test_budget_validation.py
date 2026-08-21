"""Budget Validation refuses an impossible configuration at startup.

The arithmetic is local and costs no tokens (``docs/adr/0014``): a pricing table
that cannot fund one Analysis under $0.0045 or one Turn under $0.50 is a fact
about the configuration, knowable before the first request. Discovering it
halfway through a real Turn is the failure these checks exist to prevent.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.core.config import Settings
from src.core.llm.budget import (
    ANALYSIS_COST_CEILING_USD,
    ANALYSIS_INPUT_TOKENS,
    ANALYSIS_OUTPUT_TOKENS,
    TURN_COST_CEILING_USD,
    BudgetValidationError,
    enforce_budget_validation,
    validate_budget,
)
from src.core.llm.config import llm_config_from_settings

# Prices that fund both workloads with room to spare: one Analysis costs
# 6,000 x $0.5/Mtok + 1,500 x $1/Mtok = $0.0045, exactly the ceiling.
AFFORDABLE = dict(
    llm_price_batch_input_usd_per_mtok=0.5,
    llm_price_batch_cached_input_usd_per_mtok=0.05,
    llm_price_batch_cache_write_usd_per_mtok=0.5,
    llm_price_batch_output_usd_per_mtok=1.0,
    llm_price_session_input_usd_per_mtok=2.0,
    llm_price_session_cached_input_usd_per_mtok=0.2,
    llm_price_session_cache_write_usd_per_mtok=2.5,
    llm_price_session_output_usd_per_mtok=10.0,
)


def _config(**overrides):
    base = dict(
        # Ignore any .env a developer happens to have: a local price or lane
        # override would fail these tests for a reason not in the repository.
        _env_file=None,
        alpha_desk_enabled=True,
        llm_base_url="http://localhost:8317/v1",
        llm_api_key="dev-token",
        llm_pricing_version="2026-08",
        llm_pricing_effective_date=date(2026, 8, 1),
        **AFFORDABLE,
    )
    base.update(overrides)
    return llm_config_from_settings(Settings(**base))


def _failed_ceilings(report) -> set[str]:
    return {failure.ceiling for failure in report.failures}


class TestAffordableConfiguration:
    def test_the_published_shape_passes(self):
        report = validate_budget(_config())

        assert report.ok, report.summary()
        assert report.failures == ()

    def test_it_reports_what_the_two_workloads_actually_cost(self):
        report = validate_budget(_config())

        assert report.analysis_cost_usd == pytest.approx(ANALYSIS_COST_CEILING_USD)
        # 100,000 input at the dearer cache-write price, 20,000 output.
        assert report.turn_cost_usd == pytest.approx(0.45)

    def test_the_worst_case_input_price_is_the_one_that_is_charged(self):
        """Admission reserves the cache-write worst case, so validation must too."""
        report = validate_budget(
            _config(llm_price_batch_cache_write_usd_per_mtok=1.0)
        )

        expected = (
            ANALYSIS_INPUT_TOKENS * 1.0 + ANALYSIS_OUTPUT_TOKENS * 1.0
        ) / 1_000_000
        assert report.analysis_cost_usd == pytest.approx(expected)
        assert not report.ok


class TestImpossibleConfiguration:
    def test_an_analysis_that_cannot_be_funded_names_its_ceiling(self):
        report = validate_budget(
            _config(llm_price_batch_input_usd_per_mtok=5.0)
        )

        assert not report.ok
        assert "analysis_cost" in _failed_ceilings(report)
        assert "$0.0045" in report.summary()

    def test_a_turn_that_cannot_be_funded_names_its_ceiling(self):
        report = validate_budget(
            _config(llm_price_session_output_usd_per_mtok=100.0)
        )

        assert not report.ok
        assert "turn_cost" in _failed_ceilings(report)
        assert "$0.50" in report.summary()

    def test_lane_allocations_that_miss_the_envelope_are_refused(self):
        report = validate_budget(_config(llm_budget_turn_usd=40.0))

        assert not report.ok
        assert "monthly_envelope" in _failed_ceilings(report)

    def test_the_hard_fifty_dollar_envelope_cannot_be_configured_upward(self):
        report = validate_budget(
            _config(
                llm_budget_monthly_usd=100.0,
                llm_budget_analysis_usd=20.0,
                llm_budget_turn_usd=60.0,
                llm_budget_emergency_usd=10.0,
                llm_budget_eval_usd=10.0,
            )
        )

        assert not report.ok
        assert "monthly_envelope" in _failed_ceilings(report)

    def test_a_lane_too_small_for_one_unit_of_its_own_workload_is_refused(self):
        report = validate_budget(
            _config(
                llm_budget_analysis_usd=0.001,
                llm_budget_turn_usd=39.999,
            )
        )

        assert not report.ok
        assert "analysis_lane" in _failed_ceilings(report)

    def test_a_missing_price_is_refused_rather_than_read_as_free(self):
        report = validate_budget(
            _config(llm_price_session_output_usd_per_mtok=0.0)
        )

        assert not report.ok
        assert "pricing_table" in _failed_ceilings(report)
        assert "session" in report.summary()

    def test_a_cached_read_dearer_than_a_fresh_one_is_refused(self):
        """The only way that arithmetic happens is a transposed pair of prices."""
        report = validate_budget(
            _config(llm_price_batch_cached_input_usd_per_mtok=0.6)
        )

        assert not report.ok
        assert "pricing_table" in _failed_ceilings(report)

    def test_prices_with_no_version_or_effective_date_are_refused(self):
        report = validate_budget(
            _config(llm_pricing_version="", llm_pricing_effective_date=None)
        )

        assert not report.ok
        assert "pricing_version" in _failed_ceilings(report)

    def test_a_route_with_no_credential_is_refused(self):
        report = validate_budget(_config(llm_api_key=""))

        assert not report.ok
        assert "route" in _failed_ceilings(report)

    def test_every_failure_is_reported_rather_than_only_the_first(self):
        report = validate_budget(
            _config(
                llm_price_batch_input_usd_per_mtok=5.0,
                llm_price_session_output_usd_per_mtok=100.0,
                llm_budget_eval_usd=6.0,
            )
        )

        assert {"analysis_cost", "turn_cost", "monthly_envelope"} <= _failed_ceilings(
            report
        )


class TestAnUnmeteredEnvelope:
    """Zero across all five values is a deployment with no monthly ceiling.

    The prices are not part of that decision. They are what the ledger records
    against every call, so they stay validated — an unmetered envelope must not
    become a licence to boot with a price table nobody filled in.
    """

    UNMETERED = dict(
        llm_budget_monthly_usd=0,
        llm_budget_analysis_usd=0,
        llm_budget_turn_usd=0,
        llm_budget_emergency_usd=0,
        llm_budget_eval_usd=0,
    )

    def test_all_five_at_zero_passes(self):
        report = validate_budget(_config(**self.UNMETERED))

        assert report.ok, report.summary()
        assert report.analysis_cost_usd == pytest.approx(ANALYSIS_COST_CEILING_USD)

    def test_the_price_table_is_still_validated(self):
        report = validate_budget(
            _config(**self.UNMETERED, llm_price_session_output_usd_per_mtok=0)
        )

        assert not report.ok
        assert "pricing_table" in _failed_ceilings(report)

    def test_one_lane_left_at_zero_is_a_variable_nobody_filled_in(self):
        report = validate_budget(_config(llm_budget_turn_usd=0))

        assert not report.ok
        assert "monthly_envelope" in _failed_ceilings(report)


class TestEnforcement:
    def test_alpha_desk_enabled_fails_startup_naming_the_ceiling(self):
        config = _config(llm_price_batch_input_usd_per_mtok=5.0)

        with pytest.raises(BudgetValidationError) as exc_info:
            enforce_budget_validation(config)

        assert "analysis_cost" in str(exc_info.value)
        assert exc_info.value.report.failures

    def test_alpha_desk_disabled_only_warns_and_the_app_starts(self, caplog):
        config = _config(
            alpha_desk_enabled=False, llm_price_batch_input_usd_per_mtok=5.0
        )

        with caplog.at_level("WARNING"):
            report = enforce_budget_validation(config)

        assert not report.ok
        assert any("analysis_cost" in record.message for record in caplog.records)

    def test_an_affordable_configuration_returns_its_report(self):
        report = enforce_budget_validation(_config())

        assert report.ok


class TestStartup:
    """Placement matters as much as the check: before anything else runs."""

    def test_an_impossible_configuration_refuses_startup(self, monkeypatch):
        from fastapi.testclient import TestClient

        from src import main

        started = []
        monkeypatch.setattr(
            main, "llm_config_from_settings", lambda _s=None: _config(
                llm_price_batch_input_usd_per_mtok=5.0
            )
        )
        monkeypatch.setattr(
            main, "setup_scheduler", lambda scheduler: started.append(scheduler)
        )

        with pytest.raises(BudgetValidationError) as exc_info:
            with TestClient(main.app):
                pass  # pragma: no cover - startup is what raises

        assert "analysis_cost" in str(exc_info.value)
        # Before the scheduler, so no job can dispatch against a route whose
        # prices were never going to hold.
        assert started == []

    def test_a_fundable_configuration_lets_the_app_start(self, monkeypatch):
        from fastapi.testclient import TestClient

        from src import main

        monkeypatch.setattr(main, "llm_config_from_settings", lambda _s=None: _config())

        with TestClient(main.app) as client:
            assert client.get("/health").status_code == 200


class TestValidationCostsNoTokens:
    def test_it_makes_no_network_call(self, monkeypatch):
        """The check is arithmetic. Anything reaching for a socket is a defect."""
        import httpx

        def explode(*args, **kwargs):  # pragma: no cover - the point is not calling it
            raise AssertionError("Budget Validation must not open a connection")

        monkeypatch.setattr(httpx, "Client", explode)
        monkeypatch.setattr(httpx, "AsyncClient", explode)
        monkeypatch.setattr(httpx, "request", explode)

        assert validate_budget(_config()).ok

    def test_the_budget_module_imports_no_transport(self):
        import src.core.llm.budget as budget

        assert not hasattr(budget, "httpx")

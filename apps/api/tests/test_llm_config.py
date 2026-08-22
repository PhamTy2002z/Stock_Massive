"""The route, the models and the prices are configuration, and nothing else.

The whole reason the LLM boundary exists is that a route change is an env-var
flip (``docs/adr/0014``). These tests hold that line: a model id compiled into
the source would still pass every behavioural test in the suite, so the
assertion has to be made about the source itself.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.core.config import Settings
from src.core.llm.config import (
    LLMConfig,
    TokenPrices,
    Workload,
    llm_config_from_settings,
)


def _settings(**overrides) -> Settings:
    base = dict(
        # Ignore any .env a developer happens to have: these tests are about
        # the values handed in, and a local file overriding one of them would
        # fail the suite for a reason that is not in the repository.
        _env_file=None,
        alpha_desk_enabled=True,
        llm_base_url="http://localhost:8317/v1",
        llm_api_key="dev-token",
        llm_model_batch="model-batch",
        llm_model_session="model-session",
        llm_pricing_version="2026-08-openai",
        llm_pricing_effective_date=date(2026, 8, 1),
        llm_price_batch_input_usd_per_mtok=0.5,
        llm_price_batch_cached_input_usd_per_mtok=0.05,
        llm_price_batch_cache_write_usd_per_mtok=0.5,
        llm_price_batch_output_usd_per_mtok=1.0,
        llm_price_session_input_usd_per_mtok=2.0,
        llm_price_session_cached_input_usd_per_mtok=0.2,
        llm_price_session_cache_write_usd_per_mtok=2.5,
        llm_price_session_output_usd_per_mtok=10.0,
    )
    base.update(overrides)
    return Settings(**base)


class TestConfiguredRoute:
    def test_carries_route_models_and_both_price_sets(self):
        config = llm_config_from_settings(_settings())

        assert config.enabled is True
        assert config.route.base_url == "http://localhost:8317/v1"
        assert config.route.api_key == "dev-token"
        assert config.model_for(Workload.BATCH) == "model-batch"
        assert config.model_for(Workload.SESSION) == "model-session"
        assert config.pricing.version == "2026-08-openai"
        assert config.pricing.effective_from == date(2026, 8, 1)
        assert config.pricing.for_workload(Workload.SESSION).output == 10.0

    def test_lane_allocations_come_from_settings(self):
        config = llm_config_from_settings(
            _settings(
                llm_budget_monthly_usd=45.0,
                llm_budget_analysis_usd=10.0,
                llm_budget_turn_usd=30.0,
                llm_budget_emergency_usd=5.0,
            )
        )

        assert config.lanes.monthly_envelope_usd == 45.0
        assert config.lanes.allocated_usd == 45.0

    def test_per_user_ceilings_come_from_settings(self):
        config = llm_config_from_settings(
            _settings(
                llm_user_turn_starts_per_day=50,
                llm_user_active_turns=4,
                llm_system_active_turns=8,
                llm_user_daily_usd=9.5,
                llm_user_rolling_30d_usd=40.0,
            )
        )

        assert config.ceilings.turn_starts_per_day == 50
        assert config.ceilings.active_turns_per_user == 4
        assert config.ceilings.active_turns_system == 8
        assert config.ceilings.daily_usd == 9.5
        assert config.ceilings.rolling_30d_usd == 40.0

    def test_zero_reads_as_unlimited_one_ceiling_at_a_time(self):
        """``0`` means unlimited, and only for the ceiling that carries it."""
        config = llm_config_from_settings(
            _settings(llm_user_turn_starts_per_day=0, llm_user_daily_usd=0)
        )

        assert config.ceilings.turn_starts_per_day is None
        assert config.ceilings.daily_usd is None
        assert config.ceilings.active_turns_per_user == 1
        assert config.ceilings.rolling_30d_usd == 15.0

    def test_the_adr_numbers_are_the_defaults(self):
        """A deployment that configures nothing gets the contract."""
        config = llm_config_from_settings(_settings())

        assert config.ceilings.turn_starts_per_day == 20
        assert config.ceilings.active_turns_per_user == 1
        assert config.ceilings.active_turns_system == 3
        assert config.ceilings.daily_usd == 3.0
        assert config.ceilings.rolling_30d_usd == 15.0

    def test_an_unmetered_envelope_is_all_four_values_or_none(self):
        unmetered = llm_config_from_settings(
            _settings(
                llm_budget_monthly_usd=0,
                llm_budget_analysis_usd=0,
                llm_budget_turn_usd=0,
                llm_budget_emergency_usd=0,
            )
        )

        assert unmetered.lanes.unmetered is True
        assert llm_config_from_settings(_settings()).lanes.unmetered is False
        assert (
            llm_config_from_settings(_settings(llm_budget_turn_usd=0)).lanes.unmetered
            is False
        )

    def test_credential_stays_out_of_the_representation(self):
        """A route printed into a log or a traceback must not carry the key."""
        config = llm_config_from_settings(_settings(llm_api_key="sk-secret-value"))

        assert "sk-secret-value" not in repr(config)
        assert "sk-secret-value" not in repr(config.route)
        assert "sk-secret-value" not in str(config.route)

    def test_disabled_alpha_desk_still_produces_a_config(self):
        """Nothing about being off changes what the configuration says."""
        config = llm_config_from_settings(_settings(alpha_desk_enabled=False))

        assert config.enabled is False
        assert config.model_for(Workload.BATCH) == "model-batch"


class TestTokenPrices:
    def test_reasoning_tokens_bill_at_the_output_price(self):
        """Five counters, four prices — reasoning has no price of its own."""
        prices = TokenPrices(
            input=1.0, cached_input=0.1, cache_write=1.25, output=10.0
        )

        cost = prices.cost_usd(
            input_tokens=1_000_000,
            cached_input_tokens=0,
            cache_write_tokens=0,
            output_tokens=0,
            reasoning_tokens=1_000_000,
        )

        assert cost == pytest.approx(11.0)

    def test_each_counter_meets_its_own_price(self):
        prices = TokenPrices(
            input=1.0, cached_input=0.1, cache_write=2.0, output=10.0
        )

        cost = prices.cost_usd(
            input_tokens=1_000_000,
            cached_input_tokens=1_000_000,
            cache_write_tokens=1_000_000,
            output_tokens=1_000_000,
            reasoning_tokens=0,
        )

        assert cost == pytest.approx(13.1)

    def test_a_call_that_spends_nothing_costs_nothing(self):
        prices = TokenPrices(input=1.0, cached_input=0.1, cache_write=2.0, output=10.0)

        assert prices.cost_usd() == 0.0


class TestNoModelIdIsCompiledIn:
    """The one assertion that cannot be made about behaviour.

    A default lives in ``Settings`` — that is the configuration layer, and the
    published production defaults belong there. Anywhere else, a model id is a
    constant that survives an env-var flip.
    """

    def test_no_source_file_outside_settings_names_a_model(self):
        api_root = Path(__file__).resolve().parents[1]
        settings_file = api_root / "src" / "core" / "config.py"
        offenders = []

        for path in (api_root / "src").rglob("*.py"):
            if path == settings_file:
                continue
            text = path.read_text(encoding="utf-8")
            if "gpt-5.6" in text or "gpt-4" in text or "claude-" in text:
                offenders.append(str(path.relative_to(api_root)))

        assert offenders == []

    def test_the_published_defaults_are_the_settings_defaults(self):
        defaults = Settings(
            _env_file=None,
            database_url="postgresql://unused/unused",
        )

        assert defaults.llm_model_batch == "gpt-5.6-luna"
        assert defaults.llm_model_session == "gpt-5.6-terra"


class TestAnUnfilledKeyReachesBudgetValidation:
    """``docker-compose.yml`` forwards the price block with ``${VAR:-}``.

    An unfilled key therefore arrives as an empty string rather than as an
    absent variable. Settings has to survive that: the refusal belongs to
    Budget Validation, which can name the key an operator failed to fill,
    not to a Pydantic parse error thrown before the app has a voice.
    """

    def test_an_empty_effective_date_is_an_unset_one(self):
        settings = Settings(
            _env_file=None,
            database_url="postgresql://unused/unused",
            llm_pricing_effective_date="",
        )

        assert settings.llm_pricing_effective_date is None

    def test_whitespace_is_not_a_date_either(self):
        settings = Settings(
            _env_file=None,
            database_url="postgresql://unused/unused",
            llm_pricing_effective_date="   ",
        )

        assert settings.llm_pricing_effective_date is None

    def test_a_real_date_still_parses(self):
        settings = Settings(
            _env_file=None,
            database_url="postgresql://unused/unused",
            llm_pricing_effective_date="2026-08-01",
        )

        assert settings.llm_pricing_effective_date == date(2026, 8, 1)


class TestConfigIsImmutable:
    def test_a_config_cannot_be_edited_after_it_is_built(self):
        config = llm_config_from_settings(_settings())

        with pytest.raises(Exception):
            config.enabled = False  # type: ignore[misc]

    def test_workloads_cover_both_lanes(self):
        assert set(Workload) == {Workload.BATCH, Workload.SESSION}
        assert isinstance(llm_config_from_settings(_settings()), LLMConfig)

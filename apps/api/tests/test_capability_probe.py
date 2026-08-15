"""The configured route proves the four contracts Alpha Desk relies on."""

import logging
from types import SimpleNamespace

import pytest

from src.core.llm import (
    BudgetLane,
    CapabilityProbe,
    CapabilityProbeError,
    Completion,
    OwnerType,
    ToolCall,
    clear_capability_probe_cache,
    enforce_capability_probe,
)


class ConformingRoute:
    def __init__(self) -> None:
        self.calls = []

    async def complete(self, request, spend):
        assert spend.owner.type is OwnerType.CAPABILITY_PROBE
        assert spend.lane is BudgetLane.EMERGENCY
        self.calls.append((request, spend))
        check = request.metadata["probe_check"]
        step = request.metadata.get("probe_step", 1)
        if check == "forced_tool_choice":
            return Completion(
                model=request.model,
                tool_calls=(
                    ToolCall(
                        id="forced",
                        name="probe_echo",
                        arguments={"value": "forced"},
                    ),
                ),
                finish_reason="tool_calls",
            )
        if check == "parallel_tool_calls":
            return Completion(
                model=request.model,
                tool_calls=(
                    ToolCall(id="left", name="probe_left", arguments={"value": 1}),
                    ToolCall(id="right", name="probe_right", arguments={"value": 2}),
                ),
                finish_reason="tool_calls",
            )
        if check == "strict_json_schema":
            return Completion(model=request.model, text='{"ok": true}')
        if check == "closed_tool_loop" and step == 1:
            return Completion(
                model=request.model,
                tool_calls=(
                    ToolCall(
                        id="loop",
                        name="probe_loop",
                        arguments={"value": "open"},
                    ),
                ),
                finish_reason="tool_calls",
            )
        return Completion(model=request.model, text="loop closed")


class DroppingRoute:
    def __init__(self) -> None:
        self.calls = []

    async def complete(self, request, spend):
        self.calls.append(request)
        return Completion(model=request.model, text="parameters ignored")


@pytest.fixture(autouse=True)
def empty_probe_cache():
    clear_capability_probe_cache()
    yield
    clear_capability_probe_cache()


class TestCapabilityProbe:
    pytestmark = pytest.mark.asyncio

    async def test_all_four_checks_pass_and_every_call_uses_emergency_admission(self):
        route = ConformingRoute()

        result = await CapabilityProbe(route, model="session-model").run()

        assert result.ok is True
        assert set(result.checks) == {
            "forced_tool_choice",
            "parallel_tool_calls",
            "strict_json_schema",
            "closed_tool_loop",
        }
        assert all(check.passed for check in result.checks.values())
        assert len(route.calls) == 5

    async def test_every_check_reports_even_when_the_route_drops_parameters(self):
        route = DroppingRoute()

        result = await CapabilityProbe(route, model="session-model").run()

        assert result.ok is False
        assert len(result.checks) == 4
        assert all(not check.passed for check in result.checks.values())
        assert all("parameters ignored" in check.response for check in result.checks.values())

    async def test_result_is_cached_for_the_rest_of_the_process(self):
        route = ConformingRoute()
        probe = CapabilityProbe(route, model="session-model")

        first = await probe.run()
        second = await probe.run()

        assert second is first
        assert len(route.calls) == 5


@pytest.mark.asyncio
async def test_enabled_alpha_desk_refuses_startup_with_check_and_response():
    route = DroppingRoute()
    result = await CapabilityProbe(route, model="session-model").run()

    with pytest.raises(CapabilityProbeError) as failed:
        enforce_capability_probe(result, alpha_desk_enabled=True)

    assert "forced_tool_choice" in str(failed.value)
    assert "parameters ignored" in str(failed.value)


@pytest.mark.asyncio
async def test_disabled_alpha_desk_logs_the_failure_and_continues(caplog):
    route = DroppingRoute()
    result = await CapabilityProbe(route, model="session-model").run()

    with caplog.at_level(logging.WARNING):
        enforce_capability_probe(result, alpha_desk_enabled=False)

    assert "forced_tool_choice" in caplog.text
    assert "parameters ignored" in caplog.text


def test_lifespan_runs_probe_after_universe_and_budget_before_scheduler(monkeypatch):
    from fastapi.testclient import TestClient

    from src import main

    events = []

    class UniverseResult:
        def __len__(self):
            return 0

    monkeypatch.setattr(
        main.Universe,
        "from_settings",
        classmethod(lambda cls, settings: events.append("universe") or UniverseResult()),
    )
    monkeypatch.setattr(
        main,
        "enforce_budget_validation",
        lambda config: events.append("budget"),
    )

    async def fail_probe(config):
        events.append("probe")
        raise RuntimeError("route contract failed")

    async def scheduler_started(scheduler):
        events.append("scheduler")

    monkeypatch.setattr(main, "run_capability_probe_at_startup", fail_probe)
    monkeypatch.setattr(main, "setup_scheduler", scheduler_started)

    with pytest.raises(RuntimeError, match="route contract failed"):
        with TestClient(main.app):
            pass

    assert events == ["universe", "budget", "probe"]


@pytest.mark.asyncio
async def test_probe_skip_is_only_the_explicit_flag(monkeypatch, caplog):
    from src import main

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(llm_capability_probe_enabled=False),
    )
    monkeypatch.setattr(
        main,
        "build_client",
        lambda config: (_ for _ in ()).throw(AssertionError("must not build client")),
    )

    with caplog.at_level(logging.INFO):
        await main.run_capability_probe_at_startup(object())

    assert "skipped by explicit configuration" in caplog.text

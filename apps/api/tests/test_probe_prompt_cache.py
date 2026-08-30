"""The probe's arithmetic, without the network.

Everything the probe *decides* is a pure function of what the provider reported,
and that is deliberate: the calls cost money and are run by hand, so the part
that can be wrong quietly — the summing, the ratio, the verdict — is the part
that has to be free to run.

Two shapes matter and neither is the happy one. A run where some calls hit and
some miss is the *normal* shape on this route, measured: a load balancer served
3 hits in 8 on one prefix. And a run where the provider reported no usage at all
must not read as "the cache works" or as "the cache is broken" — it has to read
as zero, with the failures visible beside it.
"""

from __future__ import annotations

from types import MappingProxyType

from scripts.probe_prompt_cache import Call, Family, summarise
from src.core.llm import Usage, Workload
from src.core.llm.config import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
)


def _routed() -> LLMConfig:
    """A config with a route, so the run reaches the allowance check.

    The probe checks for a route before it checks the allowance, and rightly:
    "no route" and "no budget" are different answers and the first one is
    cheaper to give. A test of the second needs the first to pass.
    """
    prices = TokenPrices(input=1.0, cached_input=0.5, cache_write=1.5, output=8.0)
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://route.example", api_key="k"),
        models=MappingProxyType(
            {Workload.BATCH: "batch-model", Workload.SESSION: "session-model"}
        ),
        pricing=PricingTable(
            version="2026-08", effective_from=None, batch=prices, session=prices
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=90,
            analysis_usd=40.0,
            turn_usd=40.0,
            emergency_usd=10.0,
        ),
    )


def used(fresh: int, cached: int = 0, written: int = 0) -> Usage:
    return Usage(
        input_tokens=fresh,
        cached_input_tokens=cached,
        cache_write_tokens=written,
        output_tokens=20,
    )


def family(name: str, *usages: Usage | None, prefix: int = 5_000) -> Family:
    made = Family(name, prefix)
    for index, usage in enumerate(usages):
        made.calls.append(
            Call(
                family=name,
                index=index,
                usage=usage,
                error="" if usage else "GatewayTimeout: nope",
            )
        )
    return made


def test_a_mixed_run_is_summed_rather_than_judged_call_by_call() -> None:
    """One miss is the route's load balancer, not a failure of the cache."""
    core = family("core", used(5_100), used(200, 4_900), used(5_100), used(200, 4_900))

    summary = core.summary()

    assert summary["calls"] == 4
    assert summary["hits"] == 2
    assert summary["fresh_tokens"] == 10_600
    assert summary["cached_read_tokens"] == 9_800
    assert summary["prompt_tokens"] == 20_400
    assert round(summary["cached_ratio"], 4) == round(9_800 / 20_400, 4)


def test_a_run_the_provider_reported_nothing_for_reads_as_zero() -> None:
    """"We cannot tell" and "it does not cache" look the same from here.

    So the verdict is false and every counter is zero — and the failure count
    beside them is what says which of the two it was.
    """
    report = summarise([family("core", None, None)])

    assert report["cache_is_reading"] is False
    assert report["totals"]["cached_read_tokens"] == 0
    assert report["totals"]["failed"] == 2
    assert report["totals"]["cached_ratio"] == 0.0


def test_a_call_that_returned_no_usage_at_all_is_charged_nothing() -> None:
    empty = Call(family="core", index=0)

    assert (empty.fresh, empty.cached, empty.written, empty.prompt) == (0, 0, 0, 0)
    assert empty.hit is False


def test_the_verdict_is_about_the_total_and_never_about_one_call() -> None:
    """Three misses and one hit is a working cache; four misses is not."""
    assert summarise([family("core", used(5_100), used(5_100), used(5_100), used(200, 4_900))])[
        "cache_is_reading"
    ]
    assert not summarise([family("core", used(5_100), used(5_100))])["cache_is_reading"]


def test_the_totals_are_the_sum_of_the_families_and_carry_their_own_ratio() -> None:
    report = summarise(
        [
            family("core", used(200, 4_900)),
            family("core+domain-body", used(300, 5_600), prefix=5_800),
        ]
    )
    totals = report["totals"]

    assert totals["calls"] == 2
    assert totals["cached_read_tokens"] == 10_500
    assert totals["prompt_tokens"] == 11_000
    assert round(totals["cached_ratio"], 4) == round(10_500 / 11_000, 4)
    assert set(report["families"]) == {"core", "core+domain-body"}


def test_a_cache_write_is_counted_apart_from_a_read() -> None:
    """A route that writes a cache is not a route that read one."""
    report = summarise([family("core", used(5_000, 0, 5_000))])

    assert report["totals"]["cache_write_tokens"] == 5_000
    assert report["cache_is_reading"] is False


def test_the_probe_refuses_to_start_without_a_ceiling() -> None:
    """A probe that can run unbounded eventually will."""
    import asyncio

    import pytest

    from scripts.probe_prompt_cache import main

    with pytest.raises(SystemExit):
        asyncio.run(main([]))
    assert asyncio.run(main(["--ceiling-usd", "0"])) == 2


def test_an_exhausted_probe_allowance_stops_the_run_before_the_first_call() -> None:
    """Otherwise the report reads like a route that stopped caching.

    ``PROBE_DAILY_MICRO_USD`` is a contract constant shared with the boot-time
    Capability Probe, and a deployment that restarted a few times can be most of
    the way through it. Discovering that one call at a time fills the artifact
    with refusals whose counters are all zero — which is indistinguishable, in
    the table, from a cache that returned nothing.
    """
    import asyncio

    import scripts.probe_prompt_cache as probe
    from src.core.llm.admission import PROBE_DAILY_MICRO_USD

    sent: list[object] = []
    original = probe.probe_charged_today
    charged = probe._one
    configured = probe.llm_config_from_settings
    probe.probe_charged_today = lambda: PROBE_DAILY_MICRO_USD - 1
    probe.llm_config_from_settings = _routed

    async def record(*args, **kwargs):  # pragma: no cover - must not run
        sent.append(args)
        raise AssertionError("the probe sent a call on an exhausted allowance")

    probe._one = record
    try:
        code = asyncio.run(probe.main(["--ceiling-usd", "0.5"]))
    finally:
        probe.probe_charged_today = original
        probe._one = charged
        probe.llm_config_from_settings = configured

    assert code == 3
    assert sent == []

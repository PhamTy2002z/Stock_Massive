"""Offline scripted clients driven through the real replay lifecycles."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from datetime import datetime, time, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.agent.registry import ToolEntry, object_schema
from src.auth import models as _auth_models  # noqa: F401  # register FK targets
from src.core.config import get_settings
from src.core.database import Base
from src.core.llm import BudgetLanes, Completion, LLMConfig, LLMRoute, PricingTable, TokenPrices, ToolCall, Usage, Workload, llm_config_from_settings

from .contracts import CaseFile, SnapshotFile
from .recording import ScriptedLLMClient

if TYPE_CHECKING:
    from .runner import EvalResult


def smoke_config() -> LLMConfig:
    prices = TokenPrices(input=0, cached_input=0, cache_write=0, output=0)
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://offline.eval.invalid/v1", api_key="offline-not-a-credential"),
        models=MappingProxyType({Workload.SESSION: "eval-scripted-session", Workload.BATCH: "eval-scripted-batch"}),
        pricing=PricingTable(version="eval-offline-v1", effective_from=None, session=prices, batch=prices),
        lanes=BudgetLanes(monthly_envelope_usd=1, analysis_usd=0.4, turn_usd=0.4, emergency_usd=0.2),
        route_breaker_enabled=False,
    )


def _with_database(url: str, name: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{name}"))


@contextmanager
def disposable_store() -> Iterator[Any]:
    """Create and remove one explicitly named, case-local Postgres database."""
    name = f"stock_massive_eval_{uuid.uuid4().hex[:12]}"
    base_url = get_settings().database_url
    admin = create_engine(_with_database(base_url, "postgres"), isolation_level="AUTOCOMMIT", future=True)
    engine = None
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        engine = create_engine(_with_database(base_url, name), future=True)
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as connection:
            connection.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name AND pid <> pg_backend_pid()"), {"name": name})
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


@contextmanager
def _offline_runtime_import() -> Iterator[Any]:
    """Import the runtime while suppressing dependency onboarding/update I/O.

    vnstock performs update HTTP and starts a background AGENTS.md writer at
    import time.  Neither behavior belongs in an offline evaluation.  The
    guard is installed before the runtime import and removed immediately after.
    """
    original_get = requests.get

    def blocked_get(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("network disabled during offline eval import")

    requests.get = blocked_get
    import vnai

    original_async = getattr(vnai, "async_setup_agent_environment", None)
    original_sync = getattr(vnai, "setup_agent_environment", None)
    vnai.async_setup_agent_environment = lambda *_args, **_kwargs: False
    vnai.setup_agent_environment = lambda *_args, **_kwargs: False
    try:
        from .runner import EvalRunner

        yield EvalRunner
    finally:
        requests.get = original_get
        if original_async is not None:
            vnai.async_setup_agent_environment = original_async
        if original_sync is not None:
            vnai.setup_agent_environment = original_sync


def _answer(case: CaseFile) -> str:
    words = ["FPT", "uncertain", "limited", "cannot", "unavailable", "substitute", "valuation", "counterargument", "hold", "watch", "neutral", "falsifier", "alternative", "conflict"]
    for expectation in case.expectations:
        params = expectation.params
        if expectation.kind == "figure":
            value = params["value"]
            words.append(f"{float(value):,.1f}" if isinstance(value, float) else f"{int(value):,}")
            words.append(str(params.get("unit", "")))
        elif expectation.kind == "unit":
            words.append(str(params.get("value", "")))
        elif expectation.kind in ("required_claims", "acceptable_conclusion"):
            words.extend(str(value) for value in params.get("values", []))
        elif expectation.kind == "entity_scope":
            words.extend(str(value) for value in params.get("required", []))
        elif expectation.kind == "clarification":
            words.append("What portfolio horizon and risk limits apply?")
    return " ".join(filter(None, words))


def _tool(name: str) -> ToolEntry:
    properties = {"field_id": {"type": "string"}} if name == "get_field" else {}
    return ToolEntry(
        name=name,
        toolset="signals",
        schema=object_schema(properties),
        handler=lambda _context, _arguments: {},
        description="Read one declared value from the frozen evaluation world.",
        display_name="Read frozen evidence",
        reads_external=False,
    )


def _script(case: CaseFile) -> tuple[list[Completion], tuple[ToolEntry, ...]]:
    answer = _answer(case)
    if case.surface == "conversation":
        # Every Conversation snapshot except the deliberate lookahead trap has
        # get_field.  For the trap, a direct refusal is the correct trajectory.
        if case.case_id == "fact-publication-lookahead":
            return [Completion(model="eval-scripted-session", text=answer, usage=Usage(input_tokens=10, output_tokens=10))], ()
        return [
            Completion(model="eval-scripted-session", tool_calls=(ToolCall(id="field-1", name="get_field", arguments={"field_id": "price.close"}),), usage=Usage(input_tokens=10, output_tokens=2), finish_reason="tool_calls"),
            Completion(model="eval-scripted-session", text=answer, usage=Usage(input_tokens=10, output_tokens=10)),
        ], (_tool("get_field"),)

    fragment = {
        "verdict": "hold",
        "verdictLine": answer,
        "thesis": answer,
        "citedFieldIds": ["realized_volatility.yang_zhang_annualized_pct"],
        "axes": [
            {"axis": axis, "emphasis": "lead" if axis == "technical" else "context", "emphasisReason": "Frozen point-in-time evidence is strongest here.", "read": answer}
            for axis in ("technical", "fundamental", "money_flow", "news")
        ],
    }
    return [
        Completion(model="eval-scripted-batch", tool_calls=(ToolCall(id="catalog-1", name="list_fields", arguments={}),), usage=Usage(input_tokens=10, output_tokens=2), finish_reason="tool_calls"),
        Completion(model="eval-scripted-batch", text="The frozen catalog is sufficient.", usage=Usage(input_tokens=10, output_tokens=3)),
        Completion(model="eval-scripted-batch", text=json.dumps(fragment), usage=Usage(input_tokens=20, output_tokens=20)),
    ], (_tool("list_fields"),)


def tool_catalog_for_case(case: CaseFile) -> tuple[ToolEntry, ...]:
    if case.surface == "analysis":
        return (_tool("list_fields"),)
    if case.case_id == "fact-publication-lookahead":
        return ()
    return (_tool("get_field"),)


async def execute_scripted_case(*, case: CaseFile, snapshots: tuple[SnapshotFile, ...], run_id: str, trial_index: int, mode: str, remaining_ceiling_usd: float) -> "EvalResult":
    if mode != "smoke":
        raise ValueError("the scripted executor is offline-smoke only")
    script, tools = _script(case)
    fixed_now = datetime.combine(case.as_of, time(12), tzinfo=timezone.utc)
    with _offline_runtime_import() as runner_type:
        with disposable_store() as factory:
            result = await runner_type(
                config=smoke_config(),
                session_factory=factory,
                clock=lambda: fixed_now,
            ).run(
                case=case,
                snapshots=snapshots,
                tool_catalog=tools,
                client=ScriptedLLMClient(script),
                run_id=run_id,
                trial_index=trial_index,
                mode="smoke",
            )
    trial = result.trial.model_copy(
        update={
            "started_at": fixed_now,
            "finished_at": fixed_now,
            "latency_ms": 0,
        }
    )
    content = dict(result.observable.content)
    if "elapsed_ms" in content:
        content["elapsed_ms"] = 0
    observable = replace(result.observable, persisted_id=None, content=content)
    trajectory = tuple(
        event.model_copy(
            update={
                "at": fixed_now,
                "payload": {
                    **event.payload,
                    **({"latency_ms": 0} if "latency_ms" in event.payload else {}),
                },
            }
        )
        for event in result.trajectory
    )
    return replace(result, trial=trial, observable=observable, trajectory=trajectory)


async def execute_live_case(*, case: CaseFile, snapshots: tuple[SnapshotFile, ...], run_id: str, trial_index: int, mode: str, remaining_ceiling_usd: float) -> "EvalResult":
    if mode != "multi-trial":
        raise ValueError("the live executor requires multi-trial mode")
    config = llm_config_from_settings()
    if not config.enabled or not config.route.api_key:
        raise ValueError("paid eval requires the configured LLM route and API key")
    with _offline_runtime_import() as runner_type:
        from src.core.llm.transport import build_transport
        from .recording import LiveEvalLLMClient
        from .runner import LiveAuthorization

        with disposable_store() as factory:
            client = LiveEvalLLMClient(
                build_transport(config),
                config=config,
                session_factory=factory,
                clock=lambda: datetime.now(timezone.utc),
            )
            try:
                return await runner_type(config=config, session_factory=factory).run(
                    case=case,
                    snapshots=snapshots,
                    tool_catalog=tool_catalog_for_case(case),
                    client=client,
                    run_id=run_id,
                    trial_index=trial_index,
                    mode="live",
                    live_authorization=LiveAuthorization(route=config.route.base_url, ceiling_usd=remaining_ceiling_usd),
                )
            finally:
                await client.aclose()


@asynccontextmanager
async def live_rubric_judge() -> Iterator[Any]:
    """Own one separately metered rubric client for a paid harness run."""
    config = llm_config_from_settings()
    if not config.enabled or not config.route.api_key:
        raise ValueError("paid rubric requires the configured LLM route and API key")
    from src.core.llm.transport import build_transport
    from .recording import SingleAttemptEvalLLMClient
    from .rubric import LLMRubricJudge
    from src.core.llm import SpendAdmission

    with disposable_store() as factory:
        client = SingleAttemptEvalLLMClient(
            build_transport(config),
            SpendAdmission(
                config,
                session_factory=factory,
                clock=lambda: datetime.now(timezone.utc),
            ),
        )
        try:
            yield LLMRubricJudge(
                client,
                config=config,
                owner_prefix=f"eval-{uuid.uuid4().hex[:12]}",
            )
        finally:
            await client.aclose()


__all__ = ["disposable_store", "execute_live_case", "execute_scripted_case", "live_rubric_judge", "smoke_config", "tool_catalog_for_case"]

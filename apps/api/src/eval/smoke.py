"""Offline scripted clients driven through the real replay lifecycles."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from datetime import datetime, time, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.agent.registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
)
from src.agent.signal_tool_contract import (
    GET_FIELD_DESCRIPTION,
    GET_FIELD_SCHEMA,
    LIST_FIELDS_DESCRIPTION,
    LIST_FIELDS_SCHEMA,
)
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


class FixtureContractInvalid(ValueError):
    """A paid case asks for evidence its frozen tool surface cannot return."""


def _fixture_results(snapshots: tuple[SnapshotFile, ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        evidence.metadata
        for snapshot in snapshots
        for evidence in snapshot.evidence
        if evidence.metadata.get("fixture_kind") == "tool_result"
    )


def tool_catalog_for_case(
    case: CaseFile, snapshots: tuple[SnapshotFile, ...]
) -> tuple[ToolEntry, ...]:
    """Production signal schemas narrowed to tools backed by frozen results."""
    if case.case_id == "fact-publication-lookahead":
        return ()
    backed = {
        str(item.get("tool_name") or "") for item in _fixture_results(snapshots)
    }
    entries = (
        ToolEntry(
            name="list_fields",
            toolset="signals",
            schema=LIST_FIELDS_SCHEMA,
            handler=lambda _context, _arguments: {},
            description=LIST_FIELDS_DESCRIPTION,
            display_name="Xem danh mục chỉ báo",
            reads_external=False,
            effect=ToolEffect.READ,
            idempotency=ToolIdempotency.IDEMPOTENT,
            access=ToolAccess.STORE,
            content_trust=ContentTrust.TRUSTED_STRUCTURED,
            concurrency=ToolConcurrency.SERIALIZED,
            max_result_size_chars=32_000,
        ),
        ToolEntry(
            name="get_field",
            toolset="signals",
            schema=GET_FIELD_SCHEMA,
            handler=lambda _context, _arguments: {},
            description=GET_FIELD_DESCRIPTION,
            display_name="Đọc chỉ báo",
            reads_external=False,
            effect=ToolEffect.READ,
            idempotency=ToolIdempotency.IDEMPOTENT,
            access=ToolAccess.STORE,
            content_trust=ContentTrust.TRUSTED_STRUCTURED,
            concurrency=ToolConcurrency.SERIALIZED,
            is_async=False,
            max_result_size_chars=32_000,
        ),
    )
    return tuple(entry for entry in entries if entry.name in backed)


def validate_fixture_contract(
    case: CaseFile, snapshots: tuple[SnapshotFile, ...]
) -> None:
    """Fail before spend when a hard fact is absent from frozen tool results."""
    offered = {entry.name for entry in tool_catalog_for_case(case, snapshots)}
    results = [
        item.get("result")
        for item in _fixture_results(snapshots)
        if item.get("tool_name") in offered
        if isinstance(item.get("result"), Mapping)
    ]
    errors: list[str] = []
    for expectation in case.expectations:
        if expectation.kind != "figure":
            continue
        expected = float(expectation.params["value"])
        tolerance = float(expectation.params.get("tolerance", 0))
        unit = expectation.params.get("unit")
        reachable = any(
            isinstance(result.get("value"), (int, float))
            and abs(float(result["value"]) - expected) <= tolerance
            and (
                unit is None
                or str(result.get("unit") or "").casefold()
                == str(unit).casefold()
            )
            for result in results
        )
        if not reachable:
            errors.append(
                f"case {case.case_id!r}: unreachable hard figure "
                f"{expectation.params!r}"
            )
    if errors:
        raise FixtureContractInvalid("\n".join(errors))


def _script(
    case: CaseFile, snapshots: tuple[SnapshotFile, ...]
) -> tuple[list[Completion], tuple[ToolEntry, ...]]:
    answer = _answer(case)
    tools = tool_catalog_for_case(case, snapshots)
    if case.surface == "conversation":
        # Every Conversation snapshot except the deliberate lookahead trap has
        # get_field.  For the trap, a direct refusal is the correct trajectory.
        if case.case_id == "fact-publication-lookahead":
            return [Completion(model="eval-scripted-session", text=answer, usage=Usage(input_tokens=10, output_tokens=10))], ()
        call_name = "list_fields" if any(item.name == "list_fields" for item in tools) else tools[0].name
        return [
            Completion(model="eval-scripted-session", tool_calls=(ToolCall(id="field-1", name=call_name, arguments={}),), usage=Usage(input_tokens=10, output_tokens=2), finish_reason="tool_calls"),
            Completion(model="eval-scripted-session", text=answer, usage=Usage(input_tokens=10, output_tokens=10)),
        ], tools

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
    ], tools


async def execute_scripted_case(*, case: CaseFile, snapshots: tuple[SnapshotFile, ...], run_id: str, trial_index: int, mode: str, remaining_ceiling_usd: float) -> "EvalResult":
    if mode != "smoke":
        raise ValueError("the scripted executor is offline-smoke only")
    validate_fixture_contract(case, snapshots)
    script, tools = _script(case, snapshots)
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
                    tool_catalog=tool_catalog_for_case(case, snapshots),
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


__all__ = ["FixtureContractInvalid", "disposable_store", "execute_live_case", "execute_scripted_case", "live_rubric_judge", "smoke_config", "tool_catalog_for_case", "validate_fixture_contract"]

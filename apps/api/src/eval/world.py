"""A case-local, store-only fixture world behind real runtime contracts."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.agent import definitions, registry, toolsets
from src.agent.persistence import AgentPersistence
from src.alpha.models import (
    AgentThread,
    Analysis,
    AnalysisRun,
    LlmCallUsage,
)
from src.auth.models import User
from src.core.provider_access import (
    ProviderSourceAccessForbidden,
    store_only_execution,
)
from src.stocks.models import ListingRoster, ProviderSnapshot

from .contracts import CaseFile, SnapshotFile, canonical_json

SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]
StopReason = Callable[[], str | None]


@contextmanager
def resolved_surface_for_catalog(
    tool_catalog: Sequence[registry.ToolEntry],
) -> Iterator[definitions.ResolvedToolSurface]:
    """Resolve the exact fixture surface while restoring process globals.

    Eval identity must describe what the real lanes receive, including
    execution and safety policy. Installing the catalog through the production
    registry/resolver keeps this a projection of that owner instead of a second
    schema-only reconstruction.
    """
    previous_entries = registry.entries()
    selected: dict[str, list[str]] = {}
    previous_toolsets: dict[str, toolsets.Toolset | None] = {}
    for entry in tool_catalog:
        selected.setdefault(entry.toolset, []).append(entry.name)
    registry.clear()
    definitions.clear_cache()
    toolsets.clear_memo()
    try:
        for name, names in selected.items():
            previous_toolsets[name] = toolsets.TOOLSETS.get(name)
            toolsets.TOOLSETS[name] = {
                "description": "Case-local replay capability surface.",
                "tools": tuple(dict.fromkeys(names)),
            }
        for entry in tool_catalog:
            registry.register(
                replace(entry, check_fn=None, requires_env=())
            )
        yield definitions.resolve_tool_surface(tuple(selected), now=0.0)
    finally:
        registry.clear()
        for entry in previous_entries:
            registry.register(entry)
        for name, previous in previous_toolsets.items():
            if previous is None:
                toolsets.TOOLSETS.pop(name, None)
            else:
                toolsets.TOOLSETS[name] = previous
        definitions.clear_cache()
        toolsets.clear_memo()


class FixtureMiss(LookupError):
    """A declared tool had no frozen result for the arguments it received."""


class FixtureScopeViolation(PermissionError):
    """A fixture call tried to leave its case's trusted scope."""


class FixtureStoreNotEmpty(RuntimeError):
    """The supplied store is not a fresh case-local evaluation database."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FixtureWorld:
    """Install one case's rows and tools, restoring process globals on exit."""

    def __init__(
        self,
        *,
        case: CaseFile,
        snapshots: Sequence[SnapshotFile],
        session_factory: SessionFactory,
        tool_catalog: Sequence[registry.ToolEntry],
        clock: Clock = _utcnow,
        stop_reason: StopReason | None = None,
    ) -> None:
        self.case = case
        self.snapshots = tuple(snapshots)
        self.session_factory = session_factory
        self.tool_catalog = tuple(tool_catalog)
        self.clock = clock
        self.stop_reason = stop_reason
        self.store = AgentPersistence(session_factory=session_factory)
        self.user_id: int | None = None
        self.thread_id: Any = None
        self.provider_access_attempts: list[str] = []
        self.scope_violations: list[str] = []
        self._previous_entries: tuple[registry.ToolEntry, ...] = ()
        self._previous_toolsets: dict[str, toolsets.Toolset | None] = {}
        self._stack: ExitStack | None = None
        self._responses = self._fixture_responses()

    @property
    def toolsets(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(entry.toolset for entry in self.tool_catalog))

    @property
    def argument_allowlists(self) -> dict[str, frozenset[str]]:
        return {
            entry.name: frozenset((entry.schema.get("properties") or {}).keys())
            for entry in self.tool_catalog
        }

    def bind_thread(self, thread_id: Any) -> None:
        self.thread_id = thread_id

    def __enter__(self) -> "FixtureWorld":
        self._previous_entries = registry.entries()
        registry.clear()
        definitions.clear_cache()
        toolsets.clear_memo()
        selected_tools: dict[str, list[str]] = {}
        for entry in self.tool_catalog:
            selected_tools.setdefault(entry.toolset, []).append(entry.name)
        for name, tools in selected_tools.items():
            previous = toolsets.TOOLSETS.get(name)
            self._previous_toolsets[name] = previous
            toolsets.TOOLSETS[name] = {
                "description": (
                    "Case-local replay tools backed by this evaluation fixture."
                ),
                "tools": tuple(dict.fromkeys(tools)),
            }
        self._stack = ExitStack()
        self._stack.enter_context(store_only_execution())
        try:
            self._materialize()
            for entry in self.tool_catalog:
                registry.register(
                    replace(
                        entry,
                        handler=self._handler(entry.name),
                        check_fn=None,
                        requires_env=(),
                        is_async=True,
                    )
                )
            return self
        except BaseException:
            self._stack.close()
            self._stack = None
            self._restore_registry()
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._stack is not None:
            self._stack.close()
            self._stack = None
        self._restore_registry()

    def _restore_registry(self) -> None:
        registry.clear()
        for entry in self._previous_entries:
            registry.register(entry)
        for name, previous in self._previous_toolsets.items():
            if previous is None:
                toolsets.TOOLSETS.pop(name, None)
            else:
                toolsets.TOOLSETS[name] = previous
        self._previous_toolsets.clear()
        definitions.clear_cache()
        toolsets.clear_memo()

    def _fixture_responses(self) -> dict[tuple[str, str], Any]:
        responses: dict[tuple[str, str], Any] = {}
        for snapshot in self.snapshots:
            for evidence in snapshot.evidence:
                metadata = evidence.metadata
                if metadata.get("fixture_kind") != "tool_result":
                    continue
                name = str(metadata.get("tool_name") or "")
                arguments = metadata.get("arguments") or {}
                if not name or not isinstance(arguments, Mapping):
                    raise ValueError(
                        f"snapshot {snapshot.snapshot_id!r} has an invalid tool result"
                    )
                key = (name, canonical_json(dict(arguments)))
                if key in responses:
                    raise ValueError(f"duplicate fixture result for {name} {arguments}")
                result = metadata.get("result")
                if callable(result) and not inspect.iscoroutinefunction(result):
                    raise TypeError(
                        "fixture result callables must be async so cancellation "
                        "can unwind before case cleanup"
                    )
                responses[key] = result
        return responses

    def _handler(self, tool_name: str) -> Callable[..., Any]:
        async def invoke(context: registry.ToolContext, arguments: Mapping[str, Any]) -> Any:
            try:
                self._assert_scope(context, arguments)
                found, result = self._response_for(tool_name, arguments)
                if not found:
                    raise FixtureMiss(
                        f"no frozen result for {tool_name} with {dict(arguments)!r}"
                    )
                if isinstance(result, BaseException):
                    raise result
                if callable(result):
                    result = result(context, arguments)
                    if inspect.isawaitable(result):
                        pending = asyncio.create_task(result)
                        try:
                            while True:
                                done, _ = await asyncio.wait(
                                    {pending}, timeout=0.01
                                )
                                if pending in done:
                                    result = await pending
                                    break
                                if (
                                    self.stop_reason is not None
                                    and self.stop_reason() is not None
                                ):
                                    pending.cancel()
                                    await asyncio.gather(
                                        pending, return_exceptions=True
                                    )
                                    raise RuntimeError(
                                        f"fixture execution stopped: {self.stop_reason()}"
                                    )
                        except BaseException:
                            if not pending.done():
                                pending.cancel()
                                await asyncio.gather(pending, return_exceptions=True)
                            raise
                return result
            except ProviderSourceAccessForbidden as failure:
                self.provider_access_attempts.append(str(failure))
                raise

        return invoke

    def _response_for(
        self, tool_name: str, arguments: Mapping[str, Any]
    ) -> tuple[bool, Any]:
        key = (tool_name, canonical_json(dict(arguments)))
        if key in self._responses:
            return True, self._responses[key]

        without_nulls = {
            key: value for key, value in arguments.items() if value is not None
        }
        fallback = (tool_name, canonical_json(without_nulls))
        if fallback in self._responses:
            return True, self._responses[fallback]

        if tool_name == "get_field" and "symbol" in arguments:
            scoped = {key: value for key, value in arguments.items() if key != "symbol"}
            fallback = (tool_name, canonical_json(scoped))
            if fallback in self._responses:
                return True, self._responses[fallback]

        if tool_name == "list_fields" and arguments.get("axis"):
            fallback = (tool_name, canonical_json({}))
            result = self._responses.get(fallback)
            if isinstance(result, Mapping):
                axis = str(arguments["axis"])
                fields = [
                    item
                    for item in result.get("fields", [])
                    if isinstance(item, Mapping) and item.get("axis") == axis
                ]
                return True, {**result, "axis": axis, "count": len(fields), "fields": fields}

        return False, None

    def _assert_scope(
        self, context: registry.ToolContext, arguments: Mapping[str, Any]
    ) -> None:
        if self.case.surface == "conversation":
            if context.user_id != self.user_id or context.thread_id != self.thread_id:
                self._scope_failure("conversation identity left its fixture scope")
        else:
            if (
                context.symbol != self.case.input.symbol
                or context.trading_day != self.case.input.trading_day
            ):
                self._scope_failure("analysis identity left its fixture scope")

        allowed_entities = {
            evidence.entity.upper()
            for snapshot in self.snapshots
            for evidence in snapshot.evidence
        }
        supplied_symbol = arguments.get("symbol")
        if supplied_symbol is not None and str(supplied_symbol).upper() not in allowed_entities:
            self._scope_failure(f"symbol {supplied_symbol!r} is outside the case")
        for key in ("as_of", "trading_day", "date"):
            supplied = arguments.get(key)
            if supplied is None:
                continue
            expected: date = self.case.input.trading_day or self.case.as_of
            if str(supplied) != expected.isoformat():
                self._scope_failure(f"{key} {supplied!r} is outside the case")

    def _scope_failure(self, message: str) -> None:
        self.scope_violations.append(message)
        raise FixtureScopeViolation(message)

    def _materialize(self) -> None:
        with self.session_factory() as session:
            populated = [
                model.__tablename__
                for model in (
                    User,
                    AgentThread,
                    Analysis,
                    AnalysisRun,
                    LlmCallUsage,
                    ProviderSnapshot,
                    ListingRoster,
                )
                if session.scalar(select(func.count()).select_from(model))
            ]
            if populated:
                raise FixtureStoreNotEmpty(
                    "eval requires a fresh case-local store; found rows in "
                    + ", ".join(populated)
                )
            if self.case.surface == "conversation":
                context = self.case.user_context
                if context is None:
                    raise ValueError("a conversation eval case needs synthetic user context")
                user = User(
                    email=f"{context.synthetic_user_id}@eval.invalid",
                    hashed_password="eval-not-a-login",
                    full_name=context.display_name,
                )
                session.add(user)
                session.flush()
                self.user_id = int(user.id)

            for snapshot in self.snapshots:
                for evidence in snapshot.evidence:
                    metadata = evidence.metadata
                    kind = metadata.get("fixture_kind")
                    if kind == "provider_snapshot":
                        payload = metadata.get("payload")
                        if not isinstance(payload, Mapping):
                            raise ValueError("a provider snapshot fixture needs payload")
                        session.add(
                            ProviderSnapshot(
                                capability=evidence.capability,
                                symbol=evidence.entity.upper(),
                                source=evidence.source.value,
                                effective_at=evidence.effective_at,
                                observed_at=evidence.ingested_at or evidence.effective_at,
                                schema_version=int(metadata.get("schema_version") or 1),
                                payload=dict(payload),
                            )
                        )
                    elif kind == "listing_roster":
                        session.add(
                            ListingRoster(
                                symbol=evidence.entity.upper(),
                                exchange=str(metadata.get("exchange") or ""),
                                is_listed=True,
                                company_name=metadata.get("company_name"),
                                icb_code=metadata.get("icb_code"),
                                source=evidence.source.value,
                                observed_at=evidence.ingested_at or evidence.effective_at,
                            )
                        )
                    elif kind not in (None, "tool_result"):
                        raise ValueError(f"unknown fixture_kind {kind!r}")
            session.commit()


__all__ = [
    "FixtureMiss",
    "FixtureScopeViolation",
    "FixtureStoreNotEmpty",
    "FixtureWorld",
    "resolved_surface_for_catalog",
]

"""Runtime identity, derived from actual code rather than declared by hand.

Every eval artifact stamps what produced it. A stamp somebody has to remember
to update is a stamp that eventually lies, so each identity here is *derived*:

- **Code** from the Git checkout itself (SHA plus dirty state).
- **Prompt** from the rendered contract content and its version constants —
  the hash already moves when the prose moves without a version bump
  (``prompt.contract``), and this adds the Analysis loop's own version.
- **Tool catalog** from the resolved ``ToolSchema.as_wire()`` forms, so a
  description or parameter edit changes the digest automatically.
- **Model/config/pricing** from :func:`llm_config_from_settings`, never from a
  copy of it.
- **Provider capability** from the ownership table plus an executable adapter
  inventory read out of the adapter modules' source with ``ast`` — parsing,
  **never importing**: importing an adapter pulls pandas and a provider SDK,
  and deriving identity must not cost a credential check or a network packet.
  A declared cover without an executable adapter is reported as unavailable,
  never as an assumed fallback.

Nothing here probes a provider to learn anything.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from src.agent.prompt.contract import PROMPT_HASH, PROMPT_VERSION
from src.alpha.analysis_loop import LOOP_PROMPT_VERSION
from src.alpha.generation import PROMPT_VERSION as GENERATION_PROMPT_VERSION
from src.core.llm import ToolSchema
from src.core.llm.config import LLMConfig, Workload, llm_config_from_settings
from src.stocks.providers.contracts import (
    MARKET_SCHEMA_VERSION,
    SOURCE_OWNERSHIP_BY_CAPABILITY,
    Capability,
)


# ---------------------------------------------------------------------------
# Code


@dataclass(frozen=True)
class CodeStamp:
    """Which checkout produced a run."""

    git_sha: str
    dirty: bool

    def as_wire(self) -> dict[str, Any]:
        return {"git_sha": self.git_sha, "dirty": self.dirty}


def code_stamp(repo_root: Path | None = None) -> CodeStamp:
    """The real SHA and dirty state of the checkout running right now."""
    root = repo_root if repo_root is not None else _find_repo_root()
    sha = _git(root, ["rev-parse", "HEAD"])
    status = _git(root, ["status", "--porcelain"], allow_empty=True)
    return CodeStamp(git_sha=sha.strip(), dirty=bool(status.strip()))


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError(
        "code_stamp could not find the repository root; pass repo_root explicitly"
    )


def _git(root: Path, args: list[str], *, allow_empty: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {args[0]} failed in {root}: {result.stderr.strip()}"
        )
    if not allow_empty and not result.stdout.strip():
        raise RuntimeError(f"git {args[0]} answered nothing in {root}")
    return result.stdout


# ---------------------------------------------------------------------------
# Prompt


@dataclass(frozen=True)
class PromptIdentity:
    """What the model was actually told, identified two ways."""

    version: str
    contract_sha: str
    loop_version: str
    generation_version: str

    @property
    def digest(self) -> str:
        from .contracts import content_digest

        return content_digest(self.as_wire())

    def as_wire(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "contract_sha": self.contract_sha,
            "loop_version": self.loop_version,
            "generation_version": self.generation_version,
        }


def prompt_identity() -> PromptIdentity:
    """Identity of both lanes' prompt contracts, from their owners."""
    return PromptIdentity(
        version=PROMPT_VERSION,
        contract_sha=PROMPT_HASH,
        loop_version=LOOP_PROMPT_VERSION,
        generation_version=GENERATION_PROMPT_VERSION,
    )


# ---------------------------------------------------------------------------
# Tool catalog


@dataclass(frozen=True)
class ToolCatalogIdentity:
    """What tools a run's model could see, and what that surface hashed to."""

    catalog_digest: str
    names: tuple[str, ...]
    requested: tuple[str, ...]
    unavailable: tuple[str, ...]

    def as_wire(self) -> dict[str, Any]:
        return {
            "digest": self.catalog_digest,
            "names": list(self.names),
            "unavailable": list(self.unavailable),
        }


def tool_catalog_identity(
    schemas: Sequence[ToolSchema],
    *,
    requested: Sequence[str] | None = None,
    unavailable: Sequence[str] | None = None,
) -> ToolCatalogIdentity:
    """Digest the wire forms the model would actually receive.

    Taken over ``ToolSchema.as_wire()`` — the strict-mode restatement included —
    because that is what crossed to the route. A description edit therefore
    moves this digest without anyone bumping anything.
    """
    wanted = tuple(requested) if requested is not None else tuple(
        schema.name for schema in schemas
    )
    resolved_names = tuple(schema.name for schema in schemas)
    dropped = tuple(name for name in wanted if name not in set(resolved_names))
    missing = tuple(unavailable) if unavailable is not None else dropped
    from .contracts import content_digest

    digest = content_digest([schema.as_wire() for schema in schemas])
    return ToolCatalogIdentity(
        catalog_digest=digest,
        names=resolved_names,
        requested=wanted,
        unavailable=missing,
    )


# ---------------------------------------------------------------------------
# Model / config / pricing


def llm_identity(config: LLMConfig | None = None) -> dict[str, Any]:
    """The route, models, prices, and timeouts a run ran under.

    The credential is structurally unreachable here: ``LLMRoute`` excludes it
    from every representation, and only the fields named below are read.
    """
    resolved = config if config is not None else llm_config_from_settings()
    session_prices = resolved.prices_for(Workload.SESSION)
    batch_prices = resolved.prices_for(Workload.BATCH)

    def _prices(block: Any) -> dict[str, float]:
        return {
            "input": block.input,
            "cached_input": block.cached_input,
            "cache_write": block.cache_write,
            "output": block.output,
        }

    return {
        "session_model": resolved.model_for(Workload.SESSION),
        "batch_model": resolved.model_for(Workload.BATCH),
        "route_base_url": resolved.route.base_url,
        "streaming": resolved.route.streaming,
        "reasoning_history": resolved.route.reasoning_history,
        "prompt_cache_control": resolved.route.prompt_cache_control,
        "pricing_version": resolved.pricing.version,
        "pricing_effective_from": (
            resolved.pricing.effective_from.isoformat()
            if resolved.pricing.effective_from is not None
            else None
        ),
        "session_prices": _prices(session_prices),
        "batch_prices": _prices(batch_prices),
        "request_timeout_seconds": resolved.request_timeout_seconds,
        "route_breaker_enabled": resolved.route_breaker_enabled,
    }


# ---------------------------------------------------------------------------
# Provider capability ownership versus executable adapters

#: Adapter modules whose *source* declares the executable inventory.
ADAPTER_MODULES: tuple[str, ...] = ("fiinquant.py", "vnstock_provider.py")

#: The fetch methods each capability's protocol requires. Adapters satisfy the
#: protocols structurally rather than by inheritance, so the executable fact
#: is the presence of the method, resolved through the module's own ancestor
#: chain.
_METHOD_TO_CAPABILITY: Mapping[str, str] = MappingProxyType(
    {
        "fetch_market": "market",
        "fetch_market_history": "market",
        "fetch_index_history": "market_index",
        "fetch_valuation": "valuation",
        "fetch_reference": "reference",
        "fetch_listing_roster": "reference",
        "fetch_fundamentals": "fundamental",
        "fetch_corporate_actions": "corporate_action",
    }
)


@dataclass(frozen=True)
class ProviderCapabilityRow:
    """One capability: who owns it, and who can actually execute it."""

    capability: str
    main: str
    cover: str | None
    main_executable: bool
    cover_declared: bool
    cover_executable: bool

    def as_wire(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "main": self.main,
            "cover": self.cover,
            "main_executable": self.main_executable,
            "cover_declared": self.cover_declared,
            "cover_executable": self.cover_executable,
        }


@dataclass(frozen=True)
class ProviderCapabilityIdentity:
    capabilities: Mapping[str, ProviderCapabilityRow]
    inventory: Mapping[str, Mapping[str, tuple[str, ...]]]
    market_schema_version: int
    identity_digest: str

    def as_wire(self) -> dict[str, Any]:
        from .contracts import content_digest

        return {
            "capabilities": {
                key: row.as_wire() for key, row in sorted(self.capabilities.items())
            },
            "inventory": {
                source: {capability: list(classes) for capability, classes in sorted(by_cap.items())}
                for source, by_cap in sorted(self.inventory.items())
            },
            "market_schema_version": self.market_schema_version,
            "digest": self.identity_digest,
        }


def executable_adapter_inventory(
    providers_dir: Path | None = None,
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Which provider has an executable class for which capability.

    Derived by parsing adapter sources with ``ast`` — no import, so no pandas,
    no SDK, no credential probe. A class counts when the module's own ancestry
    gives it a capability's ``fetch_*`` method and a resolvable
    ``source = ProviderSource.X`` declaration.
    """
    if providers_dir is None:
        import src.stocks.providers as package

        providers_dir = Path(package.__file__).parent

    inventory: dict[str, dict[str, list[str]]] = {}
    for module_name in ADAPTER_MODULES:
        path = providers_dir / module_name
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        module_source_default = _declared_source(ast.iter_child_nodes(tree))

        for name, node in classes.items():
            methods = _inherited_methods(node, classes)
            capabilities = sorted(
                {_METHOD_TO_CAPABILITY[m] for m in methods if m in _METHOD_TO_CAPABILITY}
            )
            if not capabilities:
                continue
            source = _source_through_ancestry(node, classes, module_source_default)
            if source is None:
                continue
            by_capability = inventory.setdefault(source, {})
            for capability in capabilities:
                registered = by_capability.setdefault(capability, [])
                if name not in registered:
                    registered.append(name)

    return {
        source: {cap: tuple(classes) for cap, classes in sorted(by_cap.items())}
        for source, by_cap in inventory.items()
    }


def _inherited_methods(
    node: ast.ClassDef, classes: Mapping[str, ast.ClassDef]
) -> set[str]:
    """Every method reachable from ``node`` through bases named in this module."""
    seen_methods: set[str] = set()
    visited: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if current.name in visited:
            continue
        visited.add(current.name)
        for item in current.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seen_methods.add(item.name)
        for base in current.bases:
            base_name = (
                base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            )
            if base_name in classes and base_name not in visited:
                stack.append(classes[base_name])
    return seen_methods


def _source_through_ancestry(
    node: ast.ClassDef,
    classes: Mapping[str, ast.ClassDef],
    module_default: str | None,
) -> str | None:
    """The nearest ``source`` declaration on the class or its bases."""
    visited: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if current.name in visited:
            continue
        visited.add(current.name)
        declared = _declared_source(ast.iter_child_nodes(current))
        if declared is not None:
            return declared
        for base in current.bases:
            base_name = (
                base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            )
            if base_name in classes and base_name not in visited:
                stack.append(classes[base_name])
    return module_default


def _declared_source(nodes: Any) -> str | None:
    """Read ``source = ProviderSource.X`` out of AST assignment statements."""
    for node in nodes:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "source" and node.value is not None:
                return _provider_source_name(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "source":
                    return _provider_source_name(node.value)
    return None


def _provider_source_name(value: ast.expr) -> str | None:
    """``ProviderSource.X`` as written, matched against enum members by name.

    The AST carries the member's *name* (``FIINQUANT``); the enum's *value*
    is the lowercase wire form. Comparing case-insensitively keeps the two
    spellings from silently failing to meet.
    """
    if isinstance(value, ast.Attribute) and value.value.__class__ is ast.Name:
        if value.value.id == "ProviderSource":
            return value.attr.lower()
    return None


def provider_capability_identity(
    *,
    inventory: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    ownership: Mapping[Capability, Any] | None = None,
) -> ProviderCapabilityIdentity:
    """Ownership versus executability, per capability, plus one digest.

    With ``inventory=None`` the real adapter tree is parsed. A declared cover
    with no executable class is reported as exactly that — unavailable — which
    is the honest answer, and the one the plan table records for valuation.
    """
    resolved_inventory: dict[str, dict[str, tuple[str, ...]]] = {
        source: dict(by_cap)
        for source, by_cap in (
            inventory.items()
            if inventory is not None
            else executable_adapter_inventory().items()
        )
    }
    table = ownership if ownership is not None else SOURCE_OWNERSHIP_BY_CAPABILITY

    rows: dict[str, ProviderCapabilityRow] = {}
    for capability, owned in table.items():
        main = owned.main.value
        cover = owned.cover.value if owned.cover is not None else None
        rows[capability.value] = ProviderCapabilityRow(
            capability=capability.value,
            main=main,
            cover=cover,
            main_executable=bool(resolved_inventory.get(main, {}).get(capability.value)),
            cover_declared=cover is not None,
            cover_executable=(
                bool(resolved_inventory.get(cover, {}).get(capability.value))
                if cover is not None
                else False
            ),
        )

    from .contracts import content_digest

    digest = content_digest(
        {
            "capabilities": {
                key: row.as_wire() for key, row in sorted(rows.items())
            },
            "inventory": {
                source: {cap: sorted(classes) for cap, classes in by_cap.items()}
                for source, by_cap in resolved_inventory.items()
            },
            "market_schema_version": MARKET_SCHEMA_VERSION,
        }
    )
    return ProviderCapabilityIdentity(
        capabilities=MappingProxyType(rows),
        inventory=MappingProxyType(resolved_inventory),
        market_schema_version=MARKET_SCHEMA_VERSION,
        identity_digest=digest,
    )


__all__ = [
    "ADAPTER_MODULES",
    "CodeStamp",
    "PromptIdentity",
    "ProviderCapabilityIdentity",
    "ProviderCapabilityRow",
    "ToolCatalogIdentity",
    "code_stamp",
    "executable_adapter_inventory",
    "llm_identity",
    "prompt_identity",
    "provider_capability_identity",
    "tool_catalog_identity",
]

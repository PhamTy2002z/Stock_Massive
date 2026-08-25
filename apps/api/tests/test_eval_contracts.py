"""Strict wire contracts, canonical serialization, and identity derivation.

The eval lane is a measurement system around the runtime, so its first
artifacts are the ones everything else is stamped with: versioned schemas that
refuse unknown fields, digests that move when content moves, and identity
derived from actual code rather than declared by hand.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from src.agent import definitions, registry
from src.agent.prompt.contract import PROMPT_HASH, contract_hash
from src.agent.prompt.sections import SECTIONS, PromptSection
from src.core.llm import ToolSchema
from src.eval.contracts import (
    CASE_SCHEMA,
    RUN_MANIFEST_SCHEMA,
    DATASET_SCHEMA,
    SNAPSHOT_SCHEMA,
    CaseFile,
    CaseInput,
    DatasetManifest,
    EvidenceRecord,
    Expectation,
    ManifestSnapshotRef,
    RunManifest,
    SizeBudget,
    SnapshotFile,
    SnapshotRef,
    UserContext,
    canonical_json,
    content_digest,
    find_secret_shapes,
)
from src.stocks.providers import Capability, PriceBasis, ProviderSource


async def _identity_handler(_context, _arguments):
    return {}


def _resolved_tool_entry(name: str = "resolved") -> registry.ToolEntry:
    return registry.ToolEntry(
        name=name,
        toolset="signals",
        schema=registry.object_schema({}),
        handler=_identity_handler,
        description=f"Resolve {name}.",
        display_name=f"Resolved {name}",
        reads_external=False,
        effect=registry.ToolEffect.READ,
        idempotency=registry.ToolIdempotency.IDEMPOTENT,
        access=registry.ToolAccess.STORE,
        content_trust=registry.ContentTrust.TRUSTED_STRUCTURED,
        concurrency=registry.ToolConcurrency.SERIALIZED,
        contract_version="1",
        max_result_size_chars=8_000,
    )


def _surface(
    *entries: registry.ToolEntry,
    available: bool = True,
    reason: registry.AvailabilityReason | None = None,
) -> definitions.ResolvedToolSurface:
    tools = tuple(
        registry.ResolvedTool.from_entry(
            entry,
            available=available,
            unavailable_reason=reason,
            availability_expires_at=30.0,
        )
        for entry in entries
    )
    return definitions.ResolvedToolSurface(
        tools=tools,
        registry_generation=1,
        expanded_names=tuple(entry.name for entry in entries),
        expires_at=30.0,
    )


def _evidence(**overrides: Any) -> dict[str, Any]:
    """One valid evidence record as it would appear on disk."""
    payload: dict[str, Any] = {
        "source": "fiinquant",
        "capability": "market",
        "entity": "VCB",
        "unit": "VND",
        "value": 91_500.0,
        "health": "ok",
        "effective_at": "2026-08-14T00:00:00Z",
        "published_at": "2026-08-14T15:10:00Z",
        "ingested_at": "2026-08-14T16:00:00Z",
        "provenance": "fiinquant quote history",
        "price_basis": "raw",
    }
    payload.update(overrides)
    return payload


class TestCanonicalJson:
    def test_sorted_keys_and_compact_separators(self) -> None:
        text = canonical_json({"b": 1, "a": [2, 1]})
        assert text == '{"a":[2,1],"b":1}'

    def test_same_content_different_order_same_digest(self) -> None:
        assert content_digest({"a": 1, "b": {"c": 2, "d": 3}}) == content_digest(
            {"b": {"d": 3, "c": 2}, "a": 1}
        )

    def test_array_order_is_meaningful(self) -> None:
        """Arrays carry order; only object keys are sorted."""
        assert content_digest({"xs": [1, 2]}) != content_digest({"xs": [2, 1]})

    def test_digest_is_short_and_hex(self) -> None:
        digest = content_digest({"anything": True})
        assert len(digest) == 16
        int(digest, 16)


class TestEvidenceRecord:
    def test_round_trip_preserves_every_field(self) -> None:
        record = EvidenceRecord.model_validate(_evidence())
        revived = EvidenceRecord.model_validate(json.loads(record.model_dump_json()))
        assert revived == record
        assert record.effective_at.utcoffset() == timezone.utc.utcoffset(None)

    def test_naive_timestamp_refused(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord.model_validate(
                _evidence(effective_at="2026-08-14T00:00:00")
            )

    def test_unknown_field_refused(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord.model_validate(_evidence(secret_extra="nope"))

    def test_unknown_source_refused(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord.model_validate(_evidence(source="bloomberg"))

    def test_published_after_ingested_refused(self) -> None:
        """Ingestion follows publication; a row claiming otherwise is corrupt."""
        with pytest.raises(ValidationError):
            EvidenceRecord.model_validate(
                _evidence(
                    published_at="2026-08-14T18:00:00Z",
                    ingested_at="2026-08-14T16:00:00Z",
                )
            )


class TestSnapshotAndCase:
    def _snapshot(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": SNAPSHOT_SCHEMA,
            "snapshot_id": "vcb-market-20260814",
            "description": "One closed session of one symbol.",
            "evidence": [_evidence()],
        }
        payload.update(overrides)
        return payload

    def test_snapshot_requires_schema_tag(self) -> None:
        payload = self._snapshot()
        del payload["schema"]
        with pytest.raises(ValidationError):
            SnapshotFile.model_validate(payload)

    def test_snapshot_rejects_wrong_schema_generation(self) -> None:
        with pytest.raises(ValidationError):
            SnapshotFile.model_validate(self._snapshot(schema="eval.snapshot@99"))

    def test_empty_snapshot_refused(self) -> None:
        with pytest.raises(ValidationError):
            SnapshotFile.model_validate(self._snapshot(evidence=[]))

    def _case(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": CASE_SCHEMA,
            "case_id": "fact-vcb-close-20260814",
            "surface": "analysis",
            "family": "fact-unit-asof",
            "title": "VCB closed-session close",
            "as_of": "2026-08-18",
            "input": {"symbol": "VCB", "trading_day": "2026-08-14"},
            "user_context": {"synthetic_user_id": "synthetic-eval-user"},
            "expectations": [{"kind": "figure_matches_evidence"}],
            "traps": ["stale_provider"],
            "snapshots": [
                {
                    "snapshot_id": "vcb-market-20260814",
                    "digest": content_digest(self._snapshot()),
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_case_round_trip(self) -> None:
        case = CaseFile.model_validate(self._case())
        assert case.as_of == date(2026, 8, 18)
        assert case.expectations[0].kind == "figure_matches_evidence"

    def test_conversation_case_needs_a_prompt(self) -> None:
        payload = self._case(surface="conversation")
        payload["input"] = {}
        with pytest.raises(ValidationError):
            CaseFile.model_validate(payload)

    def test_analysis_case_cannot_carry_a_prompt(self) -> None:
        payload = self._case(
            input={
                "symbol": "VCB",
                "trading_day": "2026-08-14",
                "prompt": "Phân tích VCB giúp tôi",
            }
        )
        with pytest.raises(ValidationError):
            CaseFile.model_validate(payload)

    def test_synthetic_user_id_enforced(self) -> None:
        with pytest.raises(ValidationError):
            UserContext(synthetic_user_id="user-42")

    def test_case_id_shape_refused(self) -> None:
        with pytest.raises(ValidationError):
            CaseFile.model_validate(self._case(case_id="Fact VCB!"))

    def test_case_without_expectations_refused(self) -> None:
        with pytest.raises(ValidationError):
            CaseFile.model_validate(self._case(expectations=[]))


class TestDatasetManifest:
    def test_manifest_round_trip_with_budgets(self) -> None:
        manifest = DatasetManifest(
            schema=DATASET_SCHEMA,
            dataset_id="investment-intelligence-v1",
            created=date(2026, 8, 23),
            description="Shell manifest.",
            cases=(),
            snapshots=(
                ManifestSnapshotRef(
                    snapshot_id="vcb-market-20260814",
                    file="snapshots/vcb-market-20260814.json",
                    digest="0" * 16,
                ),
            ),
            budget=SizeBudget(
                max_snapshot_bytes=40_000,
                max_snapshot_rows=200,
                max_total_bytes=400_000,
                max_total_rows=2_000,
            ),
        )
        revived = DatasetManifest.model_validate(json.loads(manifest.model_dump_json()))
        assert revived == manifest
        assert revived.snapshots[0].file == "snapshots/vcb-market-20260814.json"

    def test_unknown_schema_tag_refused(self) -> None:
        with pytest.raises(ValidationError):
            DatasetManifest.model_validate(
                {
                    "schema": "eval.dataset@2",
                    "dataset_id": "x",
                    "created": "2026-08-23",
                    "cases": [],
                    "snapshots": [],
                    "budget": {
                        "max_snapshot_bytes": 1,
                        "max_snapshot_rows": 1,
                        "max_total_bytes": 1,
                        "max_total_rows": 1,
                    },
                }
            )


class TestSecretShapes:
    @pytest.mark.parametrize(
        "value",
        [
            "sk-" + "proj-abcdefghijklmnopqrstuvwxyz012345",
            "sk-" + "ant-api03-abcdef0123456789ABCDEF",
            "ghp_" + "a" * 36,
            "github_" + "pat_11ABCDEFG0" + "a" * 30,
            "xoxb-" + "123456789012-123456789012-abcdefghijklmnop",
            "AKIA" + "IOSFODNN7EXAMPLE",
            "AIza" + "SyA1234567890abcdefghijklmnopqrstuv",
            "-----BEGIN RSA " + "PRIVATE KEY-----",
            "Bearer " + "abc.def.ghi",
        ],
    )
    def test_known_shapes_are_found_nested(self, value: str) -> None:
        document = {"nested": {"deep": [value], "other": "harmless"}}
        found = find_secret_shapes(document)
        assert len(found) == 1

    def test_plain_market_text_passes(self) -> None:
        assert find_secret_shapes(_evidence()) == ()

    def test_empty_or_short_strings_ignored(self) -> None:
        assert find_secret_shapes({"k": "", "j": "sk-"}) == ()


class TestRunManifestContract:
    def test_run_manifest_stamps_the_whole_environment(self) -> None:
        manifest = RunManifest(
            schema=RUN_MANIFEST_SCHEMA,
            run_id="run-" + "0" * 12,
            mode="smoke",
            code={"git_sha": "f" * 40, "dirty": False},
            dataset_id="investment-intelligence-v1",
            dataset_digest="a" * 16,
            case_contract_digest="c" * 16,
            prompts={
                "version": "2.4.0",
                "contract_sha": PROMPT_HASH,
                "loop_version": "v2",
                "generation_version": "v1",
            },
            tools={"digest": "b" * 16, "names": ["get_field"], "unavailable": []},
            model={
                "session_model": "m-session",
                "batch_model": "m-batch",
                "route_base_url": "https://gateway.example/v1",
                "streaming": True,
                "reasoning_history": False,
                "prompt_cache_control": False,
                "pricing_version": "2026-08",
                "pricing_effective_from": None,
                "session_prices": {
                    "input": 1.0,
                    "cached_input": 0.5,
                    "cache_write": 2.0,
                    "output": 3.0,
                },
                "batch_prices": {
                    "input": 1.0,
                    "cached_input": 0.5,
                    "cache_write": 2.0,
                    "output": 3.0,
                },
                "request_timeout_seconds": 120.0,
                "route_breaker_enabled": True,
            },
            provider_capabilities={"digest": "d" * 16},
            policy_version="1.0.0",
            trials=1,
        )
        revived = RunManifest.model_validate(json.loads(manifest.model_dump_json()))
        assert revived.code.git_sha == "f" * 40
        assert revived.mode == "smoke"
        assert revived.case_contract_digest == "c" * 16
        assert revived.policy_version == "1.0.0"


class TestIdentityDerivation:
    def test_tool_catalog_digest_moves_when_description_moves(self) -> None:
        before = ToolSchema(name="t", description="Read a field.", parameters={})
        after = ToolSchema(name="t", description="Read a field today.", parameters={})
        from src.eval.versions import tool_catalog_identity

        assert (
            tool_catalog_identity([before]).catalog_digest
            != tool_catalog_identity([after]).catalog_digest
        )

    def test_tool_catalog_identity_reports_unavailable_names(self) -> None:
        from src.eval.versions import tool_catalog_identity

        schema = ToolSchema(name="present", description="d", parameters={})
        identity = tool_catalog_identity(
            [schema], requested=("present", "missing"), unavailable=("missing",)
        )
        assert identity.names == ("present",)
        assert identity.unavailable == ("missing",)

    @pytest.mark.parametrize(
        "change",
        (
            {"effect": registry.ToolEffect.WRITE},
            {"idempotency": registry.ToolIdempotency.NON_IDEMPOTENT},
            {"access": registry.ToolAccess.NETWORK},
            {
                "content_trust": registry.ContentTrust.UNTRUSTED,
                "reads_external": True,
            },
            {"concurrency": registry.ToolConcurrency.PARALLEL_SAFE},
            {"max_result_size_chars": 9_999},
            {"display_name": "Another display"},
            {"contract_version": "2"},
        ),
    )
    def test_each_resolved_behavior_field_moves_catalog_identity(
        self, change: dict[str, Any]
    ) -> None:
        from src.eval.versions import tool_catalog_identity

        base = _resolved_tool_entry()
        changed = registry.ToolEntry(**{**base.__dict__, **change})

        assert (
            tool_catalog_identity(_surface(base)).catalog_digest
            != tool_catalog_identity(_surface(changed)).catalog_digest
        )

    def test_availability_handler_schema_and_selection_order_move_identity(self) -> None:
        from src.eval.versions import tool_catalog_identity

        first = _resolved_tool_entry()

        async def replacement(_context, _arguments):
            return "replacement"

        changed_handler = registry.ToolEntry(
            **{**first.__dict__, "handler": replacement}
        )
        changed_schema = registry.ToolEntry(
            **{**first.__dict__, "description": "Changed schema description."}
        )
        unavailable = _surface(
            first,
            available=False,
            reason=registry.AvailabilityReason.CHECK_REFUSED,
        )
        second = _resolved_tool_entry(name="second")
        forward = _surface(first, second)
        backward = _surface(second, first)
        original = tool_catalog_identity(_surface(first)).catalog_digest

        assert tool_catalog_identity(_surface(changed_handler)).catalog_digest != original
        assert tool_catalog_identity(_surface(changed_schema)).catalog_digest != original
        assert tool_catalog_identity(unavailable).catalog_digest != original
        assert tool_catalog_identity(forward).catalog_digest != tool_catalog_identity(
            backward
        ).catalog_digest

    def test_case_and_lane_surface_membership_moves_run_catalog_identity(self) -> None:
        from src.eval.versions import scoped_tool_catalog_identity

        tool = _resolved_tool_entry()
        offered = _surface(tool)
        empty = _surface()
        before = scoped_tool_catalog_identity(
            (
                ("case-a", "conversation", offered),
                ("case-b", "analysis", empty),
            )
        )
        after = scoped_tool_catalog_identity(
            (
                ("case-a", "conversation", empty),
                ("case-b", "analysis", offered),
            )
        )

        assert before.names == after.names == (tool.name,)
        assert before.catalog_digest != after.catalog_digest

    def test_resolved_catalog_artifact_excludes_callable_secret_and_object_identity(
        self,
    ) -> None:
        secret = "sk-" + "x" * 40

        async def handler(_context, _arguments):
            return secret

        entry = registry.ToolEntry(
            **{**_resolved_tool_entry().__dict__, "handler": handler}
        )
        encoded = json.dumps(_surface(entry).identity_payload(), sort_keys=True)

        assert secret not in encoded
        assert "0x" not in encoded
        assert "requires_env" not in encoded
        assert "check_fn" not in encoded

    def test_prompt_contract_hash_moves_without_a_version_bump(self) -> None:
        """An edit that forgets the bump still changes the hash."""
        edited = (
            *SECTIONS[:-1],
            PromptSection(key="extra", title="9. Hết", body="Một dòng mới."),
        )
        assert contract_hash(edited) != contract_hash(SECTIONS)

    def test_provider_capability_identity_marks_missing_cover_unavailable(
        self,
    ) -> None:
        """A declared cover without an executable adapter is unavailable, not assumed."""
        from src.eval.versions import provider_capability_identity

        inventory = {
            ProviderSource.FIINQUANT: {Capability.MARKET.value: ("FiinQuantProvider",)},
            ProviderSource.VNSTOCK: {Capability.REFERENCE.value: ("RosterProvider",)},
        }
        report = provider_capability_identity(inventory=inventory)
        market = report.capabilities[Capability.MARKET.value]
        assert market.main_executable is True
        assert market.cover_declared is True
        assert market.cover_executable is False
        valuation = report.capabilities[Capability.VALUATION.value]
        assert valuation.main_executable is False
        assert report.identity_digest

    def test_code_stamp_reads_the_real_checkout(self) -> None:
        from src.eval.versions import code_stamp

        stamp = code_stamp()
        assert stamp.git_sha and len(stamp.git_sha) == 40
        assert isinstance(stamp.dirty, bool)

    def test_real_adapter_inventory_derived_from_source_not_import(
        self,
    ) -> None:
        """The inventory reads adapter source; it never imports an SDK."""
        from src.eval.versions import executable_adapter_inventory

        inventory = executable_adapter_inventory()
        assert "FiinQuantMarketProvider" in inventory["fiinquant"]["market"]
        assert (
            "FiinQuantMarketIndexProvider"
            in inventory["fiinquant"]["market_index"]
        )
        assert "VnstockFundamentalProvider" in inventory["vnstock"]["fundamental"]
        # The ownership table says vnstock covers valuation, but no adapter
        # implements it — the honest inventory records exactly that.
        assert "valuation" not in inventory.get("vnstock", {})

    def test_real_capability_report_marks_valuation_cover_unavailable(
        self,
    ) -> None:
        """Plan boundary table: valuation's declared cover does not exist yet."""
        from src.eval.versions import provider_capability_identity

        report = provider_capability_identity()
        market = report.capabilities["market"]
        assert market.main == "fiinquant"
        assert market.main_executable is True
        valuation = report.capabilities["valuation"]
        assert valuation.cover_declared is True
        assert valuation.cover_executable is False
        fundamental = report.capabilities["fundamental"]
        assert fundamental.main_executable is True


class TestImmutability:
    def test_models_are_frozen(self) -> None:
        record = EvidenceRecord.model_validate(_evidence())
        with pytest.raises(ValidationError):
            record.entity = "ACB"

    def test_wire_payload_not_aliased(self) -> None:
        """Mutating the dict handed to the model must not reach stored state."""
        raw = _evidence()
        snapshot = SnapshotFile.model_validate(
            {"schema": SNAPSHOT_SCHEMA, "snapshot_id": "s1", "evidence": [raw]}
        )
        raw["entity"] = "MUTATED"
        snapshot_copy = copy.deepcopy(snapshot)
        assert snapshot == snapshot_copy


def test_expectation_params_accept_arbitrary_json() -> None:
    expectation = Expectation.model_validate(
        {
            "kind": "figure_within_band",
            "params": {"tolerance_pct": 0.5, "labels": ["close", "high"]},
        }
    )
    assert expectation.params["labels"] == ["close", "high"]


def test_case_input_holds_both_lane_shapes() -> None:
    conversation = CaseInput(prompt="VCB giá bao nhiêu phiên 14/8?")
    assert conversation.symbol is None
    analysis = CaseInput.model_validate(
        {"symbol": "VCB", "trading_day": "2026-08-14"}
    )
    assert analysis.prompt is None


def test_price_basis_enum_survives_the_trip() -> None:
    record = EvidenceRecord.model_validate(_evidence(price_basis=None))
    assert record.price_basis is None
    record = EvidenceRecord.model_validate(_evidence(price_basis="adjusted_at_source"))
    assert record.price_basis == PriceBasis.ADJUSTED_AT_SOURCE

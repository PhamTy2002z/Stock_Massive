"""Digest, temporal, reference, size, and mutation validation of a dataset.

Every test here encodes one way a frozen dataset could lie: an edited snapshot,
evidence the runtime could not have known at ``as_of``, a budget quietly
exceeded, or a secret that slipped into a fixture. The loader's job is to
refuse all of them, before spend, with every violation named at once.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.eval.contracts import (
    DATASET_SCHEMA,
    SNAPSHOT_SCHEMA,
    SizeBudget,
    content_digest,
)
from src.eval.dataset import DatasetInvalid, LoadedDataset, load_dataset

BUDGET = dict(
    max_snapshot_bytes=4_000,
    max_snapshot_rows=20,
    max_total_bytes=8_000,
    max_total_rows=40,
)


def _evidence(**overrides: Any) -> dict[str, Any]:
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


def _snapshot(snapshot_id: str = "vcb-market", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "evidence": [_evidence()],
    }
    payload.update(overrides)
    return payload


def _case(case_id: str, snapshot_ids: list[str], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "eval.case@1",
        "case_id": case_id,
        "surface": "analysis",
        "family": "fact-unit-asof",
        "title": case_id,
        "as_of": "2026-08-18",
        "input": {"symbol": "VCB", "trading_day": "2026-08-14"},
        "expectations": [{"kind": "figure_matches_evidence"}],
        "snapshots": [
            {"snapshot_id": sid, "digest": content_digest(_snapshot(sid))}
            for sid in snapshot_ids
        ],
    }
    payload.update(overrides)
    return payload


def _case_over(case_id: str, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """A case pinned to exactly the snapshot documents given, whatever they hold."""
    case = _case(case_id, [s["snapshot_id"] for s in snapshots])
    case["snapshots"] = [
        {"snapshot_id": s["snapshot_id"], "digest": content_digest(s)}
        for s in snapshots
    ]
    return case


def _write_dataset(
    root: Path,
    *,
    cases: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    extra_case_files: list[dict[str, Any]] | None = None,
    extra_snapshot_files: list[dict[str, Any]] | None = None,
    budget: dict[str, int] | None = None,
    manifest_overrides: dict[str, Any] | None = None,
) -> Path:
    (root / "cases").mkdir(parents=True)
    (root / "snapshots").mkdir(parents=True)

    manifest: dict[str, Any] = {
        "schema": DATASET_SCHEMA,
        "dataset_id": "test-dataset-v1",
        "created": "2026-08-23",
        "description": "Written by a test.",
        "cases": [
            {
                "case_id": c["case_id"],
                "file": f"cases/{c['case_id']}.json",
                "digest": content_digest(c),
            }
            for c in cases
        ],
        "snapshots": [
            {
                "snapshot_id": s["snapshot_id"],
                "file": f"snapshots/{s['snapshot_id']}.json",
                "digest": content_digest(s),
            }
            for s in snapshots
        ],
        "budget": budget or BUDGET,
    }
    manifest.update(manifest_overrides or {})

    for c in cases + (extra_case_files or []):
        (root / "cases" / f"{c['case_id']}.json").write_text(json.dumps(c))
    for s in snapshots + (extra_snapshot_files or []):
        (root / "snapshots" / f"{s['snapshot_id']}.json").write_text(json.dumps(s))
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def _load(root: Path) -> LoadedDataset:
    return load_dataset(root)


class TestHappyPath:
    def test_loading_twice_yields_identical_digests(self, tmp_path: Path) -> None:
        _write_dataset(
            tmp_path,
            cases=[_case("c1", ["s1"])],
            snapshots=[_snapshot("s1")],
        )
        first = _load(tmp_path)
        second = _load(tmp_path)
        assert first.dataset_digest == second.dataset_digest
        assert first.case_digest("c1") == second.case_digest("c1")
        assert first.snapshot_digest("s1") == second.snapshot_digest("s1")

    def test_shared_snapshot_resolves_once_for_both_cases(
        self, tmp_path: Path
    ) -> None:
        """One digest serves every referencing case; there is no per-case copy."""
        shared = _snapshot("shared")
        _write_dataset(
            tmp_path,
            cases=[_case("c1", ["shared"]), _case("c2", ["shared"])],
            snapshots=[shared],
        )
        loaded = _load(tmp_path)
        assert loaded.snapshot_digest("shared")
        assert len(loaded.snapshots) == 1
        assert {pin.snapshot_id for pin in loaded.cases["c1"].snapshots} == {"shared"}
        assert {pin.snapshot_id for pin in loaded.cases["c2"].snapshots} == {"shared"}

    def test_empty_dataset_is_a_valid_shell(self, tmp_path: Path) -> None:
        _write_dataset(tmp_path, cases=[], snapshots=[])
        loaded = _load(tmp_path)
        assert loaded.dataset_digest
        assert loaded.errors == ()

    def test_disk_pretty_printing_does_not_change_digests(
        self, tmp_path: Path
    ) -> None:
        _write_dataset(
            tmp_path, cases=[_case("c1", ["s1"])], snapshots=[_snapshot("s1")]
        )
        compact = _load(tmp_path).dataset_digest

        # Rewrite the same content indented; identity must not move.
        case_path = tmp_path / "cases" / "c1.json"
        case_path.write_text(json.dumps(json.loads(case_path.read_text()), indent=2))
        assert _load(tmp_path).dataset_digest == compact


class TestMutationRefusal:
    def test_changed_snapshot_value_without_digest_update_refused(
        self, tmp_path: Path
    ) -> None:
        root = _write_dataset(
            tmp_path, cases=[_case("c1", ["s1"])], snapshots=[_snapshot("s1")]
        )
        # Edit the file after the manifest stamped it: the fixture and its
        # claim must move together or not at all.
        path = root / "snapshots" / "s1.json"
        edited = json.loads(path.read_text())
        edited["evidence"][0]["value"] = 99_999.0
        path.write_text(json.dumps(edited))

        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any(
            "s1" in e and "digest" in e for e in excinfo.value.errors
        )

    def test_edited_case_without_digest_update_refused(self, tmp_path: Path) -> None:
        case = _case("c1", [])
        root = _write_dataset(tmp_path, cases=[case], snapshots=[])
        path = root / "cases" / "c1.json"
        edited = json.loads(path.read_text())
        edited["title"] = "Changed under someone's feet"
        path.write_text(json.dumps(edited))
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any("c1" in e for e in excinfo.value.errors)


class TestTemporalValidation:
    def test_publication_after_as_of_refused(self, tmp_path: Path) -> None:
        late = _snapshot(
            evidence=[
                _evidence(
                    published_at="2026-08-19T15:00:00Z",
                    ingested_at="2026-08-19T16:00:00Z",
                )
            ]
        )
        _write_dataset(tmp_path, cases=[_case_over("c1", [late])], snapshots=[late])
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(tmp_path)
        assert any("published_at" in e and "as_of" in e for e in excinfo.value.errors)

    def test_post_as_of_publication_allowed_when_marked_trap(self, tmp_path: Path) -> None:
        late = _snapshot(
            evidence=[
                _evidence(
                    published_at="2026-08-19T15:00:00Z",
                    ingested_at="2026-08-19T16:00:00Z",
                    available_after_as_of=True,
                    health="stale",
                )
            ]
        )
        _write_dataset(
            tmp_path,
            cases=[{**_case_over("c1", [late]), "traps": ["publication_after_as_of"]}],
            snapshots=[late],
        )
        assert _load(tmp_path).errors == ()

    def test_ingestion_after_as_of_refused(self, tmp_path: Path) -> None:
        late = _snapshot(evidence=[_evidence(ingested_at="2026-08-20T00:00:00Z")])
        _write_dataset(tmp_path, cases=[_case_over("c1", [late])], snapshots=[late])
        with pytest.raises(DatasetInvalid):
            _load(tmp_path)

    def test_effective_after_as_of_refused_even_when_marked(self, tmp_path: Path) -> None:
        future = _snapshot(
            evidence=[
                _evidence(
                    effective_at="2026-08-25T00:00:00Z", available_after_as_of=True
                )
            ]
        )
        _write_dataset(tmp_path, cases=[_case_over("c1", [future])], snapshots=[future])
        with pytest.raises(DatasetInvalid):
            _load(tmp_path)

    def test_as_of_boundary_is_inclusive(self, tmp_path: Path) -> None:
        """Evidence published exactly on as_of was knowable that day."""
        edge = _snapshot(
            evidence=[
                _evidence(
                    published_at="2026-08-18T09:00:00Z",
                    ingested_at="2026-08-18T10:00:00Z",
                )
            ]
        )
        _write_dataset(tmp_path, cases=[_case_over("c1", [edge])], snapshots=[edge])
        assert _load(tmp_path).errors == ()


class TestReferenceValidation:
    def test_missing_referenced_snapshot_refused(self, tmp_path: Path) -> None:
        case = _case("c1", ["ghost"])
        root = _write_dataset(tmp_path, cases=[case], snapshots=[])
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any("ghost" in e for e in excinfo.value.errors)

    def test_orphan_snapshot_file_refused(self, tmp_path: Path) -> None:
        _write_dataset(
            tmp_path,
            cases=[],
            snapshots=[],
            extra_snapshot_files=[_snapshot("unreferenced")],
        )
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(tmp_path)
        assert any("orphan" in e.lower() for e in excinfo.value.errors)

    def test_orphan_case_file_refused(self, tmp_path: Path) -> None:
        _write_dataset(
            tmp_path,
            cases=[],
            snapshots=[],
            extra_case_files=[_case("stray", [])],
        )
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(tmp_path)
        assert any("orphan" in e.lower() for e in excinfo.value.errors)

    def test_unknown_schema_tag_refused(self, tmp_path: Path) -> None:
        stray = _snapshot("odd")
        stray["schema"] = "eval.snapshot@7"
        root = _write_dataset(tmp_path, cases=[], snapshots=[stray])
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any("schema" in e for e in excinfo.value.errors)

    def test_duplicate_snapshot_ids_refused(self, tmp_path: Path) -> None:
        first = _snapshot("dup")
        second = _snapshot("dup", evidence=[_evidence(entity="ACB")])
        root = _write_dataset(
            tmp_path,
            cases=[_case("c1", ["dup"])],
            snapshots=[first, second],
        )
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any("duplicate" in e.lower() for e in excinfo.value.errors)


class TestSizeBudgets:
    def test_snapshot_row_budget_names_the_owner(self, tmp_path: Path) -> None:
        fat = _snapshot("fat", evidence=[_evidence()] * 21)
        root = _write_dataset(tmp_path, cases=[_case_over("c1", [fat])], snapshots=[fat])
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any(
            "fat" in e and "rows" in e for e in excinfo.value.errors
        )

    def test_snapshot_byte_budget_identifies_the_owning_case(
        self, tmp_path: Path
    ) -> None:
        heavy_note = "x" * 5_000
        heavy = _snapshot(
            "heavy", evidence=[_evidence(metadata={"note": heavy_note})]
        )
        root = _write_dataset(
            tmp_path, cases=[_case_over("c1", [heavy])], snapshots=[heavy]
        )
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any(
            "heavy" in e and "bytes" in e and "c1" in e for e in excinfo.value.errors
        )

    def test_total_row_budget_refuses_across_snapshots(self, tmp_path: Path) -> None:
        rows_each = 11
        s1 = _snapshot("s1", evidence=[_evidence()] * rows_each)
        s2 = _snapshot("s2", evidence=[_evidence()] * rows_each)
        root = _write_dataset(
            tmp_path,
            cases=[_case_over("c1", [s1]), _case_over("c2", [s2])],
            snapshots=[s1, s2],
            budget={**BUDGET, "max_total_rows": 20},
        )
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any("total" in e.lower() for e in excinfo.value.errors)

    def test_within_budget_passes(self, tmp_path: Path) -> None:
        s1 = _snapshot("s1", evidence=[_evidence()] * 3)
        root = _write_dataset(
            tmp_path, cases=[_case_over("c1", [s1])], snapshots=[s1]
        )
        assert _load(root).errors == ()


class TestSecretRejection:
    def test_credential_shape_anywhere_refused_before_spend(self, tmp_path: Path) -> None:
        leaked = _snapshot(
            evidence=[
                _evidence(
                    provenance="sk-" + "proj-abcdefghijklmnopqrstuvwxyz012345"
                )
            ]
        )
        root = _write_dataset(
            tmp_path, cases=[_case_over("c1", [leaked])], snapshots=[leaked]
        )
        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        assert any("credential" in e.lower() for e in excinfo.value.errors)


class TestFailTogetherPreflight:
    def test_every_violation_reported_at_once(self, tmp_path: Path) -> None:
        """One broken case must not hide the next one."""
        broken_snapshot = _snapshot("bad-temporal")
        broken_snapshot["evidence"][0]["published_at"] = "2026-08-19T15:00:00Z"
        broken_snapshot["evidence"][0]["ingested_at"] = "2026-08-19T16:00:00Z"
        orphan = _snapshot("orphaned")

        root = _write_dataset(
            tmp_path,
            cases=[
                _case("stale-digest", []),
                _case("good", []),
                _case("dangling", ["missing-snapshot"]),
                # Pinned so the temporal check actually walks this snapshot.
                _case_over("reads-late-evidence", [broken_snapshot]),
            ],
            snapshots=[broken_snapshot, orphan],
        )

        # Edit one case on disk after the manifest stamped it.
        stale_path = root / "cases" / "stale-digest.json"
        edited = json.loads(stale_path.read_text())
        edited["title"] = "Edited after stamping"
        stale_path.write_text(json.dumps(edited))

        with pytest.raises(DatasetInvalid) as excinfo:
            _load(root)
        errors = excinfo.value.errors
        assert len(errors) >= 4
        joined = "\n".join(errors)
        # An indexed snapshot no case reaches.
        assert "orphaned" in joined
        # A case pointing at evidence nobody wrote.
        assert "missing-snapshot" in joined
        # A fixture edited under its own stamp.
        assert "stale-digest" in joined
        # Knowledge that postdates the task date.
        assert "as_of" in joined

    def test_missing_manifest_refused(self, tmp_path: Path) -> None:
        (tmp_path / "cases").mkdir(parents=True)
        (tmp_path / "snapshots").mkdir(parents=True)
        with pytest.raises(DatasetInvalid):
            load_dataset(tmp_path)


def test_size_budget_model_rejects_zero() -> None:
    with pytest.raises(Exception):
        SizeBudget(
            max_snapshot_bytes=0,
            max_snapshot_rows=10,
            max_total_bytes=100,
            max_total_rows=100,
        )


def test_dataset_digest_covers_case_and_snapshot_indexes(
    tmp_path: Path,
) -> None:
    """Adding a case changes the dataset digest even when snapshots stand still."""
    _write_dataset(tmp_path, cases=[_case("c1", [])], snapshots=[])
    before = load_dataset(tmp_path).dataset_digest

    case2 = _case("c2", [])
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["cases"].append(
        {"case_id": "c2", "file": "cases/c2.json", "digest": content_digest(case2)}
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "cases" / "c2.json").write_text(json.dumps(case2))

    after = load_dataset(tmp_path).dataset_digest
    assert before != after
    assert date.fromisoformat("2026-08-23")

"""Loading a frozen dataset, and refusing every way one could lie.

A dataset is a manifest plus the case and snapshot files it indexes. Loading
is where the anti-repeat contract becomes executable:

- **Digests are recomputed, never trusted.** A file whose canonical form no
  longer matches its stamped digest is refused — the fixture and the claim
  about the fixture must move together.
- **References are closed.** Every file on disk is indexed, everything indexed
  exists, every snapshot is reachable from at least one case, and no case
  points at a snapshot nobody wrote.
- **Time flows toward ``as_of``.** Evidence published or ingested after a
  case's ``as_of`` is knowledge the runtime could not have had; it is refused
  unless explicitly marked as an unavailable trap. Effective-after-``as_of``
  is refused unconditionally.
- **Budgets are enforced.** Per-snapshot and total byte/row ceilings come from
  the reviewed manifest, so a fixture that grows quietly fails loudly.
- **Everything fails together.** Preflight collects every violation across
  every case and reports them in one raise — an operator fixing one broken
  case should not discover the next one on a second run.

Loading touches only this filesystem. No provider call, no database, no
network: repeating a dataset load never repeats a data-provider call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import ValidationError

from .contracts import (
    CASE_SCHEMA,
    SNAPSHOT_SCHEMA,
    CaseFile,
    DatasetManifest,
    SnapshotFile,
    canonical_json,
    content_digest,
    find_secret_shapes,
)

#: Where generated runs are written. Outside the committed dataset paths, and
#: Git-ignored — datasets are reviewed artifacts, runs are disposable output.
DEFAULT_ARTIFACTS_DIR = "apps/api/.artifacts/eval"


class DatasetInvalid(ValueError):
    """The dataset cannot be trusted, with every reason named.

    Carries the full violation list rather than only a headline: preflight
    exists so an operator repairs a dataset in one pass, not one raise per
    defect.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        count = len(self.errors)
        joined = "\n  - ".join(self.errors)
        super().__init__(
            f"the eval dataset is invalid ({count} violation"
            f"{'' if count == 1 else 's'}):\n  - {joined}"
        )


class LoadedDataset:
    """A validated dataset: parsed models plus their recomputed digests."""

    def __init__(
        self,
        *,
        root: Path,
        manifest: DatasetManifest,
        cases: Mapping[str, CaseFile],
        snapshots: Mapping[str, SnapshotFile],
        case_digests: Mapping[str, str],
        snapshot_digests: Mapping[str, str],
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.cases = dict(cases)
        self.snapshots = dict(snapshots)
        self._case_digests = dict(case_digests)
        self._snapshot_digests = dict(snapshot_digests)

    @property
    def errors(self) -> tuple[str, ...]:
        return ()

    @property
    def dataset_digest(self) -> str:
        """Identity of the whole dataset over its sorted content digests."""
        return content_digest(
            {
                "dataset_id": self.manifest.dataset_id,
                "schema": self.manifest.schema_tag,
                "budget": self.manifest.budget.model_dump(mode="json"),
                "cases": sorted(
                    [ref.case_id, self._case_digests[ref.case_id]]
                    for ref in self.manifest.cases
                    if ref.case_id in self._case_digests
                ),
                "snapshots": sorted(
                    [ref.snapshot_id, self._snapshot_digests[ref.snapshot_id]]
                    for ref in self.manifest.snapshots
                    if ref.snapshot_id in self._snapshot_digests
                ),
            }
        )

    def case_digest(self, case_id: str) -> str:
        return self._case_digests[case_id]

    def snapshot_digest(self, snapshot_id: str) -> str:
        return self._snapshot_digests[snapshot_id]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DatasetInvalid([f"{path}: not valid UTF-8 JSON ({exc})"]) from exc


def load_dataset(root: Path | str) -> LoadedDataset:
    """Load, validate, and digest the dataset rooted at ``root``.

    Raises :class:`DatasetInvalid` carrying **every** violation found, before
    any caller can spend anything against a dataset it cannot trust.
    """
    root = Path(root)
    errors: list[str] = []

    # ---- Manifest ---------------------------------------------------------
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise DatasetInvalid([f"{manifest_path}: missing dataset manifest"])

    raw_manifest: Any
    try:
        raw_manifest = _read_json(manifest_path)
        manifest = DatasetManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        raise DatasetInvalid(
            [f"{manifest_path}: {_first(exc)}"]
            + [f"{manifest_path}: {_first_location(item)}" for item in exc.errors()[1:]]
        ) from exc
    except DatasetInvalid as exc:
        raise DatasetInvalid(list(exc.errors)) from exc

    # Duplicates must be caught on the manifest itself: keyed collections below
    # would silently let the last index win.
    _flag_duplicates(manifest.cases, "case", "case_id", errors)
    _flag_duplicates(manifest.snapshots, "snapshot", "snapshot_id", errors)

    if find_secret_shapes(raw_manifest):
        errors.append(f"{manifest_path}: a credential shape appears in the manifest")

    # ---- Files on disk versus files indexed -------------------------------
    case_dir = root / "cases"
    snapshot_dir = root / "snapshots"
    indexed_case_files = {ref.file for ref in manifest.cases}
    indexed_snapshot_files = {ref.file for ref in manifest.snapshots}

    if not case_dir.is_dir() and manifest.cases:
        errors.append(f"{case_dir}: expected directory is missing")
    if not snapshot_dir.is_dir() and manifest.snapshots:
        errors.append(f"{snapshot_dir}: expected directory is missing")

    for directory, indexed, label in (
        (case_dir, indexed_case_files, "cases"),
        (snapshot_dir, indexed_snapshot_files, "snapshots"),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            rel = f"{label}/{path.name}"
            if rel not in indexed:
                errors.append(
                    f"{rel} is on disk but not indexed by the manifest "
                    "(orphan file)"
                )

    # ---- Load and re-digest every indexed document ------------------------
    raw_cases: dict[str, Any] = {}
    raw_snapshots: dict[str, Any] = {}

    for ref in manifest.cases:
        path = root / ref.file
        if not path.is_file():
            errors.append(f"case {ref.case_id!r}: file {ref.file} missing")
            continue
        doc = _read_json(path)
        if not isinstance(doc, Mapping) or doc.get("schema") != CASE_SCHEMA:
            tag = doc.get("schema") if isinstance(doc, Mapping) else "<non-object>"
            errors.append(
                f"{ref.file}: unknown schema tag {tag!r}; expected '{CASE_SCHEMA}'"
            )
            continue
        if content_digest(doc) != ref.digest:
            errors.append(
                f"case {ref.case_id!r}: content changed after stamping — file "
                f"digest {content_digest(doc)} does not match manifest digest "
                f"{ref.digest}"
            )
        if find_secret_shapes(doc):
            errors.append(f"{ref.file}: a credential shape appears in this case")
        raw_cases[ref.case_id] = doc

    for ref in manifest.snapshots:
        path = root / ref.file
        if not path.is_file():
            errors.append(f"snapshot {ref.snapshot_id!r}: file {ref.file} missing")
            continue
        doc = _read_json(path)
        if not isinstance(doc, Mapping) or doc.get("schema") != SNAPSHOT_SCHEMA:
            tag = doc.get("schema") if isinstance(doc, Mapping) else "<non-object>"
            errors.append(
                f"{ref.file}: unknown schema tag {tag!r}; expected "
                f"'{SNAPSHOT_SCHEMA}'"
            )
            continue
        if content_digest(doc) != ref.digest:
            errors.append(
                f"snapshot {ref.snapshot_id!r}: content changed after stamping — "
                f"file digest {content_digest(doc)} does not match manifest "
                f"digest {ref.digest}"
            )
        if find_secret_shapes(doc):
            errors.append(f"{ref.file}: a credential shape appears in this snapshot")
        raw_snapshots[ref.snapshot_id] = doc

    # ---- Strict model validation ------------------------------------------
    cases: dict[str, CaseFile] = {}
    snapshots: dict[str, SnapshotFile] = {}

    for case_id, doc in raw_cases.items():
        try:
            case = CaseFile.model_validate(doc)
        except ValidationError as exc:
            errors.append(f"case {case_id!r}: {_first(exc)}")
            continue
        if case.case_id in cases:
            errors.append(
                f"duplicate case id {case.case_id!r} across indexed files"
            )
            continue
        cases[case.case_id] = case

    for snapshot_id, doc in raw_snapshots.items():
        try:
            snapshot = SnapshotFile.model_validate(doc)
        except ValidationError as exc:
            errors.append(f"snapshot {snapshot_id!r}: {_first(exc)}")
            continue
        if snapshot.snapshot_id in snapshots:
            errors.append(
                f"duplicate snapshot id {snapshot.snapshot_id!r} across indexed "
                "files"
            )
            continue
        snapshots[snapshot.snapshot_id] = snapshot

    # ---- Cross-references --------------------------------------------------
    snapshot_digest_by_id = {
        ref.snapshot_id: content_digest(doc)
        for ref in manifest.snapshots
        for doc in [raw_snapshots.get(ref.snapshot_id)]
        if doc is not None
    }
    owners_of: dict[str, list[str]] = {}
    for case in cases.values():
        seen_by_case: set[str] = set()
        for pin in case.snapshots:
            if pin.snapshot_id not in snapshots:
                errors.append(
                    f"case {case.case_id!r} references snapshot "
                    f"{pin.snapshot_id!r}, which does not exist"
                )
                continue
            # Compared against the raw file document's digest, never a
            # re-serialization: the pin was stamped over what is on disk.
            actual = snapshot_digest_by_id[pin.snapshot_id]
            if actual != pin.digest:
                errors.append(
                    f"case {case.case_id!r}: pinned digest for snapshot "
                    f"{pin.snapshot_id!r} is stale ({pin.digest} != {actual})"
                )
            if pin.snapshot_id not in seen_by_case:
                seen_by_case.add(pin.snapshot_id)
                owners_of.setdefault(pin.snapshot_id, []).append(case.case_id)
    for snapshot_id in snapshots:
        if not owners_of.get(snapshot_id):
            errors.append(
                f"snapshot {snapshot_id!r} is indexed but no case reaches it "
                "(orphan)"
            )

    # ---- Temporal validation ----------------------------------------------
    for case in cases.values():
        as_of_iso = case.as_of.isoformat()
        for pin in case.snapshots:
            snapshot = snapshots.get(pin.snapshot_id)
            if snapshot is None:
                continue
            for index, record in enumerate(snapshot.evidence):
                location = (
                    f"case {case.case_id!r} / snapshot {pin.snapshot_id!r} / "
                    f"evidence[{index}] ({record.entity})"
                )
                if record.effective_at.date() > case.as_of:
                    errors.append(
                        f"{location}: effective_at {record.effective_at.date()} is "
                        f"after case as_of {as_of_iso}; facts effective after the "
                        "task date are refused even when marked as traps"
                    )
                if record.available_after_as_of:
                    continue
                if (
                    record.published_at is not None
                    and record.published_at.date() > case.as_of
                ):
                    errors.append(
                        f"{location}: published_at "
                        f"{record.published_at.date()} is after case as_of "
                        f"{as_of_iso}; mark available_after_as_of if this is a "
                        "deliberate unavailable-trap"
                    )
                if (
                    record.ingested_at is not None
                    and record.ingested_at.date() > case.as_of
                ):
                    errors.append(
                        f"{location}: ingested_at "
                        f"{record.ingested_at.date()} is after case as_of "
                        f"{as_of_iso}"
                    )

    # ---- Budgets -----------------------------------------------------------
    budget = manifest.budget
    total_bytes = 0
    total_rows = 0
    for snapshot_id, snapshot in snapshots.items():
        doc = raw_snapshots.get(snapshot_id)
        size_bytes = len(canonical_json(doc).encode("utf-8")) if doc else 0
        rows = len(snapshot.evidence)
        total_bytes += size_bytes
        total_rows += rows
        owners = owners_of.get(snapshot_id) or ["<unreferenced>"]
        ownership_note = f"owned by case(s) {', '.join(owners)}"
        if rows > budget.max_snapshot_rows:
            errors.append(
                f"snapshot {snapshot_id!r} ({ownership_note}): {rows} evidence "
                f"rows exceed the reviewed per-snapshot budget of "
                f"{budget.max_snapshot_rows}"
            )
        if size_bytes > budget.max_snapshot_bytes:
            errors.append(
                f"snapshot {snapshot_id!r} ({ownership_note}, reached from case "
                f"{owners[0]}): {size_bytes} canonical bytes exceed the reviewed "
                f"per-snapshot budget of {budget.max_snapshot_bytes}"
            )
    if total_rows > budget.max_total_rows:
        errors.append(
            f"dataset totals {total_rows} evidence rows, above the reviewed total "
            f"budget of {budget.max_total_rows}"
        )
    if total_bytes > budget.max_total_bytes:
        errors.append(
            f"dataset totals {total_bytes} canonical bytes, above the reviewed "
            f"total budget of {budget.max_total_bytes}"
        )

    if errors:
        raise DatasetInvalid(errors)

    return LoadedDataset(
        root=root,
        manifest=manifest,
        cases=cases,
        snapshots=snapshots,
        case_digests={
            case_id: content_digest(raw_cases[case_id]) for case_id in raw_cases
        },
        snapshot_digests={
            snapshot_id: content_digest(raw_snapshots[snapshot_id])
            for snapshot_id in raw_snapshots
        },
    )


def _flag_duplicates(refs: Any, label: str, id_field: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for ref in refs:
        identifier = getattr(ref, id_field)
        if identifier in seen:
            errors.append(f"duplicate {label} id {identifier!r} indexed twice")
        seen.add(identifier)


def _first(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    location = ".".join(str(part) for part in first_error["loc"]) or "<root>"
    return f"{location}: {first_error['msg']}"


def _first_location(error: Any) -> str:
    location = ".".join(str(part) for part in error["loc"]) or "<root>"
    return f"{location}: {error['msg']}"


__all__ = [
    "DEFAULT_ARTIFACTS_DIR",
    "DatasetInvalid",
    "LoadedDataset",
    "load_dataset",
]

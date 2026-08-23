"""Canonical atomic JSON artifacts and deterministic Markdown projections."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .contracts import RunManifest, canonical_json, content_digest
from .harness import GatePolicy, HarnessRun


def build_artifact(run: HarnessRun, *, identity: Mapping[str, Any], policy: GatePolicy, reproduction_command: str) -> dict[str, Any]:
    manifest = RunManifest.model_validate(
        {
            "schema": "eval.run-manifest@1",
            "run_id": run.run_id,
            "mode": run.mode,
            **dict(identity),
        }
    )
    body = {
        "schema": "eval.run@1",
        "run_id": run.run_id,
        "mode": run.mode,
        "manifest": manifest.model_dump(mode="json", by_alias=True),
        "policy": policy.model_dump(mode="json", by_alias=True),
        "trials": [record.as_wire() for record in run.records],
        "aggregate": dict(run.aggregate),
        "usage": dict(run.usage),
        "provider": dict(run.provider),
        "completeness": dict(run.completeness),
        "reproduction_command": reproduction_command,
    }
    body["artifact_digest"] = content_digest(body)
    return body


def persist_artifact(path: Path | str, artifact: Mapping[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(dict(artifact)) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def load_artifact(path: Path | str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    stamped = value.pop("artifact_digest", None)
    actual = content_digest(value)
    value["artifact_digest"] = stamped
    if stamped != actual:
        raise ValueError(f"artifact digest mismatch: {stamped} != {actual}")
    return value


def render_markdown(artifact: Mapping[str, Any], *, comparison: Mapping[str, Any] | None = None) -> str:
    completeness = artifact.get("completeness", {})
    provider = artifact.get("provider", {})
    failures = list(completeness.get("failures", []))
    for trial in artifact.get("trials", []):
        for finding in trial.get("grade", {}).get("findings", []):
            failures.append(
                {
                    "case_id": finding.get("case_id", trial.get("case_id")),
                    "trial_index": finding.get("trial_index"),
                    "reason": (
                        f"{finding.get('dimension')}: "
                        f"{finding.get('remediation')}"
                    ),
                }
            )
    lines = [
        f"# Evaluation run {artifact['run_id']}",
        "",
        f"- Artifact digest: `{artifact['artifact_digest']}`",
        f"- Complete: `{str(bool(completeness.get('complete'))).lower()}` ({completeness.get('observed_trials', 0)}/{completeness.get('expected_trials', 0)} trials)",
        f"- Data-provider calls: `{provider.get('data_provider_calls', 'unknown')}`",
        f"- Reproduce: `{artifact.get('reproduction_command', '')}`",
        "",
        "## Environment identity",
        "",
        "```json",
        json.dumps(artifact.get("manifest", artifact.get("identity", {})), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Hard results",
        "",
        f"Hard failures: `{artifact.get('aggregate', {}).get('hard_failures', 0)}`",
    ]
    if comparison is not None:
        lines.extend(["", "## Baseline comparison", "", "```json", json.dumps(dict(comparison), ensure_ascii=False, indent=2, sort_keys=True), "```"])
    lines.extend(["", "## Failed samples", ""])
    if failures:
        lines.extend(f"- `{item.get('case_id')}` trial `{item.get('trial_index')}`: {item.get('reason')}" for item in failures)
    else:
        lines.append("None.")
    lines.extend(["", "## Usage and latency", "", "```json", json.dumps(artifact.get("usage", {}), ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


__all__ = ["build_artifact", "load_artifact", "persist_artifact", "render_markdown"]

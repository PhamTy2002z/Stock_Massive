"""Thin command-line composition root for evaluation operations."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from src.core.llm import llm_config_from_settings

from .baseline import compare
from .contracts import content_digest
from .dataset import DEFAULT_ARTIFACTS_DIR, load_dataset
from .graders import default_registry
from .grading import GradePipeline
from .harness import EvalHarness, GatePolicy
from .report import build_artifact, load_artifact, persist_artifact, render_markdown
from .rubric import RUBRIC_VERSION, StaticRubricJudge
from .smoke import execute_live_case, execute_scripted_case, live_rubric_judge, smoke_config, tool_catalog_for_case, validate_fixture_contract
from .versions import code_stamp, llm_identity, prompt_identity, provider_capability_identity, scoped_tool_catalog_identity

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
DEFAULT_DATASET = API_ROOT / "eval" / "datasets" / "investment-intelligence-v1"
DEFAULT_POLICY = API_ROOT / "eval" / "gate-policy.json"
DEFAULT_BASELINE = API_ROOT / "eval" / "baselines" / "investment-intelligence-v1.json"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / DEFAULT_ARTIFACTS_DIR


def _policy(path: Path) -> GatePolicy:
    return GatePolicy.model_validate_json(path.read_text(encoding="utf-8"))


def _identity(dataset: Any, policy: GatePolicy, *, mode: str) -> dict[str, Any]:
    # Deferred so ``python -m src.eval validate`` remains import-only/offline.
    # Smoke/live execution has already imported this module under its guarded
    # runtime boundary before identity is assembled.
    from .world import resolved_surface_for_catalog

    config = smoke_config() if mode == "smoke" else llm_config_from_settings()
    registry = default_registry()
    catalogs = []
    for case in dataset.cases.values():
        catalog = tool_catalog_for_case(
            case,
            tuple(dataset.snapshots[pin.snapshot_id] for pin in case.snapshots),
        )
        with resolved_surface_for_catalog(catalog) as surface:
            catalogs.append((case.case_id, case.surface, surface))
    tools = scoped_tool_catalog_identity(tuple(catalogs))
    provider = provider_capability_identity()
    return {
        "code": code_stamp(REPO_ROOT).as_wire(),
        "dataset_id": dataset.manifest.dataset_id,
        "dataset_digest": dataset.dataset_digest,
        "case_contract_digest": content_digest([[ref.case_id, ref.digest] for ref in dataset.manifest.cases]),
        "prompts": prompt_identity().as_wire(),
        "tools": tools.as_wire(),
        "model": llm_identity(config),
        "provider_capabilities": provider.as_wire(),
        "graders": registry.versions,
        "rubric_version": RUBRIC_VERSION,
        "policy_version": policy.version,
        "trials": 1 if mode == "smoke" else policy.paid_trials,
    }


async def _execute(args: argparse.Namespace, *, mode: str) -> tuple[dict[str, Any], Path, Path]:
    dataset = load_dataset(args.dataset)
    policy = _policy(args.policy)
    executor = execute_scripted_case if mode == "smoke" else execute_live_case
    if mode != "smoke":
        config = llm_config_from_settings()
        if args.route != config.route.base_url:
            raise ValueError("--route must exactly match the configured LLM route")
        if args.ceiling != policy.run_ceiling_usd:
            raise ValueError(f"--ceiling must match repository policy ({policy.run_ceiling_usd})")
    if mode == "smoke":
        harness = EvalHarness(
            dataset=dataset,
            policy=policy,
            executor=executor,
            pipeline=GradePipeline(judge=StaticRubricJudge()),
        )
        run = await harness.run(mode="smoke")
    else:
        async with live_rubric_judge() as judge:
            harness = EvalHarness(
                dataset=dataset,
                policy=policy,
                executor=executor,
                pipeline=GradePipeline(judge=judge),
            )
            run = await harness.run(
                mode="multi-trial",
                requested_ceiling_usd=args.ceiling,
            )
    command = "make eval-smoke" if mode == "smoke" else f"make eval-run EVAL_ROUTE={args.route} EVAL_CEILING={args.ceiling}"
    artifact = build_artifact(run, identity=_identity(dataset, policy, mode=mode), policy=policy, reproduction_command=command)
    output = Path(args.output) if args.output else DEFAULT_ARTIFACT_ROOT / f"{run.run_id}.json"
    markdown = output.with_suffix(".md")
    persist_artifact(output, artifact)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(artifact), encoding="utf-8")
    return artifact, output, markdown


def _validate(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    policy = _policy(args.policy)
    GradePipeline().validate_cases(tuple(dataset.cases.values()))
    for case in dataset.cases.values():
        validate_fixture_contract(
            case,
            tuple(dataset.snapshots[pin.snapshot_id] for pin in case.snapshots),
        )
    if policy.dataset_id != dataset.manifest.dataset_id:
        raise ValueError("gate policy targets another dataset")
    print(json.dumps({"dataset_id": dataset.manifest.dataset_id, "dataset_digest": dataset.dataset_digest, "cases": len(dataset.cases), "snapshots": len(dataset.snapshots), "graders": default_registry().versions}, sort_keys=True))
    return 0


def _run_command(args: argparse.Namespace, *, mode: str) -> int:
    artifact, output, markdown = asyncio.run(_execute(args, mode=mode))
    print(json.dumps({"complete": artifact["completeness"]["complete"], "hard_failures": artifact["aggregate"]["hard_failures"], "artifact": str(output), "markdown": str(markdown), "digest": artifact["artifact_digest"]}, sort_keys=True))
    return 0 if artifact["completeness"]["complete"] and artifact["aggregate"]["hard_failures"] == 0 else 1


def _compare(args: argparse.Namespace) -> int:
    baseline = load_artifact(args.baseline)
    candidate = load_artifact(args.candidate)
    decision = compare(baseline, candidate)
    print(json.dumps(decision.as_wire(), sort_keys=True))
    return 0 if decision.passed else 1


def _render(args: argparse.Namespace) -> int:
    artifact = load_artifact(args.artifact)
    text = render_markdown(artifact)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def _gate(args: argparse.Namespace) -> int:
    summary = json.loads(Path(args.baseline_summary).read_text(encoding="utf-8"))
    approved = summary.get("approved_artifact_digest")
    if summary.get("status") != "approved" or not approved:
        raise ValueError("no owner-approved paid baseline exists; release gate cannot run")
    artifact, output, markdown = asyncio.run(_execute(args, mode="multi-trial"))
    baseline_path = Path(args.baseline_artifact)
    baseline = load_artifact(baseline_path)
    if baseline.get("artifact_digest") != approved:
        raise ValueError("approved baseline digest does not match the supplied baseline artifact")
    decision = compare(baseline, artifact)
    markdown.write_text(
        render_markdown(artifact, comparison=decision.as_wire()),
        encoding="utf-8",
    )
    print(json.dumps({"candidate": str(output), "decision": decision.as_wire()}, sort_keys=True))
    return 0 if decision.passed else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m src.eval")
    root.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    root.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate dataset, graders, and gate policy")
    smoke = commands.add_parser("smoke", help="run the complete offline scripted battery")
    smoke.add_argument("--output", type=Path)
    paid = commands.add_parser("run", help="run the repository-owned paid multi-trial policy")
    paid.add_argument("--route", required=True)
    paid.add_argument("--ceiling", type=float, required=True)
    paid.add_argument("--output", type=Path)
    comparison = commands.add_parser("compare", help="compare immutable candidate and baseline artifacts")
    comparison.add_argument("baseline", type=Path)
    comparison.add_argument("candidate", type=Path)
    render = commands.add_parser("render", help="render Markdown from canonical JSON")
    render.add_argument("artifact", type=Path)
    render.add_argument("--output", type=Path)
    gate = commands.add_parser("gate", help="run and compare under approved repository policy")
    gate.add_argument("--route", required=True)
    gate.add_argument("--ceiling", type=float, required=True)
    gate.add_argument("--output", type=Path)
    gate.add_argument("--baseline-summary", type=Path, default=DEFAULT_BASELINE)
    gate.add_argument("--baseline-artifact", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "smoke":
            return _run_command(args, mode="smoke")
        if args.command == "run":
            return _run_command(args, mode="multi-trial")
        if args.command == "compare":
            return _compare(args)
        if args.command == "render":
            return _render(args)
        return _gate(args)
    except Exception as exc:  # noqa: BLE001 - CLI owns the exit contract
        print(f"eval error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


__all__ = ["main", "parser"]

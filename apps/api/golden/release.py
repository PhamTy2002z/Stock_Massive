"""One command: run the corpus, judge it, grade it, and say what it amounts to.

Roadmap §10 Phase 1 asks for exactly this — the whole corpus behind a single
invocation, with pass and fail printed per dimension — and the reason it is one
command rather than four is that a four-step measurement is a measurement
somebody eventually runs three steps of.

The file is deliberately thin. It owns no logic: the corpus belongs to
``run.py``, the rubric to ``judge.py``, the scoring to ``grade.py`` and the bars
to ``gate.py``. Everything here is sequencing, artifact paths and the exit code.
Each stage is also still runnable on its own, because a run that cost real money
must be re-gradeable and re-judgeable for free.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import gate as gate_module
from .grade import grade, load_corpus
from .judge import judge_artifact
from .run import run_corpus

logger = logging.getLogger("golden.release")

DEFAULT_CORPUS = "golden/release.json"


def _stamped(corpus: dict[str, Any]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")
    return f"{corpus.get('corpus_id', 'run')}-{stamp}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run, judge, grade and gate the golden release corpus."
    )
    # No default, for the same reason ``run.py`` has none: a runner that can
    # start without a ceiling eventually will, and the whole model envelope is
    # $45 a month.
    parser.add_argument("--ceiling-usd", type=float, required=True)
    parser.add_argument(
        "--judge-ceiling-usd",
        type=float,
        default=None,
        help="separate ceiling for the rubric pass; a fifth of the run's by default",
    )
    parser.add_argument("--corpus", default=DEFAULT_CORPUS)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="how many Turns of one trial run side by side; changes latency, not answers",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tape", default=None, help="defaults to a tape beside the artifact")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--out", default=None)
    parser.add_argument("--git-sha", default=None)
    parser.add_argument("--no-judge", action="store_true", help="skip the rubric pass")
    parser.add_argument(
        "--grade-only",
        default=None,
        help="skip running and grade this artifact instead; costs nothing",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.ceiling_usd <= 0:
        parser.error("--ceiling-usd must be positive")
    if args.trials < 1:
        parser.error("--trials must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    corpus = load_corpus(args.corpus)

    if args.grade_only:
        artifact_path = Path(args.grade_only)
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    else:
        name = _stamped(corpus)
        artifact_path = Path(args.out or f"golden/artifacts/{name}.json")
        tape_path = Path(args.tape or f"golden/artifacts/{name}-tape.json")
        artifact = asyncio.run(
            run_corpus(
                corpus=corpus,
                ceiling_micro_usd=int(round(args.ceiling_usd * 1_000_000)),
                tape_path=tape_path,
                replay=bool(args.replay),
                limit=args.limit,
                git_sha=args.git_sha,
                trials=args.trials,
                concurrency=args.concurrency,
            )
        )
        if not args.no_judge:
            judge_ceiling = args.judge_ceiling_usd
            if judge_ceiling is None:
                judge_ceiling = args.ceiling_usd / 5
            artifact = asyncio.run(
                judge_artifact(
                    artifact,
                    corpus,
                    ceiling_micro_usd=int(round(judge_ceiling * 1_000_000)),
                    user_id=(artifact.get("run") or {}).get("runner_user_id"),
                    concurrency=args.concurrency,
                )
            )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    report = grade(artifact, corpus)
    verdict = gate_module.evaluate(report, gate_module.load_thresholds())

    report_path = artifact_path.with_name(artifact_path.stem + "-report.json")
    report_path.write_text(
        json.dumps(
            {
                "artifact": str(artifact_path),
                "corpus": args.corpus,
                "run": report.run,
                "gate": verdict.as_dict(),
                "report": report.as_dict(),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(gate_module.render(verdict))
    print(f"\nartifact: {artifact_path}")
    print(f"report:   {report_path}")
    return verdict.exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DEFAULT_CORPUS", "main"]

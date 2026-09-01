"""The rubric pass: one model call per case-trial, scoring roadmap §3.

It is a separate pass, run between the corpus and the grader, and that
separation is the design rather than a convenience. ``grade.py`` must stay a
pure function of the artifact — free to re-run, identical months later — and a
grader that called a model would be neither. So the judge runs once, writes its
verdicts *into* the artifact under ``cases[].judge``, and the grader reads them
the way it reads every other recorded field.

**The judge sees the answer and nothing else.** Not the evidence, not the tool
calls, not what the deterministic dimensions concluded. Two reasons, and the
second is the load-bearing one. A judge shown the evidence starts re-checking
the numbers, which is work the backend does mechanically and better. And a judge
shown the other scores agrees with them — the correlation would be an artefact
of the prompt rather than a measurement of the answer.

**A judge that cannot answer says so.** A parse failure, a provider error or a
refusal produces ``status: "unavailable"`` with the reason attached. It never
produces a middling score: a missing rubric verdict is missing information,
whereas a three out of five is a claim about the answer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger("golden.judge")

PROMPT_VERSION = "golden.judge@1"

#: The five axes of roadmap §3. The names are the contract with ``grade.py``.
AXES = (
    "synthesis",
    "structure_for_intent",
    "counterargument",
    "uncertainty",
    "decision_utility",
)

#: Worst case per judge call. Generous on input because a deep memo is long, and
#: tight on output because the reply is one small JSON object.
JUDGE_INPUT_TOKENS = 8000
JUDGE_OUTPUT_TOKENS = 700

SYSTEM = """\
Bạn là giám khảo chấm chất lượng câu trả lời phân tích chứng khoán. Bạn chấm
theo năm trục dưới đây, thang 1–5, kèm một câu lý do ngắn cho mỗi trục.

- synthesis: câu trả lời có tổng hợp thành một bức tranh, hay chỉ liệt kê rời rạc.
- structure_for_intent: cấu trúc có phục vụ đúng câu hỏi được hỏi, mở đầu bằng
  kết luận, hay là một khuôn mẫu áp vào mọi câu.
- counterargument: có nêu điều gì có thể làm luận điểm sai, có tự tấn công lập
  luận của mình, hay chỉ một chiều.
- uncertainty: có phân biệt dữ kiện, suy luận và kịch bản; có nêu khoảng trống
  và mâu thuẫn, hay biến phỏng đoán thành điều chắc chắn.
- decision_utility: người đọc có rút ra được điều gì để quyết định, hay chỉ đọc
  xong rồi thôi.

Ba điều bạn TUYỆT ĐỐI không làm, vì đã có cơ chế khác đo chúng chính xác hơn:
1. Không chấm đúng/sai của bất kỳ con số nào. Bạn không có nguồn để đối chiếu.
2. Không chấm việc trích dẫn hay có nguồn hay không.
3. Không thưởng điểm cho độ dài, cho giọng văn tự tin, hay cho việc đưa khuyến
   nghị mua bán. Một câu trả lời từ chối đúng chỗ có thể đạt điểm cao.

Trả lời DUY NHẤT một object JSON, không kèm giải thích ngoài JSON, dạng:
{"synthesis": {"score": 1-5, "why": "..."}, "structure_for_intent": {...},
 "counterargument": {...}, "uncertainty": {...}, "decision_utility": {...}}
"""

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def build_user_message(case: Mapping[str, Any], corpus: Mapping[str, Any]) -> str:
    """What the judge is shown: the question, its family, and the answer.

    The family description is included because §3 asks for structure *by intent*
    and a judge that cannot tell an event memo from a refusal case would score
    both against the same shape.
    """
    family = str(case.get("family") or "")
    description = (corpus.get("families") or {}).get(family) or ""
    answer = str(case.get("answer_text") or "").strip() or "(câu trả lời rỗng)"
    return (
        f"Loại câu hỏi: {family}\n"
        f"Loại này kiểm tra: {description}\n\n"
        f"CÂU HỎI:\n{case.get('question')}\n\n"
        f"CÂU TRẢ LỜI CẦN CHẤM:\n{answer}\n"
    )


def parse_scores(text: str) -> dict[str, dict[str, Any]]:
    """The five axes out of whatever the model returned.

    Raises rather than guessing. A judge reply that cannot be read is an
    unavailable verdict, and inventing a default here is exactly the silent
    score this pass is arranged to avoid.
    """
    body = (text or "").strip()
    fenced = _FENCE.search(body)
    if fenced:
        body = fenced.group(1).strip()
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("the reply carried no JSON object")
    parsed = json.loads(body[start : end + 1])
    if not isinstance(parsed, Mapping):
        raise ValueError("the reply's JSON is not an object")

    scores: dict[str, dict[str, Any]] = {}
    for axis in AXES:
        entry = parsed.get(axis)
        if isinstance(entry, Mapping):
            raw, why = entry.get("score"), str(entry.get("why") or "")
        else:
            raw, why = entry, ""
        if raw is None:
            raise ValueError(f"the reply is missing the {axis!r} axis")
        score = float(raw)
        if not 1.0 <= score <= 5.0:
            raise ValueError(f"{axis} scored {score}, which is outside 1–5")
        scores[axis] = {"score": score, "why": why}
    return scores


class Judge:
    """One model, one prompt, one JSON object per case-trial."""

    def __init__(self, client: Any, model: str, *, user_id: int | None = None) -> None:
        self._client = client
        self._model = model
        self._user_id = user_id
        self._run_id = uuid.uuid4().hex[:12]
        self._index = 0
        self.spent_micro_usd = 0

    @property
    def model(self) -> str:
        return self._model

    def _owner_id(self, index: int) -> str:
        return f"golden-judge:{self._run_id}:{index}"

    async def _reconcile(self, owner_id: str) -> int:
        """What one judge call actually cost, read back from the ledger.

        Read rather than estimated. A ceiling enforced against a number the
        harness made up is not a ceiling, and the reserved worst case is several
        times the real price of a short JSON reply — a run would stop less than
        halfway through and call it spent.
        """
        from sqlalchemy import func, select

        from src.alpha.models import LlmCallUsage
        from src.core.database import sync_session_factory
        from src.core.llm import OwnerType

        def read() -> int:
            with sync_session_factory() as session:
                return int(
                    session.execute(
                        select(
                            func.coalesce(
                                func.sum(
                                    func.coalesce(
                                        LlmCallUsage.actual_micro_usd,
                                        LlmCallUsage.reserved_micro_usd,
                                    )
                                ),
                                0,
                            )
                        ).where(
                            LlmCallUsage.owner_type == OwnerType.GOLDEN_JUDGE.value,
                            LlmCallUsage.owner_id == owner_id,
                        )
                    ).scalar_one()
                )

        return await asyncio.to_thread(read)

    async def score(
        self, case: Mapping[str, Any], corpus: Mapping[str, Any]
    ) -> dict[str, Any]:
        from src.core.llm import (
            BudgetLane,
            CallOwner,
            CompletionRequest,
            Message,
            OwnerType,
            Role,
            SpendRequest,
            Workload,
        )

        request = CompletionRequest(
            model=self._model,
            messages=(
                Message(role=Role.SYSTEM, content=SYSTEM),
                Message(role=Role.USER, content=build_user_message(case, corpus)),
            ),
            tool_choice="none",
            max_output_tokens=JUDGE_OUTPUT_TOKENS,
            stream=False,
            metadata={"golden_judge": f"{case.get('id')}:{case.get('trial')}"},
        )
        self._index += 1
        owner_id = self._owner_id(self._index)
        spend = SpendRequest(
            # Its own owner and its own lane, for reasons written out beside
            # ``OwnerType.GOLDEN_JUDGE``: borrowing the probe's owner would
            # exhaust an allowance production needs at boot, and borrowing the
            # Turn's would put measurement spend inside the rows a Turn's cost
            # is read from — measuring the system by changing it.
            owner=CallOwner(OwnerType.GOLDEN_JUDGE, owner_id, user_id=self._user_id),
            lane=BudgetLane.ANALYSIS,
            workload=Workload.SESSION,
            input_tokens=JUDGE_INPUT_TOKENS,
            output_tokens=JUDGE_OUTPUT_TOKENS,
        )

        try:
            return await self._attempts(request, spend, case)
        finally:
            # Once for the whole call, retry included: both attempts reserve
            # under the same owner id, so reading inside the loop would count
            # the first attempt twice.
            self.spent_micro_usd += await self._reconcile(owner_id)

    async def _attempts(
        self, request: Any, spend: Any, case: Mapping[str, Any]
    ) -> dict[str, Any]:
        last: str = ""
        for attempt in (1, 2):
            try:
                completion = await self._client.complete(request, spend)
            except Exception as exc:  # noqa: BLE001 - a judge failure is data
                return {
                    "status": "unavailable",
                    "model": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            try:
                return {
                    "status": "scored",
                    "model": completion.model or self._model,
                    "prompt_version": PROMPT_VERSION,
                    "scores": parse_scores(completion.text or ""),
                }
            except (ValueError, json.JSONDecodeError) as exc:
                # One retry, because a model that fenced its JSON once often
                # does not twice. Two failures is a verdict, not a hiccup.
                last = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "judge reply for %s t%s was unreadable on attempt %d: %s",
                    case.get("id"), case.get("trial"), attempt, last,
                )
        return {
            "status": "unavailable",
            "model": self._model,
            "prompt_version": PROMPT_VERSION,
            "reason": last,
        }


async def judge_artifact(
    artifact: dict[str, Any],
    corpus: Mapping[str, Any],
    *,
    ceiling_micro_usd: int,
    client: Any | None = None,
    model: str | None = None,
    user_id: int | None = None,
    concurrency: int = 1,
) -> dict[str, Any]:
    """Score every case-trial in place and hand the artifact back.

    The ceiling is checked before each call and is its own, separate from the
    run's: a judge pass that could eat the corpus budget would make the two
    numbers in the artifact impossible to read apart.
    """
    from src.core.llm import Workload, build_client

    from .run import runner_config

    config = runner_config()
    owned = client is None
    if client is None:
        client = build_client(config=config)
    judge = Judge(client, model or config.model_for(Workload.SESSION), user_id=user_id)

    cases = [case for case in artifact.get("cases") or () if isinstance(case, dict)]
    stopped: str | None = None
    scored = 0
    gate = asyncio.Semaphore(max(1, concurrency))

    async def score_one(case: dict[str, Any]) -> None:
        nonlocal stopped, scored
        async with gate:
            if judge.spent_micro_usd >= ceiling_micro_usd:
                stopped = (
                    f"judge ceiling reached after {scored} of {len(cases)} case-trial(s)"
                )
                case["judge"] = {
                    "status": "unavailable",
                    "model": judge.model,
                    "prompt_version": PROMPT_VERSION,
                    "reason": stopped,
                }
                return
            case["judge"] = await judge.score(case, corpus)
            scored += 1

    try:
        await asyncio.gather(*(score_one(case) for case in cases))
    finally:
        if owned and hasattr(client, "aclose"):
            await client.aclose()

    provenance = artifact.setdefault("run", {}).setdefault("provenance", {})
    provenance["judge_model"] = judge.model
    provenance["judge_prompt_version"] = PROMPT_VERSION
    provenance["judge_scored"] = scored
    if stopped:
        provenance["judge_stopped"] = stopped
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a golden artifact's answers.")
    parser.add_argument("artifact", help="path to a golden artifact JSON file")
    parser.add_argument("--corpus", default=None, help="the corpus the artifact was run from")
    parser.add_argument(
        "--ceiling-usd",
        type=float,
        required=True,
        help="hard spend ceiling for the judge pass, in USD; required",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default=None, help="where to write; defaults to in place")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.ceiling_usd <= 0:
        parser.error("--ceiling-usd must be positive")

    from .grade import corpus_beside, load_corpus

    path = Path(args.artifact)
    artifact = json.loads(path.read_text(encoding="utf-8"))
    corpus = (
        load_corpus(args.corpus)
        if args.corpus
        else corpus_beside(artifact, Path(__file__).resolve().parent)
    )
    artifact = asyncio.run(
        judge_artifact(
            artifact,
            corpus,
            ceiling_micro_usd=int(round(args.ceiling_usd * 1_000_000)),
            model=args.model,
        )
    )
    out = Path(args.out or path)
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"judged: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AXES",
    "JUDGE_INPUT_TOKENS",
    "JUDGE_OUTPUT_TOKENS",
    "PROMPT_VERSION",
    "SYSTEM",
    "Judge",
    "build_user_message",
    "judge_artifact",
    "parse_scores",
]

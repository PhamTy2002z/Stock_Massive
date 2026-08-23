"""Strict, blinded rubric grading kept behind deterministic checks."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.llm import (
    BudgetLane,
    CallOwner,
    CompletionRequest,
    JsonSchemaFormat,
    Message,
    OwnerType,
    Role,
    SpendRequest,
    Workload,
)
from src.core.llm.config import LLMConfig, TOKENS_PER_PRICE_UNIT

from .contracts import CaseFile, SnapshotFile, canonical_json
if TYPE_CHECKING:
    from .runner import EvalResult

RUBRIC_VERSION = "investment-intelligence-rubric@1"
RUBRIC_OUTPUT_TOKENS = 512
RUBRIC_SCHEMA = {
    "type": "object",
    "properties": {
        "synthesis": {"type": "integer", "minimum": 1, "maximum": 5},
        "counterargument": {"type": "integer", "minimum": 1, "maximum": 5},
        "uncertainty": {"type": "integer", "minimum": 1, "maximum": 5},
        "utility": {"type": "integer", "minimum": 1, "maximum": 5},
        "justification": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["synthesis", "counterargument", "uncertainty", "utility", "justification"],
    "additionalProperties": False,
}
RUBRIC_FORMAT = JsonSchemaFormat(name="eval_rubric", schema=RUBRIC_SCHEMA)
RUBRIC_SYSTEM_PROMPT = (
    "Grade only the supplied blinded evaluation payload. Return strict JSON "
    "matching the response schema. Never infer candidate identity or hard-pass status."
)


class RubricScores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    synthesis: int = Field(ge=1, le=5)
    counterargument: int = Field(ge=1, le=5)
    uncertainty: int = Field(ge=1, le=5)
    utility: int = Field(ge=1, le=5)
    justification: str = Field(min_length=1, max_length=500)


class RubricJudge(Protocol):
    def judge(self, payload: str) -> str | Any: ...


@dataclass(frozen=True)
class RubricJudgeResponse:
    text: str
    usage_tokens: int | None
    cost_usd: float | None


class StaticRubricJudge:
    """Free deterministic judge used only by offline smoke."""

    def judge(self, _payload: str) -> RubricJudgeResponse:
        return RubricJudgeResponse(
            text=json.dumps(
                {
                    "synthesis": 4,
                    "counterargument": 4,
                    "uncertainty": 4,
                    "utility": 4,
                    "justification": "Deterministic offline rubric fixture.",
                },
                sort_keys=True,
            ),
            usage_tokens=0,
            cost_usd=0.0,
        )


class LLMRubricJudge:
    """Run the blinded rubric through a separately metered eval client."""

    def __init__(self, client: Any, *, config: LLMConfig, owner_prefix: str) -> None:
        self._client = client
        self._config = config
        self._owner_prefix = owner_prefix
        self._calls = 0
        self._remaining_ceiling_usd: float | None = None

    def set_remaining_ceiling(self, value: float | None) -> None:
        self._remaining_ceiling_usd = value

    async def judge(self, payload: str) -> RubricJudgeResponse:
        self._calls += 1
        workload = Workload.BATCH
        request = CompletionRequest(
            model=self._config.model_for(workload),
            messages=(
                Message(role=Role.SYSTEM, content=RUBRIC_SYSTEM_PROMPT),
                Message(role=Role.USER, content=payload),
            ),
            tools=(),
            tool_choice="none",
            response_format=RUBRIC_FORMAT,
            max_output_tokens=RUBRIC_OUTPUT_TOKENS,
            temperature=0.0,
            stream=False,
        )
        input_tokens = max(1, (len(payload) + len(RUBRIC_SYSTEM_PROMPT) + 3) // 4)
        prices = self._config.prices_for(workload)
        reservation_usd = (
            input_tokens * max(prices.input, prices.cache_write)
            + RUBRIC_OUTPUT_TOKENS * prices.output
        ) / TOKENS_PER_PRICE_UNIT
        if self._remaining_ceiling_usd is None:
            raise ValueError("rubric run ceiling is unknown; refusing before dispatch")
        if reservation_usd > self._remaining_ceiling_usd + 1e-12:
            raise ValueError(
                "rubric reservation would exceed the remaining run ceiling"
            )
        completion = await self._client.complete(
            request,
            SpendRequest(
                owner=CallOwner(
                    type=OwnerType.ANALYSIS_RUN,
                    id=f"{self._owner_prefix}-rubric-{self._calls}",
                ),
                lane=BudgetLane.ANALYSIS,
                workload=workload,
                input_tokens=input_tokens,
                output_tokens=RUBRIC_OUTPUT_TOKENS,
            ),
        )
        if completion.text is None:
            raise ValueError("rubric judge returned no text")
        usage = completion.usage
        cost = None
        if usage is not None:
            cost = self._config.prices_for(workload).cost_usd(
                input_tokens=usage.input_tokens,
                cached_input_tokens=usage.cached_input_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
            )
        return RubricJudgeResponse(
            text=completion.text,
            usage_tokens=None if usage is None else usage.total_tokens,
            cost_usd=cost,
        )


@dataclass(frozen=True)
class RubricResult:
    available: bool
    version: str
    scores: RubricScores | None
    error: str | None
    usage_tokens: int | None = None
    cost_usd: float | None = None

    def as_wire(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "version": self.version,
            "scores": None if self.scores is None else self.scores.model_dump(mode="json"),
            "error": self.error,
            "usage_tokens": self.usage_tokens,
            "cost_usd": self.cost_usd,
        }


def blinded_payload(case: CaseFile, snapshots: tuple[SnapshotFile, ...], result: EvalResult) -> str:
    evidence = [
        {
            "snapshot_id": snapshot.snapshot_id,
            "records": [
                {
                    "source": item.source.value,
                    "capability": item.capability,
                    "entity": item.entity,
                    "unit": item.unit,
                    "value": item.value,
                    "health": item.health.value,
                    "effective_at": item.effective_at.isoformat(),
                    "published_at": None if item.published_at is None else item.published_at.isoformat(),
                    "provenance": item.provenance,
                }
                for item in snapshot.evidence
            ],
        }
        for snapshot in snapshots
    ]
    payload = {
        "rubric_version": RUBRIC_VERSION,
        "task": {"surface": case.surface, "family": case.family, "as_of": case.as_of.isoformat(), "input": case.input.model_dump(mode="json")},
        "authorized_context": None if case.user_context is None else {"display_name": case.user_context.display_name},
        "frozen_evidence": evidence,
        "outcome": dict(result.observable.content),
        "rubric": {"dimensions": ["synthesis", "counterargument", "uncertainty", "utility"], "scale": "integer 1-5", "response": "strict JSON only with concise justification"},
    }
    return canonical_json(payload)


async def run_rubric(judge: RubricJudge, *, case: CaseFile, snapshots: tuple[SnapshotFile, ...], result: EvalResult) -> RubricResult:
    try:
        raw = judge.judge(blinded_payload(case, snapshots, result))
        if inspect.isawaitable(raw):
            raw = await raw
        usage = getattr(raw, "usage_tokens", None)
        cost = getattr(raw, "cost_usd", None)
        text = getattr(raw, "text", raw)
        if not isinstance(text, str):
            raise TypeError("judge response is not text")
        decoded = json.loads(text)
        scores = RubricScores.model_validate(decoded)
        return RubricResult(True, RUBRIC_VERSION, scores, None, usage, cost)
    except Exception as exc:  # noqa: BLE001 - judge failure is measurement data
        return RubricResult(False, RUBRIC_VERSION, None, f"{type(exc).__name__}: {exc}")


__all__ = [
    "LLMRubricJudge",
    "RUBRIC_VERSION",
    "RubricJudge",
    "RubricResult",
    "RubricScores",
    "StaticRubricJudge",
    "blinded_payload",
    "run_rubric",
]

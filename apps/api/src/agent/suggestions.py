"""The follow-up questions offered under a completed answer.

``docs/adr/0020``: one extra provider call on the **batch** workload, charged to
the same owner as the Turn that earned it, producing the two short questions the
reader is most likely to ask next.

Best-effort by construction. Every failure path — refused budget, timeout, a
malformed response, a dead route — returns no suggestions and says so in the log.
The answer is the product; a Turn that succeeded must never be reported as having
failed because a garnish did not render.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from typing import Any

from src.core.llm import (
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    CompletionRequest,
    JsonSchemaFormat,
    LLMClient,
    LLMError,
    Message,
    Role,
    SpendRequest,
    Workload,
)

logger = logging.getLogger(__name__)

#: Two, and only two. A panel of five reads as a menu the reader has to triage;
#: two read as the conversation's next step, so each one has to earn its place.
MAX_SUGGESTIONS = 2
#: A follow-up is a question, not a paragraph. Anything longer is dropped.
MAX_SUGGESTION_CHARS = 120
#: Short by nature: two one-line questions cannot need more than this, and the
#: headroom is for a route that spends tokens thinking before it answers.
MAX_OUTPUT_TOKENS = 400
#: Nothing waits on these interactively, but the terminal transaction does.
TIMEOUT_SECONDS = 20.0
#: How much of the answer the suggester is shown. A follow-up is only specific if
#: it can name what the answer actually said, so it is shown the figures and the
#: names, not just the opening subject.
MAX_ANSWER_CHARS = 6_000

SUGGESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "minItems": MAX_SUGGESTIONS,
            "maxItems": MAX_SUGGESTIONS,
            "items": {"type": "string", "minLength": 1, "maxLength": MAX_SUGGESTION_CHARS},
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}

SUGGESTIONS_FORMAT = JsonSchemaFormat(name="followup_suggestions", schema=SUGGESTIONS_SCHEMA)

# Fixed prose, for the same reason every other prompt in this codebase is: a
# prompt assembled by branching on what happened to be in one answer cannot be
# reviewed or compared across two Turns.
SYSTEM_PROMPT = """\
You write follow-up questions for a Vietnamese equities research assistant.

You are given the user's question and the answer they were just shown. Return
exactly two questions — the two the same reader would most plausibly ask next.

Two, not a menu. Each one has to move the conversation forward from this answer,
so:

- Question 1 goes **deeper**: it takes a specific figure, name, period or
  mechanism the answer stated and asks for the thing behind it.
- Question 2 goes **wider**: it keeps the same subject and extends it to another
  period, another statement, a peer company or the same company's sector.

Rules:

- Name what the answer named. A question that would read the same under any
  other answer is worthless — use the ticker, the figure, the quarter, the line
  item or the company that actually appeared.
- Never ask something the answer already answered, and never restate the user's
  question.
- No general-knowledge or textbook questions ("how do I tell whether X is
  seasonal", "which items explain Y"). Ask about this company, this number,
  this period.
- Write in the language of the user's question. If it is Vietnamese, both
  questions are Vietnamese.
- One line each, at most 120 characters, phrased as the reader would type them.
- Each must be answerable from Vietnamese listed-equity data or public company
  information — never a request for a price target, a buy/sell instruction, or a
  prediction of a future price.
"""


def build_request(
    *, model: str, user_text: str, answer_text: str
) -> CompletionRequest:
    """The one call, described without naming the route."""
    content = (
        f"Câu hỏi của người dùng:\n{user_text.strip()}\n\n"
        f"Câu trả lời đã hiển thị:\n{answer_text.strip()[:MAX_ANSWER_CHARS]}"
    )
    return CompletionRequest(
        model=model,
        messages=(
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=content),
        ),
        # No tools, so no loop is expressible; "none" states it rather than
        # relying on an empty catalog to imply it.
        tools=(),
        tool_choice="none",
        response_format=SUGGESTIONS_FORMAT,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.3,
        stream=False,
    )


def parse(text: str | None) -> tuple[str, ...]:
    """Read the model's answer defensively, and keep only what is usable.

    A schema was requested, and a gateway that dropped it has been measured
    before (:class:`JsonSchemaFormat`), so nothing here trusts the shape: a
    response that is not the object it was asked for yields no suggestions
    rather than an exception on the terminal path.
    """
    if not text:
        return ()
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, dict):
        return ()
    rows = payload.get("suggestions")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()
    kept: list[str] = []
    for row in rows:
        if not isinstance(row, str):
            continue
        question = " ".join(row.split()).strip()
        if not question or len(question) > MAX_SUGGESTION_CHARS:
            continue
        if question in kept:
            continue
        kept.append(question)
        if len(kept) >= MAX_SUGGESTIONS:
            break
    return tuple(kept)


async def generate(
    client: LLMClient,
    request: CompletionRequest,
    spend: SpendRequest,
) -> tuple[str, ...]:
    """Ask for the follow-ups, and treat every failure as "none".

    The request and the spend are built by the caller because only the caller
    knows which artifact the Turn is charged to (``docs/adr/0014``) and what the
    reservation has to cover; what is fixed here is that a refusal, a timeout or
    a malformed answer ends this quietly.
    """
    try:
        completion = await asyncio.wait_for(
            client.complete(request, spend), TIMEOUT_SECONDS
        )
    except BudgetRefusal as refusal:
        logger.info("No budget for follow-up suggestions: %s", refusal.reason)
        return ()
    except (TimeoutError, asyncio.TimeoutError):
        logger.info("Follow-up suggestions timed out after %.0fs", TIMEOUT_SECONDS)
        return ()
    except LLMError as error:
        logger.info("Follow-up suggestions were not produced: %s", error)
        return ()
    except Exception:  # pragma: no cover - defence in depth on a terminal path
        logger.exception("Follow-up suggestions failed unexpectedly")
        return ()
    return parse(completion.text)


def spend_for(
    request: CompletionRequest,
    *,
    owner: CallOwner,
    lane: BudgetLane,
    estimated_input_tokens: int,
) -> SpendRequest:
    """What admission is asked to fund, on the cheap model.

    Batch rather than session because nothing is waiting on these tokens as they
    arrive: they are assembled into the terminal transaction, so they land with
    the canonical message instead of racing it.
    """
    return SpendRequest(
        owner=owner,
        lane=lane,
        workload=Workload.BATCH,
        input_tokens=estimated_input_tokens,
        output_tokens=request.max_output_tokens or MAX_OUTPUT_TOKENS,
    )


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "MAX_SUGGESTIONS",
    "MAX_SUGGESTION_CHARS",
    "SUGGESTIONS_FORMAT",
    "SUGGESTIONS_SCHEMA",
    "SYSTEM_PROMPT",
    "TIMEOUT_SECONDS",
    "build_request",
    "generate",
    "parse",
    "spend_for",
]

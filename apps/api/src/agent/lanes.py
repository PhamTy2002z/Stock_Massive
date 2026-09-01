"""What one Turn is allowed to spend, decided once from what was asked.

The ceilings a Turn runs under used to be module constants in ``loop.py``, which
made them one number for every question: a reader asking what a ticker's code is
and a reader asking for a thesis to be stress-tested were funded identically.
Four rounds is generous for the first and mean for the second, and no amount of
tuning a single constant fixes both.

So the ceilings become a *profile* the Turn carries, and the constants in
``loop.py`` become the values of :data:`LIGHT` — the same numbers, the same
behaviour, now with a name. Nothing about the loop's mechanism changes with the
lane: the guardrail ladder, the recovery bounds and the ledger still enforce
themselves, and a lane only says how far the Turn may go before it has to
conclude with what it has.

**One piece of arithmetic, declared on the profile.** A Turn makes at most
``max_tool_rounds + 1`` model calls at ``max_output_tokens`` each and is admitted
against ``owner_output_total``, so those three numbers are not free to be chosen
independently. :meth:`LaneProfile.__post_init__` refuses a profile where they
disagree, because the failure it prevents is silent: a lane that raised its
rounds without its total would spend the extra call being refused by admission,
and the Turn would end saying it ran out of budget rather than out of rounds.

**Routing is a seam, not a judgement.** :func:`route_intent` is a deterministic
heuristic that defaults to :data:`LIGHT` and reaches for :data:`DEEP` only when
the question has the shape of a memo request. It makes no model call and reads
nothing, which is what makes it testable and what keeps a misroute cheap: the
wrong lane is the wrong *ceiling*, and every safety property of the Turn holds on
either. Whether the heuristic picks well is a question for the phase that owns
answer quality and can measure it; what this file owns is that the decision is
typed, taken once, and carries the reason it was taken.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaneProfile:
    """The ceilings one Turn runs under, as one value.

    Every field is a bound on a different resource, and each has a reader that
    would otherwise reach for a constant: the loop reads the rounds, the
    external-call ceiling and the per-call output ceiling, ``turns.py`` reads the
    wall clock, and the ledger reads the two per-owner totals.
    """

    #: The stable name the lane is logged and reported under.
    name: str
    #: Tool rounds, counted by round: a round that fans out to five tools costs
    #: the same one step as a round that calls one.
    max_tool_rounds: int
    #: The whole Turn, wall clock, including the wait for an execution slot.
    deadline_seconds: float
    #: Calls to tools that cost money or reach off this deployment. A round cap
    #: alone does not bound this, because one round may fan out.
    max_external_calls: int
    #: What one model call may produce, reasoning included.
    max_output_tokens: int
    #: What every call of the Turn may produce together, as admission counts it.
    owner_output_total: int
    #: What every call of the Turn may send together, as admission counts it.
    owner_input_total: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a lane profile needs a name")
        for field_name in (
            "max_tool_rounds",
            "max_external_calls",
            "max_output_tokens",
            "owner_output_total",
            "owner_input_total",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{self.name}: {field_name} must be a positive int")
        if self.deadline_seconds <= 0:
            raise ValueError(f"{self.name}: deadline_seconds must be positive")
        calls = self.max_tool_rounds + 1
        expected = calls * self.max_output_tokens
        if self.owner_output_total != expected:
            raise ValueError(
                f"{self.name}: {calls} calls at {self.max_output_tokens} output "
                f"tokens need {expected} of aggregate output, not "
                f"{self.owner_output_total}"
            )


#: Today's numbers, and the lane almost every Turn gets.
#:
#: The values are the ones ``loop.py`` and ``turns.py`` have always used, so a
#: Turn on this lane behaves exactly as it did before lanes existed — that is the
#: property the lane test pins by comparing the two.
LIGHT = LaneProfile(
    name="light",
    max_tool_rounds=4,
    deadline_seconds=600.0,
    max_external_calls=7,
    max_output_tokens=4_000,
    owner_output_total=20_000,
    owner_input_total=100_000,
)

#: The lane for a question that asks for verification rather than a fact.
#:
#: Every number here is a two-way door: raising or lowering one changes what a
#: Turn may spend and nothing about how it spends it. The per-call output ceiling
#: is deliberately *not* raised — a longer answer is not what a memo needs; more
#: rounds of evidence is — and the aggregate totals follow the arithmetic from
#: the round count rather than being picked.
#:
#: The monetary ceiling is untouched by design. ``TURN_COST_MICRO_USD`` still
#: bounds the money, so a lane whose token ceilings turn out to be too generous
#: ends its Turn with a stated reason instead of quietly outspending the
#: envelope.
DEEP = LaneProfile(
    name="deep",
    max_tool_rounds=10,
    deadline_seconds=1_800.0,
    max_external_calls=20,
    max_output_tokens=4_000,
    owner_output_total=44_000,
    owner_input_total=280_000,
)

#: The words that make a question a verification request rather than a lookup.
#:
#: A tuple and not a set, because the reason string names the keyword that
#: matched and the first match must be the same one on every run.
#:
#: Matched as substrings against the casefolded question, which is why they are
#: written the way a reader types them. No diacritic folding: a reader who types
#: "kiem chung" gets the light lane, and that is the safe direction to be wrong
#: in — the ceiling is lower, every guard still holds, and the phase that can
#: measure routing quality owns making this cleverer.
DEEP_KEYWORDS: tuple[str, ...] = (
    "kiểm chứng",
    "luận điểm",
    "phản biện",
    "stress test",
    "memo",
    "thẩm định",
)

#: How long a question has to be before its length alone asks for the deep lane.
#:
#: A reader who writes this much has laid out a position with context, which is
#: the memo shape the keywords look for spelled out instead of named. Measured on
#: the whitespace-collapsed question so that a pasted block of line breaks is not
#: mistaken for length.
DEEP_MIN_CHARS = 240

#: The reason a Turn got the lane it got, when nothing in the question asked for
#: anything else.
DEFAULT_REASON = "default"


def normalise(user_text: str) -> str:
    """The question as the router reads it: one line, casefolded."""
    return " ".join(user_text.split()).casefold()


def route_reason(user_text: str) -> tuple[LaneProfile, str]:
    """The lane for this question, and the short machine reason it was chosen.

    The reason travels with the lane rather than being reconstructed later: a
    Turn that ran with generous ceilings has to be able to say *why* it was
    allowed to, and re-deriving that from the question after the fact would be a
    second copy of this function's rules.

    Pure, and deliberately so — no store read, no model call, no clock. A router
    that could fail is a router that can refuse a Turn before it starts.
    """
    text = normalise(user_text)
    for keyword in DEEP_KEYWORDS:
        if keyword in text:
            return DEEP, f"keyword:{keyword}"
    if len(text) >= DEEP_MIN_CHARS:
        return DEEP, f"length:{len(text)}"
    return LIGHT, DEFAULT_REASON


def route_intent(user_text: str) -> LaneProfile:
    """The lane for this question, for a caller that does not log the reason."""
    return route_reason(user_text)[0]


__all__ = [
    "DEEP",
    "DEEP_KEYWORDS",
    "DEEP_MIN_CHARS",
    "DEFAULT_REASON",
    "LIGHT",
    "LaneProfile",
    "normalise",
    "route_intent",
    "route_reason",
]

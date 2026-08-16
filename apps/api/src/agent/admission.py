"""Whether a Turn may be created at all, decided before anything is (#85).

``docs/adr/0013``'s two-request transport rests on one property: **an admission
failure never opens a stream**.  Folding admission into the stream would turn a
refusal into an in-band event the client has to parse, and it would make the
idempotency key arrive at the same moment as the work.  So the decision is taken
here, in front of the ``POST``, and it answers with an ordinary status code.

The ceilings themselves are not this module's.  They belong to
``docs/adr/0014`` and live in :class:`~src.core.llm.admission.SpendAdmission`,
which is also the authority that enforces them at dispatch.  What is here is the
part the ledger cannot own: the in-process semaphore, and the mapping from a
stable reason onto 429 or 503.

**The split between 429 and 503 is by whose allowance ran out, not by how.**
``user_active_turn`` is a capacity condition and a *user* one, so it is 429 — a
rule the caller can act on. ``system_active_turns`` is the same kind of
condition about everybody, so it is 503 with no ``Retry-After``: the only number
that could go there would be a guess at when someone else's Turn ends.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.alpha.refusals import AlphaRefusal
from src.core.llm.admission import BudgetRefusal

from .loop import DEFAULT_MAX_OUTPUT_TOKENS, SessionSlots


class TurnPreflight(Protocol):
    """The one thing admission needs from the spend ledger.

    Narrower than :class:`~src.core.llm.admission.AdmissionLedger` on purpose:
    this module must not be able to reserve anything, and a type that could
    would be an invitation to.
    """

    def preflight_turn(self, user_id: int, *, output_tokens: int) -> None: ...

# Every reason ``SpendAdmission`` can refuse a Turn with, and the status each
# one is. Exhaustive on purpose: a reason with no entry here would fall through
# to a 500, turning a rule the user could act on into an outage they cannot.
ADMISSION_STATUS: dict[str, int] = {
    "user_turn_starts_daily": 429,
    "user_active_turn": 429,
    "user_spend_daily": 429,
    "user_spend_rolling_30d": 429,
    "lane_budget_exhausted": 503,
    "system_active_turns": 503,
}

# Anything unmapped is a refusal this module did not anticipate. 503 rather than
# 500, because every ceiling in ADR-0014 is a temporary condition and none of
# them is a fault.
UNMAPPED_STATUS = 503


class TurnRefused(AlphaRefusal):
    """A Turn refused at admission, before a row or a stream existed.

    An :class:`AlphaRefusal` so the application's existing handler answers it
    with the same ``{reason, message}`` body as every other refusal in Alpha
    Desk — a capacity refusal should read the same whether it was caught at the
    route, at the semaphore, or at the ledger.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        status_code: int,
        *,
        reset_at: datetime | None = None,
    ) -> None:
        super().__init__(reason=reason, message=message, status_code=status_code)
        self.reset_at = reset_at

    @classmethod
    def of(cls, refusal: BudgetRefusal) -> "TurnRefused":
        """Carry the ledger's own reason and sentence onto the wire unchanged."""
        return cls(
            reason=refusal.reason,
            message=refusal.message,
            status_code=ADMISSION_STATUS.get(refusal.reason, UNMAPPED_STATUS),
            reset_at=refusal.reset_at,
        )


class TurnAdmission:
    """The one question the ``POST`` asks before it creates anything."""

    def __init__(
        self,
        spend: TurnPreflight,
        *,
        slots: SessionSlots,
        output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> None:
        self._spend = spend
        self._slots = slots
        self._output_tokens = output_tokens

    def admit(self, *, user_id: int) -> None:
        """Return quietly, or refuse with the reason and the status.

        The semaphore is asked first and costs no query. The two checks answer
        the same question from opposite sides — the ledger counts active rows
        across the deployment, the semaphore counts running tasks in this
        process — and either one being full is a full service.
        """
        if self._slots.full:
            raise TurnRefused(
                reason="system_active_turns",
                message="The service is at its active Turn capacity. Try again shortly.",
                status_code=503,
            )
        try:
            self._spend.preflight_turn(user_id, output_tokens=self._output_tokens)
        except BudgetRefusal as refusal:
            raise TurnRefused.of(refusal) from refusal


__all__ = [
    "ADMISSION_STATUS",
    "UNMAPPED_STATUS",
    "TurnAdmission",
    "TurnPreflight",
    "TurnRefused",
]

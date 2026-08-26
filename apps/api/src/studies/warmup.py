"""Making sure the inputs a Study declared are in the store before it reads them.

A Study reads the store and nothing else — that is what makes it deterministic
and what lets an artifact be re-rendered a week later without a provider in the
path. But a question arrives about a symbol nobody has asked about yet, and the
store's answer for it is "nothing", which is a refusal a reader would read as a
statement about the company.

So the gap is closed here, once, before ``compute`` runs: each name in
``StudyDefinition.requires`` maps to one function that makes that input present.
Three things about the arrangement are deliberate.

**It is passed in rather than imported by the runner.** ``runner.run`` takes this
as an argument and defaults to doing nothing, so the one path that talks to a
provider is the one a live question travels — the suite, the smoke script and any
later precompute choose whether to reach the network rather than discovering that
they have.

**A requirement is a name in a table, not a string a Study invents.** The
registry refuses a Study whose ``requires`` names something no warmer here
answers, at import, because the alternative is finding out on a real question
that the input was never fetched.

**One symbol per call.** The tool loop bounds a round at thirty seconds and a
cold symbol costs two to three of them; a Study that wanted five would spend the
round and answer nothing. It refuses instead, naming ``cohort_warming``, which is
the vocabulary the serving path already uses for "the data is on its way".
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.stocks.intraday import ingest
from src.stocks.signals.issues import SignalIssue

from .contracts import KNOWN_REQUIREMENTS, StudyContext, StudyDefinition, StudyRefused

#: How many sessions a warmer fetches when the params do not say. A Study whose
#: window is implicit still needs a floor, and this is the smallest window any
#: registered Study accepts.
DEFAULT_SESSIONS = 30

Warmer = Callable[[Session, BaseModel], None]


def _intraday_bars(session: Session, params: BaseModel) -> None:
    """Fetch fifteen-minute bars for the one symbol these params name."""
    symbols = getattr(params, "symbols", None)
    if symbols is not None and len(tuple(symbols)) > 1:
        raise StudyRefused(
            SignalIssue.COHORT_WARMING,
            "this call would have to fetch intraday bars for "
            f"{len(tuple(symbols))} symbols, which does not fit one round; ask "
            "about one symbol at a time",
        )
    symbol = getattr(params, "symbol", None) or (
        tuple(symbols)[0] if symbols else None
    )
    if not symbol:
        raise StudyRefused(
            SignalIssue.MISSING_TARGET_SESSION,
            "this study reads intraday bars and its parameters name no symbol",
        )
    sessions = getattr(params, "sessions", DEFAULT_SESSIONS)
    ingest.ensure_bars(session, str(symbol), sessions=int(sessions))


#: Every input a Study may declare, and what makes it present.
#:
#: The single source for both directions: the registry checks a declaration
#: against these names at import, and :func:`warm` dispatches through them at
#: run time. A requirement with no warmer would be a promise nothing keeps.
WARMERS: Mapping[str, Warmer] = {
    "intraday_bar_15m": _intraday_bars,
}


if set(WARMERS) != set(KNOWN_REQUIREMENTS):  # pragma: no cover - guards a typo
    raise ImportError(
        "the declarable requirements and the fetchable ones have to be the same "
        f"set; declarable: {sorted(KNOWN_REQUIREMENTS)}, fetchable: "
        f"{sorted(WARMERS)}"
    )


def known(requirement: str) -> bool:
    """Whether anything here can make this input present."""
    return requirement in WARMERS


def warm(definition: StudyDefinition, context: StudyContext) -> None:
    """Make every input this Study declared present, in declaration order."""
    for requirement in definition.requires:
        warmer = WARMERS.get(requirement)
        if warmer is None:  # pragma: no cover - the registry refuses these
            raise KeyError(
                f"study {definition.name!r} requires {requirement!r}, which "
                "nothing knows how to fetch"
            )
        warmer(context.session, context.params)


__all__ = ["DEFAULT_SESSIONS", "WARMERS", "Warmer", "known", "warm"]

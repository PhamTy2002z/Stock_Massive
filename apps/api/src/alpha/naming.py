"""How Alpha Desk names a session to a person, in one place.

*"phiên 12/08"* — dated, and never "today". The latest session with a Snapshot
is frequently not today, so a sentence that says "today" is wrong in exactly the
places these sentences appear: a refusal, a status line, the label on a rail.

One function rather than a `strftime` at each call site. Three of them had
already drifted to two different formats, and a user reading "phiên 12/08" in
one sentence and "phiên 12/08/2026" in the next has to work out whether they are
being told about the same session.
"""

from datetime import date


def session_label(trading_day: date) -> str:
    """A Trading Day as the interface names it: ``phiên dd/mm``."""
    return f"phiên {trading_day.strftime('%d/%m')}"

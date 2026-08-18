"""Which days the exchange is open, as far as this system knows.

Its own module because more than one scheduled run asks the question, and the
answer belongs to neither of them.
"""

from datetime import date


def is_trading_day(day: date) -> bool:
    """Report whether the exchange trades on this day, by weekday alone.

    There is no holiday calendar behind this. Tet and the public holidays read
    as trading days here, so a job gated on it still fires on days the exchange
    is shut — it finds nothing, records that, and costs a call. Saying so is
    better than a docstring that claims holidays are handled.

    Which is why this answers one question only: should a run be attempted
    today. It must never date anything. A Snapshot, an Analysis, or a signal is
    labelled with a **Trading Day**, which ``src.stocks.trading_day`` derives
    from the sessions actually held rather than from the day of the week.
    """
    return day.weekday() < 5

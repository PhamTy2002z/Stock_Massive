"""The one vocabulary for why a signal answer is less than whole.

One enum rather than one per module, because **Signal Issue** is a single domain
term (`CONTEXT.md`) and ADR-0006 grows *this* set rather than opening a second
one. A per-module vocabulary would let two modules spell the same condition two
ways, and the web app holds one Vietnamese sentence per code — a synonym is a
blank on the screen.

It lived inside ``volume_spike`` while that was the only module raising one.
Moved here when the band regime became the second, with nothing else changed:
the codes and their strings are the ones already on the wire.
"""

from __future__ import annotations

from enum import Enum


class SignalIssue(str, Enum):
    """Why an answer is less than whole. A closed set, by design.

    These are domain provenance, not transport failures: they travel in the body
    of a 200 response, never as an HTTP status and never as prose. A closed set
    is what lets the web app hold one Vietnamese sentence per code instead of
    rendering whatever the API happened to say.
    """

    # The store holds no session for this symbol on the day being answered for.
    # Not the same as a session in which nothing happened.
    MISSING_TARGET_SESSION = "missing_target_session"
    INSUFFICIENT_HISTORY = "insufficient_history"
    RECENTLY_INACTIVE = "recently_inactive"
    COHORT_WARMING = "cohort_warming"
    LAGGING_MARKET_DATA = "lagging_market_data"
    STALE_MARKET_DATA = "stale_market_data"
    RANKING_UNAVAILABLE = "ranking_unavailable"

    # --- Price Basis, from ADR-0006 -------------------------------------
    # The sessions being read together do not share a basis: the window crosses
    # the seam between a symbol's Cover Source history and its collected era.
    # Meaningless rather than degraded — a raw close and an adjusted one are not
    # two measurements of the same thing.
    MIXED_PRICE_BASIS = "mixed_price_basis"

    # The sessions being read are all `adjusted_at_source`. Refused not for
    # being mixed but because that basis was fixed at `observed_at`, decays with
    # every corporate action since, and cannot be recomputed from what is stored.
    UNADJUSTABLE_PRICE_BASIS = "unadjustable_price_basis"

    # --- Price band, dated per session ----------------------------------
    # No board for this symbol on this date, so no band either.
    EXCHANGE_UNKNOWN = "exchange_unknown"

    # The session is held without a high and a low, so where inside its band it
    # traded is unknown. A close at the ceiling is not a lock.
    SESSION_PRICES_INCOMPLETE = "session_prices_incomplete"

    # The reference this board's band is measured from is not in the store and
    # is not derivable from it: UPCOM's prior-day round-lot continuous VWAP.
    ANCHOR_NOT_STORED = "anchor_not_stored"

    # The symbol has no stored session on the trading day before this one, so
    # there is no previous close to anchor to.
    ANCHOR_MISSING = "anchor_missing"

    # --- Corporate Actions, from ADR-0006 --------------------------------
    # An action falling in the window has no ex-date, or has one the raw prices
    # do not corroborate. It may not drive arithmetic, so the window is degraded
    # rather than adjusted: something happened to this symbol that the series
    # cannot be made comparable across.
    UNCONFIRMED_CORPORATE_ACTION = "unconfirmed_corporate_action"

    # A confirmed action whose declared terms do not add up to a factor. The
    # measured case is a rights issue: the subscription price is not in the
    # provider's feed, and the par value it is usually set at is knowledge from
    # outside the row. Distinct from the code above because nothing here is in
    # doubt about *whether* the action happened.
    CORPORATE_ACTION_TERMS_INCOMPLETE = "corporate_action_terms_incomplete"

    # The session moved further than its band permits, which means the anchor is
    # wrong rather than that the market broke — an ex-date the exchange adjusted
    # its reference for and the previous close did not follow. Deliberately not
    # `unexplained_price_gap`: that one asserts no Corporate Action accounts for
    # the move, and until the action series exists nothing has looked. This code
    # reports only what was measured, and is the input the gap refusal is built
    # from.
    PRICE_MOVE_EXCEEDS_BAND = "price_move_exceeds_band"

    # --- The window gateway, from ADR-0006 and ADR-0010 -------------------
    # The one above, after the action series has been looked in and found to
    # hold nothing on that date. A window carrying a price move nothing
    # explains is refused rather than served: the move is either an action this
    # system does not hold or an anchor that is wrong, and both make every
    # price on one side of it incomparable with every price on the other.
    UNEXPLAINED_PRICE_GAP = "unexplained_price_gap"

    # A share-count-changing action falls inside the window, so the unit of
    # every `*_volume` field changes partway through it. A degradation rather
    # than a refusal, because prices are made comparable across the same action
    # and money never needed to be: a billion dong traded is a billion dong
    # traded on either side of a split (`docs/adr/0006`).
    VOLUME_BASIS_BREAK = "volume_basis_break"

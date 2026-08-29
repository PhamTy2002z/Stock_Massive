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

    # A Study needs whole sessions rather than a shortened window: a liquidity
    # profile over eight sessions is a picture of eight days, not of a habit.
    # Distinct from INSUFFICIENT_HISTORY, which is about a field's lookback over
    # daily bars; this one counts intraday sessions actually stored.
    INSUFFICIENT_SESSIONS = "insufficient_sessions"

    # The session being asked about has not reached the store yet. Distinct
    # from MISSING_TARGET_SESSION, which says the day held no session at all:
    # this one says the session is expected to exist and its bars have not
    # arrived. It is raised rather than quietly answering from the session
    # before, because a picture of yesterday captioned "today" is the one
    # wrong answer that looks exactly like a right one.
    SESSION_NOT_INGESTED = "session_not_ingested"

    # --- Price Basis, from ADR-0006 -------------------------------------
    # The sessions being read together do not share a basis: the window crosses
    # the seam between a symbol's Cover Source history and its collected era.
    # Meaningless rather than degraded — a raw close and an adjusted one are not
    # two measurements of the same thing.
    MIXED_PRICE_BASIS = "mixed_price_basis"

    # The sessions being read are all `adjusted_at_source`, and the question
    # asked of them is about a *published* price.
    #
    # **Narrowed when the daily spine became the source of sessions.** It used
    # to refuse any window on this basis, which today would refuse every window
    # there is. A window that is adjusted throughout is internally consistent and
    # is served: every ratio taken over it is unchanged by the constant it is
    # scaled by. What it cannot answer is what the exchange printed — the band a
    # session traded inside is a percentage of a published reference price, and
    # a rebased close is not that number. So this now names one question that
    # cannot be answered rather than one window that cannot be read, and it is
    # raised by `price_band._basis_of_the_pair`, never by the window gateway.
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

    # The prices this session is held at are not on the board's quoting grid, so
    # they are not the prices the exchange printed and a band cannot be measured
    # against them.
    #
    # Every limit price sits on a tick by construction — the exchange would not
    # accept an order anywhere else — so a stored price off the grid has been
    # multiplied by a factor since it was published. That makes it a fine input
    # for a ratio and an impossible one for the question "did this session trade
    # *at* its limit", which is an equality against a grid-rounded number.
    #
    # This is the price basis rule made per-session rather than per-window. A
    # window adjusted throughout is served, and most of its sessions still carry
    # the published prices because most symbols have no entitlement in the
    # window; the ones that were rebased say so here instead of quietly reporting
    # that no session ever reached its band.
    #
    # It is necessary and not sufficient, and the docstring on the check says so:
    # a rebased price can land back on the grid by coincidence. It removes the
    # bulk of the bad verdicts, and it does not pretend to be a proof.
    PRICE_OFF_TICK_GRID = "price_off_tick_grid"

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

    # --- The statistical bar, from ADR-0010 ------------------------------
    # A robust baseline every reading of which was identical, so its
    # median absolute deviation is zero and nothing can be measured in
    # sigmas of it. Live rather than defensive: a thin name that matched at
    # the same price every session of the window has exactly this baseline,
    # and dividing by it would report the first session that moved as an
    # unbounded excursion. Distinct from `insufficient_history`, which is
    # about how many sessions there were rather than what was in them.
    BASELINE_DISPERSION_ZERO = "baseline_dispersion_zero"

    # The session being judged traded at one price all day, so a range-based
    # reading of it has nothing to read. Covers both ways that happens: an order
    # book locked at a limit, and a thin name that matched once and never again.
    # Deliberately one code for the two, because what the estimator is short of
    # is the same thing either way, and which of them it was is already on the
    # window's limit-lock count.
    ZERO_RANGE_SESSION = "zero_range_session"

    # Too few sessions closed below the benchmark for a downside deviation to
    # mean anything. Sortino's discrete downside deviation is documented as
    # unstable on a handful of observations (Sortino & Forsey 1996), so the
    # ratio is withheld rather than printed with a caveat nobody reads.
    INSUFFICIENT_DOWNSIDE_OBSERVATIONS = "insufficient_downside_observations"

    # The returns are autocorrelated strongly enough negatively that Lo's
    # corrected annualization has no positive variance to take a root of. Rare,
    # and refused rather than fallen back from: √252 is precisely the number the
    # correction exists to refuse, so reaching for it here would be answering
    # with the error the check was for.
    AUTOCORRELATION_UNUSABLE = "autocorrelation_unusable"

    # The field is registered and has no inputs in the store today. Declared
    # rather than dropped, because a profile silently missing a field would make
    # two Analyses carrying the same profile version mean different things
    # (spec 0003 §8.4, §13). The input it is short of travels with it, and no
    # live Provider Source read is ever substituted to fill the slot.
    UNAVAILABLE = "unavailable"

    # A window prepared for quantities rather than for prices, so no session in
    # it was judged against a band. Not a data gap: nobody asked. A price-band
    # field handed such a window is asking the wrong window rather than meeting
    # a market it could not judge, and the two would be indistinguishable under
    # any of the codes above.
    BAND_NOT_MEASURED = "band_not_measured"

    # The instrument this window is drawn from has no price band at all: a
    # market index sits on no board, so there is no reference price to take a
    # percentage of and no limit for a session to lock at (`docs/adr/0017`).
    # Deliberately neither `exchange_unknown` — which says a board exists and
    # nothing named it — nor `band_not_measured`, which says a band exists and
    # this window did not ask for one. Here the band does not exist, and a field
    # reaching for one is asking the wrong instrument.
    BAND_NOT_APPLICABLE = "band_not_applicable"

    # --- Traded figures, from ADR-0010 -----------------------------------
    # A session inside the window carries no traded figure at all — no money on
    # a money-denominated average, no share count on a share-denominated one.
    # Distinct from `insufficient_history`, which is about how many sessions the
    # window reached: here every session is present and one of them is blank, and
    # averaging the rest would produce an average over a different stretch of
    # market than the symbol beside it.
    TRADED_FIGURE_NOT_STORED = "traded_figure_not_stored"

    # Every session in the window traded nothing, so a ratio measured per unit
    # of traded money has no observation to average. A fact about the symbol
    # rather than about the store, and the one a reader of a thin UPCOM name
    # most needs.
    NO_TRADED_SESSIONS = "no_traded_sessions"

    # The window holds a session with no foreign flow figure, so a sum or a run
    # over it would be a sum through a hole. Its own code rather than the traded
    # figure above, because the two are different collection gaps with different
    # fixes: one is the session's turnover, the other is its foreign split.
    FOREIGN_FLOW_NOT_STORED = "foreign_flow_not_stored"

    # No reference reading of this symbol's foreign ownership room is stored at
    # or before the date being answered for, so the room percentage has nothing
    # to report. Deliberately not the same as a room that is full: an
    # uncollected room is unknown, and reporting it as open would assert the
    # thing nobody looked at.
    FOREIGN_ROOM_NOT_STORED = "foreign_room_not_stored"

    # The symbol's foreign ownership room is full, or full enough to stop
    # buying by itself, so a foreign flow measured over the window was
    # mechanically constrained rather than freely chosen. A degradation because
    # the number is real: what changes is that it may not be read as a change of
    # view. Its absence from a window is not this code — an uncollected room is
    # reported as unknown rather than as open.
    FOREIGN_ROOM_EXHAUSTED = "foreign_room_exhausted"

    # --- Cross-sectional fields, from ADR-0010 ---------------------------
    # Fewer symbols survived exclusion than a percentile can be taken over. A
    # position within a sample of eleven is a rank wearing a distribution's
    # clothes, so the whole call refuses rather than each surviving symbol
    # answering with a number nobody can read.
    INSUFFICIENT_CROSS_SECTION = "insufficient_cross_section"

    # The newest quarterly statement behind a stored figure is old enough that
    # narrating it as current would be wrong. A degradation rather than a
    # refusal: the number is real and was true of its quarter, and the quarter
    # is stamped beside it.
    STALE_FUNDAMENTAL_PERIOD = "stale_fundamental_period"

    # The store holds no quarterly statement for this symbol at or before the
    # date being ranked, so there is nothing to rank it on. Distinct from the
    # code above, which is about a figure that exists and is old.
    FUNDAMENTAL_NOT_STORED = "fundamental_not_stored"

    # A statement is stored for this symbol, and the line this particular ratio
    # divides is not in it. Distinct from the code above, and the distinction is
    # the whole point: `fundamental_not_stored` sends a reader to look for a
    # filing that is already there, while this one names a gap inside a filing
    # that was collected. Two ratios over the same statement can disagree about
    # which of them is answerable, and this is the code that says so.
    STATEMENT_LINE_MISSING = "statement_line_missing"

    # No session in the window read carries a market capitalisation, so a ratio
    # measured against what the market values the company at cannot be formed.
    # It is not a statement about the filings: the quarter behind the numerator
    # may be stored, current and perfectly readable, and a ratio over it still
    # has no denominator. Reported under its own name because the fix is on the
    # market side of the store rather than the fundamental one.
    MARKET_CAP_ABSENT = "market_cap_absent"

    # The market capitalisation a ratio was formed against comes from an earlier
    # session than the newest one in the window — the provider wrote one on some
    # sessions and not on others. A degradation rather than a refusal: the ratio
    # is real as of the session its denominator came from, and that session is
    # stamped beside it. Its own code rather than `stale_market_data`, which is
    # about a whole window falling behind the calendar; here the window is
    # current and one field inside it is not.
    STALE_MARKET_CAP = "stale_market_cap"

    # The newest reference reading behind a stored figure is old enough that
    # narrating it as current would be wrong. The reference twin of
    # `stale_fundamental_period`, and a separate code because the two are
    # different collection cadences with different fixes: one is a quarterly
    # filing, the other is a daily board read that stopped. A degradation rather
    # than a refusal — the number is real and the date it was read travels with
    # it.
    STALE_REFERENCE_READING = "stale_reference_reading"

    # The fitted AR(1) half-life reaches the window the gauge was fitted over,
    # which includes a series carrying no reversion at all — the estimate is
    # unbounded there rather than merely large. Past that point a z against the
    # window's own trailing mean is measuring the window rather than the market,
    # so the z is suppressed rather than served with a caveat beside it.
    HALF_LIFE_EXCEEDS_WINDOW = "half_life_exceeds_window"

    # More than a fifth of the window was locked at a limit, so a range-based
    # estimate over it is measuring the band rather than the market. A
    # degradation with a name, not a refusal: the sessions are real and the
    # number is computable, it is the reading of it that has to change.
    LIMIT_LOCKED_WINDOW = "limit_locked_window"

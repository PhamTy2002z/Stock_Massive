"""What an Analysis says in place of a number.

A refused figure stays in the artifact with ``value: null``, and both readers of
it need a sentence: the model, which is shown the whole profile including its
refusals so it can choose emphasis honestly, and a person reading the artifact,
for whom a refusal displayed as honesty evidence is only evidence if it says
something.

The sentences are here and not in ``src/stocks/signals/issues.py`` because the
audiences are different and so is the language. That module owns the closed set
of **Signal Issue** codes; the web app holds one Vietnamese sentence per code
for the surfaces a person reads in Vietnamese; this holds one English sentence
per code for the artifact the model is handed. A code with no sentence here
fails ``tests/test_envelope.py``, so the set cannot grow past the prose.

Every sentence says what is missing or what changed, never what to do about it.
A reason that advised a reader would be the recommendation the whole citation
contract exists to keep out of a figure.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from src.stocks.signals.issues import SignalIssue

SIGNAL_ISSUE_SENTENCES: Mapping[SignalIssue, str] = MappingProxyType(
    {
        SignalIssue.MISSING_TARGET_SESSION: (
            "The store holds no session for this symbol on the day being "
            "answered for."
        ),
        SignalIssue.INSUFFICIENT_SESSIONS: (
            "The store holds fewer whole intraday sessions than this study needs, "
            "so no profile was computed over a shortened window."
        ),
        SignalIssue.SESSION_NOT_INGESTED: (
            "The session being asked about is not in the store: it may not have "
            "opened yet, its bars may not have arrived, or the market may not be "
            "trading that day. Nothing was answered from an earlier session "
            "under its name."
        ),
        SignalIssue.INSUFFICIENT_HISTORY: (
            "The store holds fewer sessions than this figure needs, so it was "
            "not computed over a shortened window."
        ),
        SignalIssue.RECENTLY_INACTIVE: (
            "At least one session in the window traded nothing at all, so a "
            "return from inactivity is not being presented as ordinary flow."
        ),
        SignalIssue.COHORT_WARMING: (
            "The cohort this figure is measured within is still loading its "
            "history."
        ),
        SignalIssue.LAGGING_MARKET_DATA: (
            "A newer Trading Day exists that this figure could not yet be "
            "computed for."
        ),
        SignalIssue.STALE_MARKET_DATA: (
            "The newest market data behind this figure is more than a week old."
        ),
        SignalIssue.RANKING_UNAVAILABLE: (
            "No ranking is currently published for this figure to be placed in."
        ),
        SignalIssue.MIXED_PRICE_BASIS: (
            "The sessions this window folds do not share one price basis, so a "
            "raw close and a provider-adjusted close would have been compared "
            "as if they measured the same thing."
        ),
        SignalIssue.UNADJUSTABLE_PRICE_BASIS: (
            "Every session in this window was adjusted by the provider at "
            "collection time, and that adjustment cannot be undone from what is "
            "stored."
        ),
        SignalIssue.EXCHANGE_UNKNOWN: (
            "No board is recorded for this symbol on these dates, so its price "
            "band could not be read."
        ),
        SignalIssue.SESSION_PRICES_INCOMPLETE: (
            "A session in the window is held without a high and a low, so where "
            "inside its band it traded is unknown."
        ),
        SignalIssue.ANCHOR_NOT_STORED: (
            "This board measures its band from a reference this system does not "
            "store and cannot reconstruct."
        ),
        SignalIssue.ANCHOR_MISSING: (
            "The session before the window's oldest one is not stored, so there "
            "is no previous close to anchor the band to."
        ),
        SignalIssue.PRICE_OFF_TICK_GRID: (
            "A session in this window is held at prices that are not on the "
            "board's quoting steps, so they are not the prices the exchange "
            "printed and its band cannot be measured against them."
        ),
        SignalIssue.UNCONFIRMED_CORPORATE_ACTION: (
            "A corporate action falling in this window has no ex-date the stored "
            "prices corroborate, so it may not drive arithmetic."
        ),
        SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE: (
            "A confirmed corporate action in this window declares terms that do "
            "not add up to an adjustment factor."
        ),
        SignalIssue.PRICE_MOVE_EXCEEDS_BAND: (
            "A session in this window moved further than its band permits, which "
            "means the anchor is wrong rather than that the market was."
        ),
        SignalIssue.UNEXPLAINED_PRICE_GAP: (
            "A session in this window moved past its band and no stored "
            "corporate action accounts for it, so prices either side of it are "
            "not comparable."
        ),
        SignalIssue.VOLUME_BASIS_BREAK: (
            "A share-count-changing action falls inside this window, so a "
            "share-denominated figure changes unit partway through it."
        ),
        SignalIssue.BASELINE_DISPERSION_ZERO: (
            "Every reading in the robust baseline was identical, so there is no "
            "dispersion to measure this figure in."
        ),
        SignalIssue.ZERO_RANGE_SESSION: (
            "The session being judged traded at one price all day, so a "
            "range-based reading of it has nothing to read."
        ),
        SignalIssue.INSUFFICIENT_DOWNSIDE_OBSERVATIONS: (
            "Too few sessions closed below the benchmark for a downside "
            "deviation to mean anything."
        ),
        SignalIssue.AUTOCORRELATION_UNUSABLE: (
            "The returns are autocorrelated strongly enough that the corrected "
            "annualization has no positive variance to take a root of."
        ),
        SignalIssue.UNAVAILABLE: (
            "The Analysis Field Profile names this field and no durable store "
            "holds its inputs yet, so it is declared rather than dropped."
        ),
        SignalIssue.BAND_NOT_MEASURED: (
            "This window was prepared for quantities rather than prices, so no "
            "session in it was judged against a band."
        ),
        SignalIssue.BAND_NOT_APPLICABLE: (
            "The instrument behind this window sits on no board, so it has no "
            "price band at all."
        ),
        SignalIssue.TRADED_FIGURE_NOT_STORED: (
            "A session inside the window carries no traded figure, so an average "
            "over the rest would cover a different stretch of market."
        ),
        SignalIssue.NO_TRADED_SESSIONS: (
            "Every session in the window traded nothing, so a figure measured "
            "per unit of traded money has no observation to average."
        ),
        SignalIssue.FOREIGN_FLOW_NOT_STORED: (
            "A session in the window carries no foreign flow figure, so a sum "
            "over it would be a sum through a hole."
        ),
        SignalIssue.FOREIGN_ROOM_NOT_STORED: (
            "No reference reading of this symbol's foreign ownership room is "
            "stored at or before this session."
        ),
        SignalIssue.FOREIGN_ROOM_EXHAUSTED: (
            "The foreign ownership room is full enough to stop buying by itself, "
            "so the flow beside it was mechanically constrained rather than "
            "freely chosen."
        ),
        SignalIssue.INSUFFICIENT_CROSS_SECTION: (
            "Too few symbols were evaluable for a percentile over them to mean "
            "anything."
        ),
        SignalIssue.STALE_FUNDAMENTAL_PERIOD: (
            "The newest quarterly statement behind this figure is old enough "
            "that narrating it as current would be wrong; the period it covers "
            "is stamped beside it."
        ),
        SignalIssue.FUNDAMENTAL_NOT_STORED: (
            "The store holds no quarterly statement for this symbol at or before "
            "this session."
        ),
        SignalIssue.STATEMENT_LINE_MISSING: (
            "A quarterly statement is stored for this symbol and the line this "
            "figure divides is not in it."
        ),
        SignalIssue.MARKET_CAP_ABSENT: (
            "No session in the window read carries a market capitalisation, so "
            "there is nothing to measure this figure against."
        ),
        SignalIssue.STALE_MARKET_CAP: (
            "The market capitalisation behind this figure comes from an earlier "
            "session than the newest one in the window; that session is stamped "
            "beside it."
        ),
        SignalIssue.STALE_REFERENCE_READING: (
            "The reference reading behind this figure is old enough that "
            "narrating it as current would be wrong; the date it was read is "
            "stamped beside it."
        ),
        SignalIssue.HALF_LIFE_EXCEEDS_WINDOW: (
            "The fitted mean-reversion half-life reaches past the window it was "
            "fitted over, so a z-score against that window measures the window."
        ),
        SignalIssue.LIMIT_LOCKED_WINDOW: (
            "More than a fifth of the window was locked at a limit, so a "
            "range-based estimate over it is measuring the band rather than the "
            "market."
        ),
    }
)


def sentence_for(issue: SignalIssue) -> str:
    """The one sentence this code says in an Analysis.

    ``KeyError`` rather than a fallback: a code with no sentence is a gap in the
    artifact, and a generic "not available" printed in its place would hide the
    gap behind text that reads like an answer.
    """
    return SIGNAL_ISSUE_SENTENCES[issue]


__all__ = ["SIGNAL_ISSUE_SENTENCES", "sentence_for"]

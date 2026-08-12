# Research: quant methods that survive daily EOD Vietnamese equities

Resolves issue #39. Question: which quantitative methods earn a place in the agent's
computation tool catalog, given daily EOD OHLCV only, a 100-symbol HOSE/HNX/UPCOM
universe, foreign flow + fundamentals, no shorting, daily price bands, limit-lock
days, and T+2 settlement — judged against five criteria: EOD-computability,
statistical honesty (a real null, trailing windows only), LLM-narratable output,
VN-microstructure survival, and long-only actionability.

Method: primary sources only, gathered 2026-08-12 by five parallel reviews — the
original papers (Parkinson 1980, Garman-Klass 1980, Rogers-Satchell 1991, Yang-Zhang
2000, Jegadeesh-Titman 1993, Moskowitz-Ooi-Pedersen 2012, Engle-Granger 1987,
Johansen 1991, Gatev et al. 2006, Kelly 1956, Lo 2002, Ledoit-Wolf 2003/2004,
Hamilton 1989, White 2000, Sullivan-Timmermann-White 1999, Amihud 2002), the
published Vietnam/EM literature, and the exchange rules themselves (HOSE's own
Feb-2026 trading-rules document, VNX Decisions 22/23/QĐ-HĐTV, VSDC settlement
regulation 39/QĐ-HĐTV 2025). Verification grade is stated per claim: **full text**,
**abstract**, **secondary-confirmed**, or **unverified**. Nothing below rests on a
blog post.

## TL;DR — ranked shortlist (build these 14)

| # | Tool | Computes | Output contract (units, sign) | Null calibration | Top VN hazard |
|---|------|----------|-------------------------------|------------------|---------------|
| 1 | `realized_volatility` | Yang-Zhang vol (GK/Parkinson/RS as components) over a trailing duration window | annualized %, always ≥ 0; no sign | none needed (descriptive estimator) | limit-lock bars contribute 0 range → downward bias; report `limit_days_in_window` |
| 2 | `volatility_regime` | GK variance z vs trailing median/MAD (the #31 keep) | robust z; + = vol elevated vs own recent history | GBM simulation at matched vol; FPR ≤ 1% | limit-lock days deflate MAD and inflate z elsewhere — exclude them from the baseline |
| 3 | `momentum_rank` | cross-sectional 12-1 return rank within the Universe | percentile 0–100 (+ = winner) plus raw % return | percentile is self-calibrating; block-bootstrap CI on the raw return | band truncation spreads one shock over days — never read a 1-day rank |
| 4 | `foreign_flow_pressure` | trailing net foreign buy value / ADTV + persistence run-length | ratio (+ = net foreign buying), days of streak | block permutation of daily net flows | room-limit ceilings mechanically stop buying; VN predictiveness itself is **unverified** |
| 5 | `drawdown_stats` | max/current drawdown, days underwater, vs E[MDD] ≈ 1.25σ√T | %, ≤ 0 by convention; days | closed-form Brownian benchmark (Magdon-Ismail et al. 2004) | band slows crashes: a −30% drawdown takes ≥ 5 sessions on HOSE |
| 6 | `liquidity_profile` | ADTV, Amihud ILLIQ, zero-volume + limit-lock day counts | VND, %/bn-VND (higher = more illiquid), counts | cross-sectional percentile within Universe | UPCOM thin trading is the point — this tool gates the others |
| 7 | `band_pressure` | limit-day counts, closes-at-band, distance to today's ceiling/floor | % distance, counts; + = room above | descriptive; base rates from own trailing history | UPCOM band anchors to prior-day VWAP, not close; HNX→HOSE migration changes the band mid-history |
| 8 | `risk_adjusted_return` | Sharpe with Lo (2002) SE + CI; Sortino with downside-obs count | dimensionless ratio + 95% CI; + = above benchmark | the CI **is** the calibration; refuse √252 annualization when autocorrelation is significant | short samples: SE ≈ √((1+SR²/2)/T) makes most 60-day Sharpes indistinguishable from 0 |
| 9 | `trend_signal` | time-series momentum: sign of past 12m (and 3m/6m) total return | sign −1/0/+1 per window + magnitude % | sign test vs block bootstrap | evidence is from futures (MOP 2012) — extrapolation to single VN stocks, flagged in contract |
| 10 | `mean_reversion_gauge` | z vs trailing mean + AR(1) half-life; descriptive only | z (+ = above own mean); half-life in days | report half-life CI via block bootstrap; suppress z when half-life ≥ window | T+2 settlement: signals with half-life < 3 days are not actionable — tool says so |
| 11 | `relative_strength` | rolling beta/correlation vs VN-Index; Ledoit-Wolf shrinkage for any matrix ask | β dimensionless; ρ ∈ [−1,1]; shrinkage intensity reported | shrinkage intensity δ̂ is the honesty signal (δ̂→1 = data insufficient) | 100×100 matrix on 250 obs is exactly Ledoit-Wolf's ill-conditioned regime |
| 12 | `factor_percentiles` | E/P, B/P, ROE, size percentile within the Universe | percentile 0–100 (+ = cheaper/more profitable/smaller) | cross-sectional rank is self-calibrating | VN evidence: E/P beats B/M (Huang-Liu-Shu 2023); quarterly staleness must be stamped |
| 13 | `indicator_pack` | RSI, MACD, Bollinger %B — **descriptive vocabulary only** | indicator units; contract states "no post-1986 statistical edge (STW 1999)" | none — the contract forbids signal language | users expect them; the tool exists so the agent cites them honestly |
| 14 | `position_size_kelly` | fractional Kelly (≤ half) from user-supplied edge/variance | % of capital, capped; full-Kelly figure shown only as the ceiling | n/a (arithmetic); input-sensitivity range mandatory | estimation error in the mean dominates (MTZ 2010); tool never estimates the edge itself |

## Reject list

| Method | One-line reason |
|--------|-----------------|
| Pairs trading / cointegration as a signal (Engle-Granger, Johansen) | needs a short leg (illegal for VN retail), loses 38% of its return to one day of execution delay (Gatev et al. 2006: 1.44→0.90%/mo), and 100 symbols = 4,950 pairs of multiple-testing on ~250 obs |
| HMM / Markov-switching regimes | regime **means** are statistically unidentifiable (Ang-Timmermann 2012: μ₀=μ₁ never rejected); what it finds is volatility — tool #2 does that honestly with a real null |
| Short-term (1-week) reversal trading | Lehmann (1990) profits are bid-ask bounce + liquidity provision; T+2 settlement blocks the round trip anyway |
| Skew/kurtosis shape statistics on daily returns | the ±7% band truncates the distribution, so the statistic measures the band, not the market; kurtosis z has no sign (the #31 lesson) |
| Full Kelly sizing | over-betting is strictly dominated — at 2× Kelly growth hits zero (MacLean-Thorp-Ziemba 2010); "Long Term Capital is one of many real world instances" |
| RSI/MACD/Bollinger as **signals** | best rule's edge vanishes out-of-sample after data-snooping adjustment (Sullivan-Timmermann-White 1999); admitted only as vocabulary (tool #13) |
| Naive √252 Sharpe annualization | wrong under serial correlation, overstates up to 65% (Lo 2002) — a contract rule inside tool #8, rejected as a standalone convention |
| GARCH-family conditional vol forecasting | ~250 trailing daily obs per symbol is marginal for stable MLE, band truncation contaminates the tails, and range-based estimators already deliver the efficiency (GK Eff ≈ 7.4 ≫ close-to-close) |
| Anything intraday (VWAP execution, order-flow imbalance, realized variance from 5-min bars) | no intraday data, full stop |
| Full-sample normalisation of any statistic | lookahead bias — the #31 post-mortem showed the same event scoring z=+151.5 vs z=+135.6 depending on run end; trailing windows only, by contract |

---

## 0. The constraint set, verified

Every tool below inherits these facts; they were verified from primary sources
because the issue asked not to trust news articles.

**Price bands** — HOSE **±7%**, HNX **±10%**, UPCOM **±15%**; first trading day
and return-from-25-session-suspension widen to ±20% / ±30% / ±40%. Primary:
HOSE's own "Quy định cần biết khi giao dịch chứng khoán tại HOSE" (Feb 2026,
[staticfile.hsx.vn PDF](https://staticfile.hsx.vn/Uploads/UploadDocuments/2453338/HTGD_Quy%20dinh%20can%20biet%20khi%20GDCK%20tren%20HOSE_T2.2026.pdf)),
citing VNX Decision 22/QĐ-HĐTV (18/04/2025, re-issued 16/03/2026); UPCOM from
Decision 23/QĐ-HĐTV 2025 Art. 18 (full text via legal mirror). HNX ±10%/±30% is
secondary-confirmed (broker restatements of Decision 22 Appendix III, which is
paywalled). Legal basis: Circular 120/2020/TT-BTC Art. 4 as consolidated in
44/VBHN-BTC 2025 — VNX sets bands with SSC approval.

**Settlement** — the cycle is **T+2**, with securities delivered 11:00–11:30 on
T+2 and allocated to client accounts before 13:00, so a buyer can sell in the
**afternoon session of T+2** (the colloquial "T+2.5"). Primary: VSDC's clearing
regulation Decision 39/QĐ-HĐTV (29/04/2025, [vsd.vn](https://vsd.vn/vi/sd/XAz40d2Q-9j569TvBgLQaQ))
and the original mechanics announcement effective 29/08/2022
([vsd.vn/vi/ad/152750](https://vsd.vn/vi/ad/152750)); restated in HOSE's Feb-2026
document ("vào chiều ngày T+2"). Circular 68/2024/TT-BTC (Art. 9a) removed
prefunding for foreign institutions only; domestic investors still prefund.
**Actionability floor: no signal with a horizon under ~3 sessions is executable
round-trip.**

**Sessions** — HOSE: ATO 09:00–09:15, continuous 09:15–11:30, lunch 11:30–13:00,
continuous 13:00–14:30, ATC 14:30–14:45 (primary, same HOSE doc). HNX: no ATO,
ATC 14:30–14:45 plus a PLO session to 15:00 (secondary-confirmed). UPCOM:
**continuous matching only — no ATO, no ATC** (primary, Decision 23 Arts. 11, 14).
Consequence for EOD bars: on HOSE/HNX the close is an auction print; on UPCOM it
is the last continuous trade.

**Reference price** — HOSE/HNX: previous close. **UPCOM: volume-weighted average
of the previous day's round-lot continuous trades** (Decision 23 Art. 19, primary).
Any "distance to band" computation must use the right anchor per exchange.

**Two live hazards** — (1) HNX-listed stocks are migrating to HOSE through
**31/12/2026** (Circular 139/2025/TT-BTC; secondary-confirmed): a symbol's band
regime can change mid-history, so band-aware tools must key the band off the
exchange **as of each bar's date**. (2) Trading regulations were re-issued
March 2026 (Decisions 22/23 QĐ-HĐTV 2026) with no parameter changes detected —
re-check Appendix III when obtainable.

**Data actually held by `apps/api`** — `StockDailyOHLCV` (O/H/L/C in VND, volume;
`apps/api/src/stocks/models.py:8`); foreign buy/sell volume+value, net value, and
foreign room in the snapshot schema (`apps/api/src/stocks/schemas/snapshot.py:48-89`
— adapters built but unwired, per #19); quarterly `net_profit`/`revenue`/`eps`
(`models.py:56`) plus the provider ratio frame (`pe_ratio`, `roe`, …,
`apps/api/src/stocks/financial/ratio_frame.py`). Whether vnstock's daily history
is corporate-action adjusted is **unverified** — an implementation check before
any multi-year return computation, since an unadjusted 2:1 split reads as a −50%
"return" that no band allows.

---

## 1. Volatility estimators from OHLC — accept, Yang-Zhang headline, GK for the anomaly screen

All four primary papers were read in full text. Notation: u = ln(H/O),
d = ln(L/O), c = ln(C/O), o = ln(O₁/C₀).

- **Parkinson (1980)**, J. Business 53(1) 61–65: σ² = (ln(H/L))²/(4 ln 2).
  Assumes driftless GBM, continuous trading. Parkinson's own efficiency claim is
  "2½–5×" vs close-to-close; the 5.2 figure is Garman-Klass's computation, 4.9 is
  Molnár's (2012).
- **Garman-Klass (1980)**, J. Business 53(1) 67–78 (authors' updated text):
  practical estimator **σ² = 0.5(ln(H/L))² − (2 ln 2 − 1)(ln(C/O))²**, Eff ≈ 7.4.
  Zero-drift, no opening jump. Critical trap flagged by Molnár (2012, IRFA 23:20–29):
  the version with ln(Cᵢ/Cᵢ₋₁) in place of ln(C/O) is a **literature error** that
  "sometimes produces negative estimates" — the tool must use C/O.
- **Rogers-Satchell (1991)**, Ann. Appl. Prob. 1(4) 504–512:
  **σ² = ln(H/C)ln(H/O) + ln(L/C)ln(L/O)** — unbiased under **any drift**
  (their eq. (3): the expectation is independent of the drift), at a modest
  variance cost vs GK.
- **Yang-Zhang (2000)**, J. Business 73(3) 477–491:
  **V = V_overnight + k·V_open-to-close + (1−k)·V_RS**, k = 0.34/(1.34 + (n+1)/(n−1)).
  Drift-independent **and** opening-jump-independent (they prove no single-period
  estimator can be both); peak efficiency 14, decaying toward 1 as the overnight
  share of variance grows; typical ≈ 7.3 at n=10 on US equities.

**Which is least damaged by VN microstructure?** Two verified facts drive the
answer. (1) On a limit-lock day H=L=O=C, so u=d=c=0 and every range term is 0 by
construction — Yang-Zhang's Appendix A requires estimators to return 0 on a
constant series. Only YZ's overnight term (o) still carries information across
the lock. (2) Thin/discrete trading biases the observed range **downward**: GK
Section VI Table 1 shows the range estimator's expected value is 0.38–0.55 of
true variance at 5 transactions/day, still 0.89–0.92 at 500; Rogers-Satchell §3
gives the analytic √h correction. UPCOM names live at the bad end of that table.

**Adaptation (tool #1)**: headline number is Yang-Zhang over a **duration-named
trailing window** (`window_days`, per #31's bar-count lesson), with GK, Parkinson,
RS, and close-to-close returned as components; the response carries
`limit_days_in_window` and `zero_range_days_in_window`, and the contract states
the estimate is biased **downward** when those counts are material. Units:
annualized %, √252 scaling on the *variance* (legitimate here — it is variance
aggregation, not Sharpe annualization). No null needed: it estimates a parameter,
it does not claim an event.

**Adaptation (tool #2, the #31 keep)**: GK variance per bar → robust z against
trailing median/MAD (window in days, e.g. 60–120), **limit-lock bars excluded
from the median/MAD baseline** (a run of zeros deflates MAD and manufactures z
elsewhere — the exact failure #31 documented). Sign is interpretable: + = range
volatility elevated vs the symbol's own recent normal. Null calibration per the
#37 bar: simulate GBM paths at matched vol (plus a variant with 7% truncation),
require false-positive rate ≤ 1% at the shipped threshold before the agent may
cite it. No published paper directly analyzes price-limit truncation of range
estimators — the closest is Kim-Rhee (1997, J. Finance 52(2), abstract verified:
price limits on the TSE caused volatility spillover to subsequent days) — so the
truncation adjustment is engineering inference, marked as such, not a cited result.

## 2. Momentum — accept cross-sectional rank and time-series sign, adapted long-only

- **Jegadeesh-Titman (1993)**, J. Finance 48(1) 65–91 (full text): J-month
  formation / K-month holding, all 32 strategies positive; ~1%/month for 6-month
  formation; best 1.49%/month (12/3 with skip-week, t=4.28). The skip exists
  "to avoid some of the bid-ask spread, price pressure, and lagged reaction
  effects" documented in **Jegadeesh (1990)** (monthly reversal, abstract verified)
  and **Lehmann (1990)** (weekly reversal, abstract verified).
- **French data library** (primary for the convention, page read): momentum =
  "prior (2-12) return" — cumulative return t−12..t−2, skipping the most recent
  month.
- **Rouwenhorst (1999)**, J. Finance 54(4) (working-paper full text): momentum
  replicates in 17 of 20 emerging markets, but at 0.39–0.58%/month — noisier than
  the US, and the significance comes from cross-market diversification. Vietnam
  was not in the sample (HOSE opened 2000).
- **Vietnam-specific**: Vo & Truong (2018), J. Behavioral & Experimental Finance
  17:10–15 (abstract verified): 10 of 16 J/K strategies profitable on HOSE
  2007–2015, best 6/9 (the 10-of-16 detail is search-snippet level, **partially
  verified**). Alphonse & Nguyen (2013, Asian J. Finance & Accounting 5(2),
  abstract verified): momentum present only **pre-2008** subsamples — regime-
  dependent. Honest read: VN momentum is plausible but fragile, mid-tier venues,
  crisis-dominated samples.
- **Moskowitz-Ooi-Pedersen (2012)**, JFE 104(2) 228–250 (full text): sign of own
  past 12-month excess return predicts 1–12 months ahead in **all 58 futures
  instruments**; persistence then partial reversal after ~1 year. Caveat carried
  into the tool contract: the sample is liquid futures — application to single VN
  equities is an extrapolation, not a paper result.

**Adaptation**: cross-sectional momentum (tool #3) returns the symbol's
**percentile rank** of prior (2-12) return within the 100-symbol Universe plus
the raw return — long-only actionable as "overweight winners / do not add to
losers / holders of losers reconsider", which is exactly what a rank narrates
without a short leg. Percentile is self-calibrating (uniform under the null);
the raw return gets a stationary-block-bootstrap CI. Band truncation hazard: a
large shock is smeared over consecutive limit days, so ranks computed on windows
shorter than ~1 month are contaminated by in-flight moves — the tool refuses
`window_days < 21`. Time-series momentum (tool #9) is per-symbol sign over 3/6/12
months, sign-test-calibrated, with the futures-extrapolation caveat in the
contract string.

## 3. Mean reversion and pairs — accept a descriptive gauge, reject pairs outright

- **Engle-Granger (1987)**, Econometrica 55(2) 251–276 (abstract verified; scan
  has no text layer): two-step residual-based test. **MacKinnon (1990/2010,
  QED WP 1227, full text)**: the EG/DF statistics "do not follow any standard
  tabulated distribution" — estimated residuals shift the distribution, so plain
  DF critical values are invalid; use MacKinnon's response-surface values.
- **Johansen (1991)**, Econometrica 59(6) 1551–1580 (abstract verified): ML
  rank test in a Gaussian VAR (trace statistic), >2 series at once.
- **Gatev-Goetzmann-Rouwenhorst (2006)**, RFS 19(3) 797–827 (full text): distance
  method earns 1.44%/month top-20 (t=11.56) 1962–2002, **declining to ~38 bp/month
  post-1988**; waiting one day after the 2σ signal cuts it to 0.90%/month —
  ~324 bp per 6 months is bid-ask bounce an EOD trader cannot capture; the
  strategy shorts the winner leg by construction.

**Verdict**: a 100-symbol universe with no shorting and T+2 is **not a viable
habitat for pairs**. The hedge leg is unavailable to VN retail; the EOD
implementation forfeits the microstructure component that is most of the modern
profit; and 4,950 candidate pairs tested on ~250 daily observations is a
data-snooping engine (White 2000 applies). Rejected as a tool family — including
Johansen rank tests, whose output (a trace statistic against nonstandard critical
values) fails LLM-narratability on its own.

**What survives (tool #10)**: single-symbol z vs its own trailing mean with an
AR(1) half-life gate — half-life = −ln 2 / ln φ̂ from Δz on z regression
(exponential-decay arithmetic on the OU/AR(1) model; standard practice per Chan
2013 ch. 2, secondary-verified — there is no originating "half-life paper" and
the doc should not pretend one exists). Contract: descriptive only; z sign = above
(+) / below (−) own trailing mean; half-life in days with a block-bootstrap CI;
the tool **suppresses** the z when the estimated half-life exceeds the window
(no evidence of reversion) and **flags non-actionability** when the half-life is
under 3 days (T+2 settlement floor).

## 4. Regime detection — reject HMM, adapt to volatility terciles

- **Hamilton (1989)**, Econometrica 57(2) 357–384 (abstract verified): the
  Markov-switching framework. Hamilton's own Palgrave entry (full text): "often
  there are relatively few transitions among regimes, making it difficult to
  estimate such parameters accurately."
- **Ang-Timmermann (2012)**, Ann. Rev. Fin. Econ. 4:313–337 (NBER WP full text),
  verbatim: "regimes are mostly identified by volatility. In all cases … we cannot
  reject that the regime-dependent means are equal to each other, μ₀ = μ₁, but
  overwhelmingly reject that σ₀ = σ₁" — and this on **monthly data over multi-decade
  samples**. Tests for the number of regimes have nonstandard distributions
  (unidentified nuisance parameters under the null).

**Verdict**: on ~250 trailing daily observations per symbol, an HMM's regime means
are noise, the regime count is untestable, and the output ("state 2, probability
0.73") invites the agent to narrate a story the data cannot support. Rejected.
What a model *can* find — volatility states — tool #2 already delivers with an
honest null; if a market-level regime label is wanted, a realized-vol tercile
split of the VN-Index (trailing window, thresholds from the symbol's own history)
is the defensible adaptation and needs no new mathematics.

## 5. Foreign-flow signals — accept, as the distinctive dataset, with the predictive claim marked honestly

- **Froot-O'Connell-Seasholes (2001)**, JFE 59(2) 151–193 (abstract verified):
  daily flows into 44 countries — flows are persistent, chase returns, and
  **inflows have statistically significant positive forecasting power for returns
  in emerging markets**; prices lag flows.
- **Richards (2005)**, JFQA 40(1) 1–27 (abstract verified): six Asian EMs —
  foreigners positive-feedback trade; price impact of net purchases is large and
  **largely contemporaneous**; predictive content comes from flow persistence,
  not foresight.
- **Grinblatt-Keloharju (2000)**, JFE 55(1) (abstract verified) and
  **Kamesaka-Nofsinger-Kawakita (2003)**, PBFJ 11(1) (abstract verified):
  foreigners are momentum traders and outperform domestic individuals.
- **Vietnam**: Vo (2017), IRFA 52:88–93 (abstract verified) confirms foreigners
  positive-feedback trade on HOSE 2006–2015, but the abstract stops short of a
  clean "net buying predicts next-period returns" result. **No published paper we
  could verify demonstrates that HOSE foreign net buying forecasts subsequent
  returns — that specific claim is unverified and the tool contract must not
  assert it.** Adjacent findings: Vo (2015, JMFM 30) — higher foreign ownership
  lowers volatility; Batten-Vo (2015, JMFM 32-33) — foreigners are long-horizon
  buy-and-hold in VN; Nguyen et al. (2019, Cogent) — non-linear ownership/return
  relation (lower-tier venue).

**Adaptation (tool #4)**: trailing net foreign buy value normalized by trailing
average daily traded value (both duration-windowed), plus the persistence
run-length in days. Sign: + = net accumulation. Narration ceiling written into
the contract: "foreign investors have been net buyers of X bn VND over N sessions,
equal to Y% of typical daily turnover" — persistence and magnitude, **not**
prediction. Null: block permutation of the daily net-flow series (preserving
autocorrelation) to calibrate what streak length/magnitude is remarkable. VN
hazards: foreign-room ceilings mechanically halt buying at the cap (room fields
are already in the snapshot schema); Circular 68/2024 non-prefunding may shift
foreign order timing post-Nov-2024, so pre/post baselines should not be pooled
silently. Data note: the flow adapters exist in `apps/api` but are unwired (#19)
— this tool has a data-plumbing prerequisite.

## 6. Fundamental factors — accept as cross-sectional percentiles, quarterly horizon

- **Fama-French (1993, 2015)**, JFE 33(1), 116(1): canonical factor definitions.
- **Cakici-Fabozzi-Tan (2013)**, Emerging Markets Review 16:46–65 (full-text
  mirror): value works in **all 18** emerging markets studied, momentum in all but
  Eastern Europe; local factors beat global (segmentation). Vietnam not in sample.
- **Huang-Liu-Shu (2023)**, Pacific-Basin Finance Journal 82:102176 (abstract
  verified — the best venue in the VN factor literature): **size is significant
  in Vietnam** (unusual vs other EMs) and **earnings-to-price beats book-to-market**
  as the value signal; a market+size+E/P model outperforms FF3 locally.
- **Ryan et al. (2021)**, JRFM 14(3):96 (full abstract): FF5 > FF3 in VN; HML not
  redundant; operating profitability the best quality proxy. Lower-tier MDPI venue,
  stated as such. Le (2024, JEECAR 11(1)): value premium on HOSE 2013–2023,
  lower-tier venue.

**Adaptation (tool #12)**: no long-short factor portfolios (no shorting, 100
symbols). Instead: the symbol's percentile within the Universe on **E/P** (VN
evidence prefers it over B/P), **B/P**, **ROE/operating profitability**, and
**market cap**, computed from the quarterly statements + ratio frame already in
`apps/api`. Output: percentiles 0–100 with declared direction (+ = cheaper / more
profitable / smaller), each stamped with the reporting period it derives from —
a Q2 EPS percentile quoted in August must say so. Horizon: quarterly; the
literature's premia are annual-horizon, and the contract says the percentile is
a positioning fact, not a timing signal. Null: cross-sectional rank is
self-calibrating.

## 7. Classic technical indicators — descriptive vocabulary only

- **Brock-Lakonishok-LeBaron (1992)**, J. Finance 47(5) (abstract verified): MA
  and range-break rules beat four null models on DJIA 1897–1986 under bootstrap.
- **Sullivan-Timmermann-White (1999)**, J. Finance 54(5) 1647–1691 (full text):
  across ~8,000 rule parameterizations, BLL's in-sample result survives snooping
  adjustment 1897–1986, but 1987–1996 out-of-sample "there is scant evidence that
  technical trading rules were of any economic value". **White (2000)**,
  Econometrica 68(5) 1097–1126 (full text): the Reality Check itself — the null
  is "the best rule in the searched universe has no superiority", resolved by
  stationary bootstrap; this is also the template for #37's permutation bar.
- RSI (Wilder 1978), MACD (Appel), Bollinger (Bollinger 2001) are practitioner
  **books** — definitions, not results (citation-level). Reachable Bollinger
  tests: Lento et al. (2007, Applied Fin. Econ. Letters, Crossref-verified;
  finding text unverified — cannot beat buy-and-hold after costs); Fang-Jacobsen-Qin
  (2017, JPM 43(4), abstract-level).

**Adaptation (tool #13)**: one indicator tool whose return contract carries the
epistemic label: values in indicator units (RSI 0–100, MACD in VND, %B unitless),
with a fixed contract sentence — "descriptive market vocabulary; no
post-data-snooping evidence of predictive value (Sullivan-Timmermann-White 1999)".
The agent can then answer "what's the RSI?" without either refusing or implying
an edge. VN hazard: on limit-lock runs RSI pins at 100/0 and Bollinger width
collapses (σ→0 makes %B explode) — the tool masks %B when trailing σ is below a
floor.

## 8. Portfolio arithmetic — accept, with the uncertainty carried in the contract

- **Sharpe (1994)** (author's full text): SR = mean/SD of **differential** return
  vs a stated benchmark. **Lo (2002)**, FAJ 58(4) (full text): SE(ŜR) ≈
  √((1+SR²/2)/T) under iid; annualization factor is q/√(q + 2Σ(q−k)ρ_k), which
  "reduces to √q" only under zero autocorrelation; hedge-fund SRs overstated "by
  as much as 65 percent". Tool #8 returns the ratio **with its 95% CI**, computes
  the autocorrelation-corrected annualization, and refuses the √252 shortcut when
  ρ₁ is significant — on a 60-day sample the CI usually straddles zero, and the
  agent must say that.
- **Sortino & van der Meer (1991)**, JPM 17(4) (citation-verified; full text
  paywalled): downside deviation vs MAR. Small-sample instability documented in
  Sortino & Forsey (1996, JPM 22(2), via CFA Institute's Kidd 2012, full text):
  discrete downside deviation "can significantly underestimate downside risk"
  when most returns are positive; the common divide-by-below-MAR-count
  implementation is an error (divide by total N). Tool #8 returns
  `downside_obs_count` and withholds Sortino below a floor (e.g. 10 downside
  observations).
- **Magdon-Ismail et al. (2004)**, J. Applied Probability 41(1) 147–161 (preprint
  full text): E[MDD] for driftless Brownian motion = σ√(πT/2) ≈ 1.2533σ√T;
  logarithmic growth under positive drift. Tool #5 uses this as the narratable
  benchmark: "a −18% max drawdown over 250 sessions at this volatility is close
  to what a driftless random walk would produce (expected −16%)" — drawdown gets
  context instead of drama. VN twist: the ±7% band means a crash is serialized —
  count of consecutive limit-down closes is part of the drawdown story.
- **Ledoit-Wolf (2003 JEF; 2004 JPM; 2004 JMVA)** (all full text): the sample
  covariance of 100 symbols on ~250 observations is exactly their ill-conditioned
  regime; optimization "will latch onto the extremes"; the fix is shrinkage toward
  constant-correlation (JPM 2004) with a data-estimated intensity δ̂ of order 1/T.
  Tool #11: any correlation/beta answer at Universe scale is computed on the
  shrunk matrix and **reports δ̂** — a shrinkage intensity near 1 is itself the
  honest message "the data cannot support this matrix".
- **Kelly (1956)**, BSTJ 35(4) 917–926 (full text): betting to maximize expected
  log growth; ℓ* = edge for even-money bets. The continuous f* = μ/σ² is **not in
  Kelly 1956** — it is from the later capital-growth literature
  (Markowitz-attributed proof in **MacLean-Thorp-Ziemba 2010**, Quant. Finance
  10(7), full text), which also proves betting 2× Kelly drives growth to zero and
  documents that even **full** Kelly turns $1,000 into $18 in 700 favorable bets
  some of the time. Tool #14 therefore: accepts a user-stated edge and variance,
  returns quarter- and half-Kelly with full Kelly only as the never-exceed
  ceiling, runs an input-sensitivity range (±50% on the mean, per Chopra-Ziemba's
  20:2:1 error dominance, cited in MTZ), and never estimates the edge from the
  100-symbol history itself.

## 9. Family coverage — verdict per issue bullet

| Family (issue #39 bullet) | Verdict |
|---|---|
| OHLC volatility estimators | **Accept** — YZ headline, GK components, limit-day counts in the contract (tools #1, #2) |
| Momentum: cross-sectional vs time-series | **Accept both, adapted** — rank (long-only narratable) + per-symbol sign; skip conventions primary-sourced (tools #3, #9) |
| Mean reversion: z-score | **Accept as descriptive gauge** with half-life gate (tool #10) |
| Mean reversion: pairs / cointegration | **Reject** — no short leg, EOD forfeits the profit, 4,950-pair snooping |
| Regime detection: HMM / Markov-switching | **Reject** — means unidentifiable (Ang-Timmermann); **adapt** to vol terciles via tool #2 |
| Foreign-flow signals | **Accept** — persistence + magnitude vs ADTV; VN predictiveness marked unverified (tool #4) |
| Fundamental factors | **Accept as percentiles** — E/P over B/M per VN evidence, quarterly stamped (tool #12) |
| Classic technicals | **Accept as vocabulary only** — contract carries the STW 1999 disclaimer (tool #13) |
| Drawdown | **Accept** with the Brownian E[MDD] benchmark (tool #5) |
| Sharpe/Sortino small-sample | **Accept** with mandatory CI (Lo 2002) and downside-obs floor (tool #8) |
| Correlation at 100 symbols | **Accept** — Ledoit-Wolf shrinkage mandatory, δ̂ reported (tool #11) |
| Kelly sizing | **Accept fractional only** — full Kelly is the documented ceiling, never the answer (tool #14) |
| Liquidity / band mechanics (implied by the microstructure bullet) | **Accept** — Amihud ILLIQ + band-pressure are the VN-native tools (tools #6, #7) |

## 10. Cross-cutting contract rules (feed #37 and #31 directly)

1. **Trailing windows only**, parameters named with units (`window_days`), per the
   #31 post-mortem. Symbols with insufficient history get an explicit
   `insufficient_history` refusal, not a silent shorter window.
2. **Every signal-shaped tool ships with a synthetic-noise null** in the White
   (2000) spirit: simulate matched-vol GBM (with and without ±7% truncation),
   measure the false-positive rate at the shipped threshold, and store that rate
   in the tool's metadata. Descriptive tools (estimators, percentiles, arithmetic)
   are exempt but must carry uncertainty (CI, SE, or δ̂) where a sampling
   distribution exists.
3. **No figure without a sign convention and a unit** in the return schema — the
   kurtosis-z failure mode from #31 is a schema-review checklist item.
4. **Limit-lock days are first-class**: counted, excluded from robust baselines,
   and reported in every window that contains them.
5. **Band regime is dated per bar** (HNX→HOSE migration through 31/12/2026), and
   UPCOM band distance anchors to prior-day VWAP, not prior close.
6. **Settlement floor**: any tool whose natural horizon is under 3 sessions must
   say its signal is not round-trip actionable under T+2.

## Verification ledger (what was actually reached)

Full text read: Parkinson 1980; Garman-Klass 1980 (author version); Rogers-Satchell
1991; Yang-Zhang 2000; Molnár 2012 (published typeset); Jegadeesh-Titman 1993;
French data library UMD page; Moskowitz-Ooi-Pedersen 2012; MacKinnon 1990/2010;
Gatev et al. 2006; Rouwenhorst 1999 (WP); Sharpe 1994; Lo 2002; Magdon-Ismail et
al. 2004 (preprint); Ledoit-Wolf ×3; Kelly 1956; MacLean-Thorp-Ziemba 2010 (draft);
Ang-Timmermann (NBER WP 17182); Hamilton Palgrave entry; Sullivan-Timmermann-White
1999; White 2000; Kidd 2012 (CFA); Amihud 2002 ([PDF](https://www.cis.upenn.edu/~mkearns/finread/amihud.pdf));
HOSE Feb-2026 rules PDF; Decision 23/QĐ-HĐTV 2025 (mirror); VSDC settlement pages;
44/VBHN-BTC 2025; Decree 245/2025 (gov portal).

Abstract-verified: Engle-Granger 1987; Johansen 1991; Jegadeesh 1990; Lehmann
1990; Hamilton 1989; Brock-Lakonishok-LeBaron 1992; Kim-Rhee 1997; Froot et al.
2001; Richards 2005; Grinblatt-Keloharju 2000; Kamesaka et al. 2003; Vo 2015/2017;
Batten-Vo 2015; Huang-Liu-Shu 2023; Vo & Truong 2018; Alphonse & Nguyen 2013.

Secondary-confirmed: HNX ±10%/±30% and PLO session (VNX Decision 22 Appendix III
paywalled; consistent broker restatements); HNX→HOSE migration deadline; Chan 2013
half-life procedure.

Unverified (and marked so wherever used): HOSE foreign net-buy → future returns
for Vietnam specifically; whether vnstock daily history is corporate-action
adjusted; Johansen 1988 content beyond citation; Sortino & van der Meer 1991 /
Sortino & Price 1994 full texts; Wilder/Appel/Bollinger books; Lento et al. 2007
finding text; bond no-band claim; band truncation's effect on range estimators as
a published result (engineering inference only).

# Host-owned numbers — plan

Status: in progress · Branch: `feat/host-owned-numbers` · Precedes `260906-1557-financial-research-agent`
Source: `plans/reports/brainstorm-260926-1427-end-to-end-gap-and-proposal.md`

**Outcome.** Every financial figure in an answer comes from this Turn's tool
data, is placed in time and carries its source date beside it — or is labelled
`chưa kiểm chứng` / `nguồn cũ`. The chart rule (host owns the numbers) extended
to prose, on every lane, with `kiro-glm-5` as the test model.

**Decisions (owner, fixed).** Label, never delete, a figure still unsupported
after one repair · financial statements behind an adapter, vnstock for dev/test
only, no data purchase · keep `kiro-glm-5` · watchlist/alerts (P4) out of scope ·
golden harness removed (2026-09-26), acceptance is live Turns + unit tests.

**Defaults chosen here** (owner left blanks): paid runs budget 0 · stale web
source for financial figures > 120 days, news > 30 days; a price is dated by its
own session instead of being called stale · P1 acceptance N = 5 banks, M = 10 samples.

**Non-goals.** P4; new data contracts or purchases; changing the injection
layer or the chart path (both must keep passing their tests).

| Phase | File | Gate |
|---|---|---|
| P0 fix now | [phase-00](phase-00-host-owned-figures.md) | 4 UI questions re-run on kiro-glm-5: no wrong-year price, no figure absent from tool data unlabelled, every figure dated; ledger row on 100% of Turns; suites green |
| P1 statements + calculator | [phase-01](phase-01-statements-and-calculator.md) | NPL, CAR, ROE, P/B for 5 banks from tools with formula; 10 samples match by hand; P0 re-run holds |
| P2 UI | [phase-02](phase-02-figure-labels-ui.md) | markers render as citations/labels; report-wrong button queues the case; P0 re-run holds |
| P3 events, news, screener | [phase-03](phase-03-events-news-screener.md) | features answer on UI through the same figure check; P0 re-run holds |

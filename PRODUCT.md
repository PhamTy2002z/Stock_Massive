# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary users are self-directed Vietnamese investors researching listed
companies and monitoring the Vietnamese stock market. They use the product to
understand market conditions, investigate securities, and evaluate evidence in
the context of their own investment decisions.

## Product Purpose

VisgniteAI turns Vietnamese market data into decision-grade investment
intelligence. It helps users understand what is happening, why it may be
happening, what evidence supports the conclusion, what could invalidate it, and
what to monitor next. Success means producing useful answers that remain
traceable to their data, timing, assumptions, and uncertainty.

## Positioning

VisgniteAI is an evidence-backed, point-in-time investment research desk rather
than a stock-prediction or trading-tip product. Its distinguishing mechanism is
the connection of sourced observations and deterministic calculations to
explicit claims, confidence, counterarguments, invalidation triggers, and
decision implications.

## Operating Context

The product is a Vietnamese-language, authenticated web application focused on
HOSE, HNX, and UPCOM. Its current single-surface workspace combines AI research
conversations, market-board data, news, watchlists, saved threads, analysis
artifacts, and source inspection without discarding in-progress work when the
user changes views.

## Capabilities and Constraints

- The product provides research and decision support; it does not execute
  trades.
- Personalized action proposals remain unavailable unless a future
  product/legal decision and an explicit human-approval flow authorize them.
- Financial calculations, market rules, time selection, units, rounding, data
  scope, authorization, and side-effect policy are deterministic system
  responsibilities rather than model claims.
- Material figures and conclusions preserve their source, as-of time,
  freshness, units, transformation method, and quality or refusal state.
- The system distinguishes observations, derived metrics, claims, hypotheses,
  scenarios, judgments, and action proposals. It must not present inference as
  observed fact.
- Missing, stale, conflicting, or insufficient evidence must be disclosed. The
  product must not fabricate evidence or silently turn incomplete data into a
  confident conclusion.

## Brand Commitments

- Product name: VisgniteAI.
- Language: Vietnamese-first user experience, with correct Vietnamese text and
  typography support.
- Existing identity assets and the VisgniteAI mark must be preserved unless a
  future rebrand is explicitly approved.
- Voice: direct, evidence-led, transparent about uncertainty, and careful not to
  overstate what the data can support.

## Evidence on Hand

- The binding investment-intelligence contract is documented at
  `docs/Harness/investment-intelligence-contract.md`.
- The capability direction and autonomy boundaries are documented at
  `docs/harness-roadmap.md`; data-platform and product-system delivery are
  tracked separately in `docs/system-roadmap.md`.
- The implemented product surface and Vietnamese copy live under
  `apps/web/src/`.
- Existing identity assets live under `apps/web/public/images/`, with the
  reusable VisgniteAI mark implemented in
  `apps/web/src/components/shared/visgnite-logo.tsx`.
- Current product data and analysis must remain grounded in real providers,
  persisted evidence, and deterministic calculations. Future work must not
  fabricate testimonials, customers, performance claims, benchmarks, or market
  evidence.

## Product Principles

1. Make every consequential conclusion traceable to evidence and time.
2. Separate fact, calculation, hypothesis, scenario, and judgment clearly.
3. Prefer honest refusal or qualified partial answers over unsupported
   certainty.
4. Keep investment research useful without crossing into unauthorized advice
   or execution.
5. Preserve the realities of the Vietnamese market in data, terminology, and
   user experience.

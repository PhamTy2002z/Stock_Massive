/**
 * Generic chart leaves: they take series and draw them, and they fetch nothing.
 *
 * ADR-0012 measured roughly thirty components on this surface and found only
 * `Sparkline` and `StockIndexCard` genuinely generic. Everything else either
 * takes a response type or takes a `symbol` and fetches its own data, which is
 * why a Widget could not be built on one: it would re-query today's numbers
 * inside a historical answer. What lands here is the other half of that split —
 * the drawing, with the flattening left behind in the card.
 */
export { ComparisonBars } from "./comparison-bars"
export type { ComparisonBarsProps, ComparisonRow } from "./comparison-bars"
export { RangeTrack } from "./range-track"
export type { RangeTrackProps } from "./range-track"

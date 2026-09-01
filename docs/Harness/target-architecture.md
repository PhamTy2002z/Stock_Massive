# Target Architecture (Superseded)

This pre-pivot architecture described Signal Desk, local financial engines,
Study lanes and stock-store capabilities that are no longer part of the product
runtime.

Use [`../roadmap.md`](../roadmap.md) as the current architecture and sequencing
authority. Its harness target combines:

- OpenCode's server-core/client-projection boundary, durable typed session state,
  unified capability resolution, permission rules and deterministic context
  pruning;
- Hermes Agent's bounded model-tool loop, one-call-one-result invariant, stable
  parallel-read ordering, typed recovery, output/context budgets and
  content-light observability;
- financial-research extensions for claim-evidence linkage, `as_of`, publication
  lag, source conflict, uncertainty and suitability boundaries.

Historical research in this folder remains useful as evidence, but any owner,
lane or module list that conflicts with the roadmap or current source is not an
implementation contract.

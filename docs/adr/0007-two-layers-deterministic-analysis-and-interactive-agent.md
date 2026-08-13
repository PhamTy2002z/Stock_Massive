# Intelligent Quant is two layers: a deterministic nightly Analysis and an interactive agent above it

**Intelligent Quant** — sidebar label **Alpha Desk** — is built as two layers that
never collapse into one.

1. The nightly **Analysis** is a deterministic pipeline: a fixed evidence
   envelope assembled in code, one strict structured-output generation call, a
   fixed template, one artifact per `(symbol, trading_day)`.
2. The agent is the interactive layer above it. `get_analysis(symbol, date)` is
   one of its twelve tools and carries no privilege the other eleven lack.

They share the `LLMClient` boundary and the computations, **Signal Registry**, unit
contracts, and hazard handling of `src/stocks/signals/`, along with the error taxonomy.
They do not share the *loop*, and they do not share the model-facing tool layer: the
pipeline reads the registry directly, while `src/agent/tools/` exists to project it into
the ≤4KB a model can be handed.

## Why the nightly batch is not an agent loop

Three properties of the daily artifact are lost the moment it is produced by an
agent, and each one is load-bearing rather than nice to have.

- **It must be budgetable.** An agent loop has no fixed token cost by
  construction; the nightly cohort is the distinct union of every Watchlist, so
  an unbounded loop multiplied by N symbols has no worst case to reserve against.
  ADR-0014 requires a worst-case reservation *before* dispatch, which a loop
  whose length the model chooses cannot supply.
- **It must be diffable day over day.** The product's value is that today's
  Analysis can be read against yesterday's. Free-form output of varying shape
  cannot be diffed; a fixed template with extracted fields can.
- **It must be evaluable.** Without a template there is nothing for a machine to
  assert on. The fixed section set, the exactly-one-`lead` rule, and
  `citedFieldIds ⊆ AnalysisFieldProfile` are the assertions ADR-0016's battery
  runs against the Analysis lane.

The inverse also holds, and is why the agent is not simply a second template. A
question worth asking is not known in advance, so the interactive layer needs the
tool-choosing freedom the batch must refuse.

## What the split does not license

The batch is not exempt from the bar because it is deterministic. It narrates the
same figures into the artifact users read *every day*, so if the statistical
contract covered only the agent surface, the more-read artifact would be the
unguarded one. The nightly template therefore cites **registered fields only**,
through the same registry (ADR-0010), and its prose is scored by the same Eval
Battery as an agent Turn (ADR-0016).

Nor is the agent allowed to manufacture the artifact. Only a Watchlist addition
creates an on-demand Analysis; asking the agent about another Universe symbol
uses store-only tools and produces no artifact. Otherwise the deterministic lane
would acquire an undeclared second entrance.

## Considered Options

- **One agent loop serving both surfaces.** Rejected for all three reasons
  above. It is also the shape that reads as obviously simpler and is not: the
  nightly lane would still need a template to be diffable, and a loop that must
  land on a fixed template is a loop fighting its own affordance.
- **Two entirely separate stacks — separate client, separate computations.**
  Rejected. It forks the error taxonomy, the unit and sign contracts, and the
  hazard handling of `prepare_bars()` into two copies that drift. Sharing at the
  client and tool layer shares exactly the things that must not diverge.
- **A deterministic pipeline only, with no agent.** This is the existing product
  (a dashboard with prose). It cannot answer a question, which is the whole
  destination.

## Consequences

- Two budget lanes, not one pool: ADR-0014 reserves Analysis and Turn spend
  separately and does not lend the Analysis reservation to interactive use before
  the month's last Trading Day has completed.
- Two evaluation lanes over one fixture, sharing categories D and E, with the
  Analysis lane carrying three checks only it has.
- `src/stocks/signals/` decides *what is true* and is not agent-specific;
  `src/agent/tools/` decides *what the model may see*. The registry lives at
  domain level for this reason.
- The nightly lane may ship before the agent lane, and does not depend on it. The
  reverse is not true: `get_analysis` returns nothing until the pipeline runs.
- A future personalised Analysis would breach this ADR and the
  `(symbol, trading_day)` key of **Analysis** at once — the shared key is what
  makes the deterministic lane's workload the *distinct* union of Watchlists. It
  is a re-decision of both, not a feature.

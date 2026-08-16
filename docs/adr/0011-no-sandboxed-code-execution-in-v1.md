# Sandboxed code execution is out of v1, and the reopening triggers are named

**Status: superseded by ADR-0019.** The demand and security analysis below is
retained as historical context; the implementation decision now lives in
`0019-networkless-container-executor-for-derived-evidence.md`.

The agent may not author or run code. There is no `run_python` tool, no executor
service, and no stub. One seam is kept because it already exists for another
reason, and two triggers would reopen the question.

## Why out

The case *for* it, stated fairly: without execution, "beta of FPT against
VN-Index over six months" is a refusal even though the data is present and the
computation is three lines of NumPy. That is a real loss, and it lands on the worst
kind of question — a reasonable one the system declines.

Four reasons it still goes out.

1. **"Understands quant" does not hang on execution; it hangs on the catalog, and
   the catalog exists.** ADR-0009 packs all fourteen ranked methods into five
   clusters with declared units, signs, and null calibration.
2. **The gap a sandbox fills is mostly the methods that were already rejected** —
   pairs and cointegration, HMM regimes, full Kelly, technicals-as-signals, shape
   statistics on band-truncated returns — and they were rejected *because they do
   not survive daily EOD Vietnamese equities*, not for lack of somewhere to run.
   Letting the model author code does not make them more correct; it makes them
   easier to produce.
3. **Dev cannot run the configuration the research recommends.** In-process
   restriction is not a security boundary — the `__builtins__={}` escape was
   reproduced in eight lines, and CPython retired `rexec`/`Bastion` while PEP 578
   and RestrictedPython both disown sandbox status. The real floor is OS-level: a
   per-call hardened container under gVisor `runsc`, launched by a separate minimal
   executor service and never by handing `api` the docker socket. Development runs
   on macOS, where Docker Desktop is a LinuxKit VM and `runsc` is unavailable. "In"
   would therefore mean a weaker boundary in dev than in production — a sandbox
   never exercised in its production form is a sandbox that has not been tested.
4. **It is the heaviest infrastructure item in the effort and the only piece that
   can be cut with the rest still standing.** The bill is a fifth compose service,
   an internal RPC channel, CPU/memory/wall-clock ceilings, a no-network data-in
   path, and a plot-out path — for a class of question whose frequency has never
   been measured.

## The one seam kept

**`data_ref` stays exactly as ADR-0009 defines it.** It is already the mechanism
for handing data in without a network call, which is the hardest part of any
sandbox design, and it exists for the visualization layer regardless. That is the
whole of the preparation: no stub, no executor, no dead code to maintain.

## What a refusal says

The refusal **lists what is available** rather than only saying no — *"I can't
compute beta; for FPT I have realized volatility (Yang-Zhang), the
volatility-regime z-score, the cross-sectional momentum rank, foreign-flow pressure, and drawdown
against its benchmark"* — plus the nearest answerable question. An empty refusal
throws away the one thing that would make the Turn useful.

**Scope is published, the catalog is not.** The empty state states the boundary in
user language — *four-axis analysis for Watchlist symbols; no ad-hoc computation* —
and the refusal teaches the detail at the moment it matters. Listing fourteen
formulas up front makes people read documentation before asking a question; giving
no signal that a boundary exists makes the system look broken rather than scoped.

## How demand is measured

Through a signal that is already free. When the model wants a computation that does
not exist it frequently **calls a tool that does not exist**, and the harness
records that as `status = 'unknown_tool'` in `agent_tool_call`. No new mechanism,
no thirteenth tool, and it states precisely what the model wanted to compute.

There is deliberately **no automatic counter for prose refusals**: it would require
the model to emit a structured marker, and a brittle mechanism producing wrong
numbers is worse than none. The remainder is the operator reading transcripts,
which is feasible at the current user count.

## No compensating tools

The five clusters stand as they are. Anything new clears ADR-0010's bar first —
adding beta or correlation now would ship a field that has not been calibrated,
which is the exact failure that disqualified the assessed external library. If beta
is genuinely needed it arrives as a sixth cluster through the registry, not as a
shortcut through this decision.

## Considered Options

- **In, with in-process restriction (`RestrictedPython`, `__builtins__={}`).**
  Rejected: not a security boundary, per the reproduction above.
- **In, with per-call hardened containers under gVisor.** The correct shape for a
  self-hosted Linux deployment, and the reason "in" is not absurd. Rejected for
  reasons 3 and 4.
- **In, on a managed Firecracker microVM (e2b, Modal) at roughly $0.06–0.14 per
  1000 short executions.** Rejected now, and named below as the route if the second
  trigger fires: what the money buys is vendor-owned escape response, which is
  exactly the duty we do not want to hold.

## Triggers that would reopen this

1. **Repeated demand for the same class of computation**: the same class appearing
   ≥10 times in 30 days in `agent_tool_call WHERE status = 'unknown_tool'`. The
   threshold is low because the user base is small, and the condition is *same
   class* — ten different questions is curiosity, ten instances of one computation
   is a missing tool. **Even then the first exit is a new tool through ADR-0010,
   not a sandbox.** Execution enters only when this trigger fires *and* the
   requested computations fail to cluster into anything a catalog could cover.
2. **Opening the system to users outside the internal group**, at which point the
   route is managed Firecracker rather than self-hosted gVisor.

## Explicitly not a trigger

**Production being able to run `runsc`.** Production is self-hosted compose, so the
technical precondition is satisfied more or less the moment it deploys. A trigger
that fires because the infrastructure became eligible — rather than because someone
needed the capability — builds something nobody uses. *"Can run" is not "should
run."*

## Consequences

- No new domain vocabulary. This is an in/out decision, and adding a term for its
  own sake dilutes the glossary.
- `docker-compose.yml` keeps its four services, no docker socket mount, and nothing
  privileged.
- `matplotlib` and `scipy` remain undeclared transitive dependencies of
  `vnstock`/`fiinquantx`. Nothing in v1 may rely on them; a chart is a **Widget**
  under ADR-0012, not a rendered image.

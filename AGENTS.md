# Stock_Massive Agent Context

This repository keeps one agent contract, and it lives in
[`CLAUDE.md`](CLAUDE.md). Read that file first and follow it — product
direction, the current capability boundary, retired paths, decision rules and
the verification commands are all stated there, and stating them twice is how
the two copies start to disagree.

This file exists because several coding agents look for `AGENTS.md` by name.
It is a pointer, not a second authority.

## The short version

- Product scope, decisions and **sequential phase order**:
  [`docs/roadmap.md`](docs/roadmap.md). Do not start later-phase work early.
- The product is the Evidence Desk: an agent harness for financial research —
  tool calling, durable Turn state, context, permissions, guardrails,
  evidence/claim ledgers, memory and eval — not a market-data terminal and not
  a local analysis engine.
- The runtime tool catalog is exactly `web_search`, `fetch_url`,
  `session_search`, `remember_fact` and `recall_facts` until a roadmap phase
  gate opens more.
- Signal Desk, analysis boards, the Study/Board DSL, widget catalogs, local
  indicator and calculation tools, stock-store reads, their schedulers and
  global watchlists are retired. Do not reintroduce them.
- No market-data provider SDK is part of this project. An agent that arrives
  here to install one has misread the repository.
- Challenge a roadmap decision only with new evidence, via a deviation report
  in `plans/reports/` — never by silently reversing it (see CLAUDE.md).
- `pnpm` for `apps/web`; the project Python environment for `apps/api`.

Anything this summary does not cover is settled by `CLAUDE.md`.

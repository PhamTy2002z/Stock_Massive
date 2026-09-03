# Phase 6 — Evidence engine: research 3-pass + finance evidence

Status: **Ready — implementation authorized by the Phase 6 request**  
Branch: `feat/phase-06-evidence-engine`  
Opened: 2026-09-02  
Base: `a10f470` (`docs(roadmap): close phase 5 security gate`)  
Authority: [`docs/roadmap.md`](../../docs/roadmap.md), Phase 6, §2, §6 and §9

## Brainstorm contract

### Outcome

The deep lane produces a financial-research memo through three real passes —
research, counterevidence and clean-context verification — and mechanically
prevents an unsupported number or URL from being rendered as verified. Claims
retain exact source spans, source identity and temporal metadata; conflicts,
missing evidence and refusals are first-class outcomes.

### Constraints

- Keep the runtime catalog exactly `web_search`, `fetch_url`, `session_search`,
  `remember_fact`, `recall_facts`. All external reads continue through the
  unified capability/permission/budget/lifecycle path.
- Deep research remains one durable Turn and one agent loop. No subagent,
  child session, MCP, local market-data SDK, indicator/store/Study path, host
  shell or compute capability is added.
- Preserve one-call-one-result, stable result order, cancellation, terminal
  ownership, SSRF/DNS/redirect/size/time protections and the Phase 5 content
  escalation boundary.
- Research, counterevidence and verifier calls spend the same Turn owner,
  deadline, model-call, external-call, input/output and monetary envelope.
- Verifier context is clean: only the question, typed draft claims and bounded
  evidence excerpts enter it; research conversation, history and instructions
  from web content do not.
- Product evidence cache stores only public web content. Thread messages,
  elicitation choices, drafts, verifier material and trajectories stay private
  and tenant scoped.
- No Phase 7 memo UI, evidence Inspector, claim-level flag UI, dossier/watch
  interaction or markdown parsing is implemented here.
- No legal-boundary reversal. Existing ban on personalised buy/sell and
  position-sizing advice remains; generic research with printed assumptions is
  allowed. A formal copy/disclaimer decision remains owned by Phase 7.
- This run uses no subagent. Review, testing and plan sync-back are performed
  directly in the controller session.

### Non-goals

- No new market-data provider, local quote store or derived indicator engine.
- No provider-specific citation dependency. Anthropic Citations may be probed
  as an optional route capability but cannot be required by the product path.
- No Phase 9 production dashboard, human sampling queue or prompt release
  framework; Phase 6 emits the typed facts Phase 9 will aggregate.
- No Phase 10 request queue or cross-user memo sharing. Only public evidence
  documents may be shared; a memo is never a product-cache value.
- No retention deletion job for historical retired schemas. This phase owns
  only new evidence-cache and trajectory records.

### Observable acceptance criteria

1. A deep Turn emits real progress for `research`, `counterevidence` and
   `verification`; light Turns preserve their current behavior byte-for-byte
   outside the additive internal metadata.
2. Research creates independent query facets covering price/movement, event,
   company/industry and counter-thesis when relevant, executes independent
   reads through the existing executor and keeps source URL/title/publisher,
   publication/retrieval time and exact excerpt.
3. Counterevidence receives the research draft and deliberately searches for
   disconfirming evidence. A completed deep memo contains an explicit
   invalidation section or a stated evidence gap.
4. Verification is a separate strict structured-output call with no tools and
   a clean context. Provider/schema/parse failure never marks a claim verified:
   the Turn still settles with a transparent unverified/insufficient-evidence
   answer.
5. A deterministic claim-ledger validator rejects unknown evidence IDs,
   mismatched quoted spans, material numbers absent from cited excerpts,
   temporal violations and unlabelled single-aggregator support. Conflicting
   support is disclosed, never silently ranked away.
6. The final renderer receives only the validated ledger. Every rendered URL
   is taken from a ledger evidence record; every rendered material fact is
   `verified`, `single_source` or `conflicting`; unsupported claims are dropped
   or rendered only as explicitly unverified.
7. Source policy is typed and independent of search relevance. It classifies
   regulator/exchange/VSDC/issuer/primary document above media, aggregator and
   snippet; each class carries ToS risk, freshness, retention and multi-source
   eligibility.
8. Publication time is extracted from search metadata, HTML metadata/JSON-LD,
   visible publisher date and bounded URL patterns with provenance and
   confidence. Unknown remains unknown; it is never replaced with retrieval
   time. Evidence published after the Turn's `as_of` cannot support a claim.
9. Product cache keys immutable public content by canonical URL + content hash
   + temporal window. Private trajectory artifacts are owner-scoped, expire
   separately and never become cache input. Claim ledgers outlive trajectory
   expiry and retain the exact excerpts needed to audit the rendered memo.
10. Elicitation is available only after a preliminary web scout and only for a
    non-discoverable decision-changing unknown. Backend permits at most one
    pre-memo question card in this version (therefore within the roadmap cap of
    three questions), with 2–4 single-select options and the mandatory skip
    option; skip proceeds with an explicit default assumption.
11. Missing/contradictory evidence, suitability refusal, deadline, verifier
    failure and cancellation all settle a typed Turn with no orphan tool/pass
    state and no blank answer.
12. The Phase 1 release corpus has frozen primary-source ground truth for all
    material-claim cases, non-empty publication-time coverage for temporal
    cases and locked post-Phase-6 soft thresholds derived from a multi-trial
    run. The paid release run passes every hard dimension at 100%, meets the
    locked rubric threshold and records material-claim accuracy over multiple
    trials.
13. Focused Phase 6 tests, full API suite, compileall, web lint/type/test/build,
    Alembic upgrade/downgrade smoke, `git diff --check` and the retired-path
    scan pass. Production imports no local signal engine.

## Scout evidence

### Project and current owners

- Python 3.12/FastAPI/SQLAlchemy backend under `apps/api`; Next.js/TypeScript
  client is a projection and is not a Phase 6 implementation owner.
- `src/agent/loop.py` is the single Turn/model/tool loop. `LaneProfile` already
  gives deep Turns 10 tool rounds, 20 external calls and 1,800 seconds, but the
  path currently stops at the first prose completion and performs no pass.
- `src/agent/executor.py` and the frozen surface from `registry.py` remain the
  only dispatch path. The five-tool catalog is verified by current tests.
- `src/agent/parts.py`/`events.py` already persist and replay typed progress;
  adding pass progress changes the closed `ProgressKind` vocabulary, not the
  SSE envelope or event type.
- `src/agent/evidence/contracts.py`, `validation.py`, `documents.py` and
  `numbers.py` provide stable evidence IDs, answer-span links, exact document
  locators and conservative Vietnamese/English number matching. They are not
  wired into production Turns today.
- `src/agent/tools/web.py` keeps source URL/title/snippet/retrieval time and
  already selects verbatim page passages, but fetched pages do not carry
  publication time or source class. Baseline measured `published_at` on 0/981
  source observations.
- `src/agent/turns.py` owns the two terminal gates and has the production-ready
  question settlement contract. `settle_with_question` currently has no
  production caller.
- `src/agent/persistence.py` and `src/alpha/models.py` own durable Turn/message/
  trace state. There is no current evidence-cache, claim-ledger or private
  trajectory table. The old `agent_artifact` migration describes retired Study
  state and is not a reusable authority.
- `apps/api/golden` is the only evaluation path. Four material-claim cases still
  have `pending_record_run`; temporal cases are BLIND; `thresholds.json` records
  the Phase 1 distribution but intentionally locks no soft bar yet.

### Verified Phase 5 hand-off

Directly verified on `a10f470` before opening the branch:

```text
189 passed
```

The focused run covered evidence contracts/numbers/documents, lanes,
fault-injection, Phase 5 adversarial security and golden gate/graders. The
branch is clean and starts from the Phase 5 closing commit. The P5 report also
records 1401 API tests, 458 web tests and green lint/type/build.

### Pattern research required by roadmap §7

- [STORM](https://github.com/stanford-oval/storm) separates pre-writing research
  from writing and uses perspective-guided questions to improve breadth. Adopt
  a small fixed financial facet vocabulary; do not adopt multi-agent simulated
  conversations.
- [GPT Researcher](https://github.com/assafelovic/gpt-researcher) separates a
  planner from parallel retrieval and keeps a summary per URL. Adopt the plan →
  bounded fan-out → source-tracked excerpt shape; retain the repository's one
  executor and one agent loop.
- [SAFE / LongFact](https://deepmind.google/research/publications/85420/) breaks
  long responses into atomic facts, searches/evaluates each fact and reports
  claim-level support. Adopt atomic verification and multiple-trial evaluation;
  do not treat model judgement as the mechanical evidence-span gate.
- [FacTool](https://github.com/GAIR-NLP/factool) and
  [RARR](https://github.com/anthonywchen/RARR) use claim extraction → retrieval
  → verdict/revision. Adopt explicit `supported|conflicting|unsupported`
  outcomes and revision/drop policy; never hallucinate evidence.
- [Hugging Face Open Deep Research](https://huggingface.co/blog/open-deep-research)
  demonstrates that browse depth and multi-step execution must be measured, not
  assumed. GAIA results are context, not a threshold for this finance corpus;
  host code execution is explicitly rejected for Phase 6.
- [Anthropic Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
  guarantees pointers into supplied documents, but the current deployment uses
  an OpenAI-compatible gateway, and Anthropic documents that citations cannot
  be combined with strict structured outputs. Treat it as named assumption A6;
  the product contract stays provider-neutral and ledger-backed.

## Design

### 1. One deep-loop state machine

Keep `AgentLoop` as the sole owner of cancellation, budget and tools. A small
`evidence/pipeline.py` owns typed stage values and prompts; the loop carries the
stage while sharing its existing `_TurnState.external_calls`, call owner,
deadline, tool-round count, executor and checkpoint.

```text
deep Turn
  research: plan facets → search/fetch → draft claims or question
      ↓
  counterevidence: attack draft → search/fetch → invalidators/conflicts
      ↓
  verification: fresh messages, no tools → strict ledger candidate
      ↓
  deterministic validation + ledger-only renderer → terminal Turn
```

Stage transitions consume model-call capacity inside the existing deep
envelope; they do not reset round or external-call counters. Light lane follows
the current loop branch unchanged. The research and counter drafts are internal
trajectory data, not streamed answer deltas. Real tool narration remains a
thought, and each actual transition emits one `pipeline_pass` progress part.

If the deep envelope leaves no model-call slot for verification, the answer is
`incomplete` with a concrete `verification_budget_exhausted` reason; it is not
rendered as verified. Verification errors fail closed for the verified label and
fail open for answering with an explicit unverified state.

### 2. Typed plan, evidence and ledger

Extend the existing evidence contracts instead of creating a parallel type
family:

- `EvidenceRef`: canonical URL, publisher, publication/retrieval/effective
  time, extraction method/confidence, source tier and ToS risk.
- `DraftClaim`: atomic claim, type (`fact|inference|scenario`), material flag,
  units/currency and candidate evidence IDs.
- `VerifiedClaim`: verdict
  (`verified|single_source|conflicting|unsupported|temporally_invalid`), exact
  supporting and contradicting evidence IDs, and invalidation text.
- `ClaimLedger`: version, `as_of`, evidence tuple, verified claims, gaps,
  assumptions and verifier outcome.

The strict verifier returns a candidate ledger, never final prose. Code checks
IDs, exact excerpts, material numbers, source independence, primary-source
exception and temporal admissibility. The renderer builds prose and citations
only from the checked object; URLs cannot enter through model prose.

### 3. Source and temporal policy

Search relevance stays a retrieval signal. A new pure `source_policy.py`
classifies the final canonical domain and document cues:

| Tier | Examples | Material claim rule | ToS risk |
|---|---|---|---|
| primary | SSC, HOSE/HNX, VSDC, SBV, issuer IR/CBTT | one source may verify | low |
| professional media | named newsroom/research publisher | two independent publishers | medium |
| aggregator | portals/quote aggregators | two independent sources and explicit `single_source` until met | medium/high by rule |
| snippet | search result not fetched | discovery only; cannot verify a material claim | inherited |
| unknown | unmapped publisher | never silently primary; two-source rule | high/unknown |

Dates are extracted in priority order: provider field → HTTP/HTML structured
metadata → visible publisher date near article heading → conservative
publisher/URL pattern. Every extracted date carries method and confidence.
Retrieval time is never substituted for publication time. `as_of` is normalized
to Asia/Ho_Chi_Minh and a source after the cutoff is inadmissible. Trading-day,
report-period, unit/currency and corporate-action helpers live beside the
existing VN trading calendar and remain deterministic.

### 4. Locked cache and retention policy

This phase locks roadmap §13.2 as a typed, test-visible policy. Values are
two-way operational defaults and can change only with measured cache behavior;
changing them never changes whether a claim is true.

| Public evidence type | Freshness/as-of bucket | Retention |
|---|---:|---:|
| dynamic market/EOD page | one ICT trading date; historical use requires an explicit effective/session date | 7 days |
| news/media article | publication date; unknown date is current-only and never valid for a pinned historical `as_of` | 30 days |
| issuer IR/CBTT, exchange/regulator/VSDC filing | publication/effective date; immutable content hash | 730 days |
| aggregator page | six-hour freshness bucket | 7 days |
| search snippet | 30-minute discovery cache only; not claim evidence | no durable evidence row |
| private trajectory artifact | Turn-scoped, owner-read only | 30 days |
| durable claim ledger | tied to the assistant message/Thread lifecycle | deleted only with its Thread |

`agent_evidence_cache` contains public web content only and is shareable across
users. Identity is `(canonical_url, content_sha256, as_of_bucket)`, with
`expires_at` and policy version. `agent_evidence_trajectory` is tied to a Turn,
contains bounded drafts/pass evidence, has `expires_at`, and is read only
through an owner-scoped join. `agent_claim_ledger` is written in the terminal
transaction beside the assistant message and carries the exact excerpts needed
after trajectory expiry.

No automatic deletion runs inside a Turn. A bounded cleanup function and
operator command delete only rows whose own `expires_at` is past; rollback does
not require retaining expired trajectory data.

### 5. Elicitation and refusal

The research-stage schema may end with `draft` or `question`. A question is
accepted only if at least one preliminary external scout completed, it names a
non-discoverable unknown and each option changes the next research branch.
Backend construction enforces one card, 2–4 options, single-select and the
mandatory skip/default option. The question travels through the existing
terminal transaction and replay path; there is no suspended Turn.

If the model proposes an invalid/over-budget question, the pipeline continues
with the documented default assumption and records why it did not ask. Advice,
position sizing or direct buy/sell requests settle as explicit refusal/research
boundary text; an ordinary under-specified research request proceeds with
printed assumptions.

### 6. Golden graduation

Curate the four `material_claim_accuracy` values from primary records already
captured or newly frozen into the tape, with source URL/publication date and
tolerance. Extend the artifact with the runtime ledger/verifier fields actually
emitted; graders never infer a contract from markdown.

Run a post-implementation multi-trial release baseline with a user-supplied
monetary ceiling. Lock:

- every hard dimension at 100% (unchanged fixed gate);
- `judge_axes` threshold at the lower bound justified by Phase 1 and Phase 6
  multi-trial distributions, never below the Phase 1 mean without a deviation;
- reported source/read metrics only after inspecting their Wilson intervals;
- material-claim accuracy as a measured result, not an asserted target.

If the paid run is not authorized or cannot reach the configured provider, the
phase remains Target. Unit/replay/grade-only success is not evidence for the
quality gate.

## Implementation slices

1. Add source/temporal policies, publication-date extraction and conservative
   canonicalization; extend `fetch_url` result metadata without weakening web
   security.
2. Add evidence cache, private trajectory and durable claim-ledger models,
   Alembic migration, owner-scoped persistence and expiry cleanup.
3. Extend evidence contracts/validation and implement the ledger-only renderer.
4. Add deep pipeline state/prompts, shared-envelope pass transitions, clean
   verifier and real progress; preserve the light path.
5. Wire valid research-stage elicitation to the existing question terminal and
   enforce skip/default/refusal behavior.
6. Curate golden ground truth, expose emitted ledger fields to artifacts, update
   graders/gate/threshold locking and run deterministic gates.
7. Run paid multi-trial golden release, fix cause-aligned failures, self-review
   every touchpoint/public contract, write the phase report and close roadmap
   Phase 6 only when all gates are proved.

## Preflight §9

### 1. Runnable gates and numeric thresholds

```bash
cd apps/api && pytest tests/test_agent_evidence_source_policy.py \
  tests/test_agent_evidence_store.py tests/test_agent_evidence_pipeline.py \
  tests/test_agent_evidence_renderer.py tests/test_agent_evidence_elicitation.py -q

cd apps/api && pytest tests/test_agent_loop.py \
  tests/test_agent_fault_injection.py tests/test_agent_context_engine.py \
  tests/test_agent_capability_contract.py tests/test_agent_security_adversarial.py \
  tests/test_agent_web_tools.py tests/test_agent_persistence_paths.py -q

cd apps/api && pytest -q
cd apps/api && alembic upgrade head
cd apps/api && alembic downgrade -1 && alembic upgrade head
python3 -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test
pnpm --dir apps/web build
make golden-release CEILING_USD=<approved-ceiling> TRIALS=3
git diff --check
rg -n 'src\.(stocks|studies)|Signal Desk|analysis board|execute_code' \
  apps/api/src apps/web/src \
  -g '*.py' -g '*.ts' -g '*.tsx'
```

Phase thresholds: hard dimensions `100%`; discoverable elicitation questions
`0`; non-branching questions `0`; unknown evidence IDs `0`; verified material
numbers absent from cited spans `0`; rendered URLs outside ledger `0`; orphan
pass/tool state `0`; local signal-engine imports `0`.

### 2. Previous-phase hand-off

Verified in code and tests, not trusted from the Done label: unified frozen
surface, typed permission/resource policy, schema validation, stable executor,
deep/light lanes, progress replay, question lifecycle, context engine, untrusted
content boundary, SSRF and terminal gates are present. Focused preflight is
`189 passed`; starting Git SHA and Phase 5 full-gate evidence are recorded
above.

### 3. Named assumptions and fallback

| Assumption | Fallback if false |
|---|---|
| A1. Strict JSON schema remains available on the configured session route, as the capability probe currently tests. | Verification fails closed to an unverified answer and the phase gate stays red; do not parse free-form verifier prose. |
| A2. Deep pipeline transitions fit inside the existing 11-call/20-external-call/1,800-second envelope. | Measure actual call/round use. Rebalance research vs counter slots within the same cap; widening the monetary or hard maximum requires an explicit plan amendment. |
| A3. Publication time can be recovered for enough pinned-as-of corpus sources from structured/visible metadata or conservative patterns. | Keep unknown as unknown, report temporal coverage numerically and write a deviation report if the hard gate remains BLIND; never substitute retrieval time. |
| A4. Public fetched text is safe to share when canonical URL, policy and content prove it contains no user/thread material. | Reject the row from product cache and keep it only in the owner-scoped trajectory/ledger; fail closed on classification ambiguity. |
| A5. One pre-memo single-select question card covers the first elicitation release while staying within the roadmap maximum of three questions. | If corpus cases require multiple independent decisions, stop and propose an additive typed-card contract for approval; do not concatenate hidden questions into prose. |
| A6. Anthropic citation blocks are unavailable or incompatible on the OpenAI-compatible route. | Use the provider-neutral strict verifier + deterministic ledger renderer. If a future probe proves native spans, treat them as an extra evidence-locator input, never the sole truth gate. |
| A7. The paid golden run receives an explicit monetary ceiling and a reachable provider/database. | Complete all free gates and leave Phase 6 open with the exact missing command/ceiling; never call grade-only or unit tests the quality gate. |

### 4. Rollback

- Code and prompt changes revert as one branch; light lane remains the baseline
  and no new capability needs disabling.
- The additive migration downgrade drops only the three new Phase 6 tables.
  It does not touch messages, Turns, tool traces, memory or retired historical
  schemas.
- Before downgrade, durable claim-ledger JSON may be exported by Turn ID. A
  rollback build continues rendering the already stored assistant prose; it
  simply does not expose or create new ledgers.
- New cache/trajectory rows have no effect on old code and may be left to
  expire if rollback happens without a database downgrade.
- Prompt version and evidence-policy version are bumped together; rollback
  restores the previous cache identity and cannot mislabel a new-policy row as
  an old-policy result.

## One-way-door audit

- Public HTTP/SSE envelope and endpoints: unchanged. Existing message content
  remains open JSON; Phase 6 ledger stays internal until Phase 7 explicitly
  projects it. `part.progress` gains closed pass kinds required by the roadmap,
  with no new event type.
- Database: additive tables only; no data drop and no mutation of historical
  messages/traces.
- Default permissions and five-tool catalog: unchanged.
- Research/advice boundary: preserved and made stricter; no new disclaimer or
  legal interpretation is introduced.
- Truth contract: implemented as written, not weakened. Any evidence that the
  hard gate is unattainable triggers a deviation report rather than a silent
  threshold change.

## Execution record

Written as the slices closed, with the numbers each one was checked by.

### Slices 1–4 — policy, store, ledger, pipeline

Source and temporal policy, the three-table store with its additive migration,
the ledger-only renderer and the deep three-pass loop are implemented and
covered by `tests/test_agent_evidence_source_policy.py`,
`…_store.py`, `…_pipeline.py`, `…_renderer.py` and `…_contract.py` — **45
passed**. The deep Turn runs planning → research → counterevidence →
verification inside one loop, one owner and one envelope; the verifier is a
tool-free strict-schema call and every fail path settles a typed Turn with an
unverified ledger rather than a verified-looking one.

### Slice 5 — elicitation

The research pass may now end the Turn on a question card. What a backend can
enforce is enforced in one place (`evidence/pipeline.elicitation_part`) and
nothing else may ask: a completed web read must already exist (scout-then-ask),
the thread must not have asked before (one round before a memo, read off the new
`TranscriptTurn.asked`), the prompt must be non-empty, every option must carry an
impact, and the count must be 2–4 with a stated default assumption. A proposal
that fails any of these is **not an error**: it becomes a printed assumption on
the draft and the Turn goes on to its memo.

Two duplications were removed rather than added to. `settle_with_question` no
longer writes a question terminal of its own — it builds an outcome and goes
through `_finish`, so there is exactly one place that orders the three writes.
And the draft parser no longer truncates an over-long option list: truncating
would have handed the gate a legal card the model never proposed, so the gate
refuses it instead (`test_an_oversized_proposal_survives_parsing_so_the_gate_can_refuse_it`).

`tests/test_agent_evidence_elicitation.py` — **14 passed**.

### Slice 6 — golden graduation

**Publication time exists now, and the BLIND dimension is gone.** Phase 1
measured `published_at` on 0/981 sources. The Phase 6 extractor was run against
the 173 distinct pages the three `as_of` cases actually cited: **112 dated, every
one of them high confidence, 98 from HTML metadata and 14 from JSON-LD**; the
remaining 61 are 48 pages carrying no date at all and 13 that no longer answer
(403/401/404/connect). A publication date is a property of the article and not of
the fetch, which is what makes this curation honest after the fact.

An earlier attempt to curate the same dates off the recorded tape returned
**0/47** and is worth writing down, because the reason is a design decision
holding: the tape stores extracted page text, Vietnamese publishers put the date
in metadata, and the visible-text pattern is anchored to an explicit label. The
strings it refuses are real — VnExpress's site-wide "Thứ ba, 1/9/2026" header and
Vietnamnet's press-licence "cấp ngày 17/10/2025" both sit near the top of the
page and neither is a publication time.

Re-grading the Phase 1 baseline against the curated corpus turns
`temporal_validity` from `BLIND` into **3 cases decided, 1 passed** — two of the
three `as_of` cases cited sources published after their own cutoff. That defect
was always there; nothing could see it until now.

**Ground truth: three of four frozen, and the fourth deliberately not.**
`rl-mc-001` VCB charter capital 83.557 tỷ đồng (issuer page; the 94.238 tỷ the
April 2026 AGM approved is a plan and is the trap), `rl-mc-002` HPG shares
outstanding 8.442.964.520 (reconciles with 84.430 tỷ at a 10.000 đồng par),
`rl-mc-003` refinancing rate 4,5%/năm (1123/QĐ-NHNN). Each value carries its
source URL, source class, publication date and tolerance.

`rl-mc-004` — HPG's foreign-ownership ceiling — is left unfrozen on purpose. The
issuer, HOSE and the aggregators were searched and **no page states HPG's own
published ceiling**; what they offer is the general rule (49% / 50% / up to 100%
by shareholder decision), which is exactly the substitution this case was written
to catch. Freezing one of those would make the corpus assert a figure no source
states. The grader therefore scores it `None`, and the honest reading is that a
correct answer refuses to name a ceiling — which suggests the case may belong to
the refusal family rather than to material-claim, a call for the golden owner.

The artifact now records the ledger the runtime wrote (read from
`claim_ledger_for_message`, never parsed back out of prose) and the question a
Turn ended on. The two corpus tests that pinned the empty state were rewritten
rather than deleted: they now hold what they always protected — no invented
truth — by demanding that every frozen figure name the page it came off and that
every curated date record its extraction method and confidence.

### Measured gates

```text
pytest tests/                       1456 passed   (Phase 5 closed at 1401)
pytest tests/golden/                 131 passed
alembic upgrade → downgrade → upgrade  clean round trip, backup taken first
compileall src golden tests            OK
git diff --check                       clean
retired-path scan                      1 hit, and it is a sentence saying the
                                       capability does not exist
pnpm lint · type-check · test · build  green, 458 web tests
```

### Slice 7 — the paid run found two defects before it could measure anything

The first release attempt at a $25 ceiling was **stopped deliberately after 8 of
120 Turns**, because the outcome table said it was measuring nothing:
`112 incomplete/user_active_turn · 7 complete · 1 running`.

**Defect 1 — the harness waited less than the Turn it started.**
`golden/run.await_terminal` polled for a fixed 60 seconds, which was correct
while every Turn was light. The deep lane is given 1,800 seconds on purpose, so
the first deep Turn outlived the poll; the harness gave up, released its
concurrency slot and moved on while the Turn it abandoned was **still active**.
Admission counts what the table says is active, so every case after it was
refused. One unfinished deep Turn cost 112 of 120 case-trials. The wait now
comes from the lane the question routes to — same `route_intent` the service
uses — plus a margin for the terminal write to land.

**Defect 2 — the research pass was asked for a shape, not held to one.** The
verifier call carries a strict schema; the research and counterevidence passes
only had a prompt note. On the live route the research pass wrote a memo, the
parse raised, and a Turn holding 19 sources threw all of it away over an
envelope. A strict format cannot bind the pass itself — it is holding a tool
conversation — so it now binds the one call that has stopped calling tools: on a
parse failure the pipeline makes **one** bounded, tool-free, strict-schema retry
that transcribes the pass's own prose into the typed draft, and fails honestly if
that also misses.

**Defect 3 — a hard dimension held the deep lane to the light lane's budget.**
Found by grading the verified deep case, not by reading code: `budget` failed
with "19 dispatched external calls over a cap of 7", where 7 is the light lane's
cap and the deep lane's is 20. `runtime_constants` recorded one flat pair — the
module constants, which since Phase 3 *are* the light lane's — and the grader
applied it to every case, so every deep case in a release run would have failed
a hard dimension for doing what its lane was configured to do. Ceilings are now
recorded per lane and resolved through the same `route_intent` the service uses,
with a fallback to the flat pair for artifacts recorded before the field existed.

**Defect 4 — introduced while fixing the others, and invisible by design.**
Relabelling the planner's trajectory row to `planning` was right in intent and
made things worse: the store's stage allowlist had drifted from `PipelineStage`
and did not contain it. A failed trajectory write is deliberately swallowed — a
private trace is not the answer — so the row stopped existing with nothing but a
log line, and every deep Turn lost its planner's four queries from the audit
trail. Found by querying the live table, not by a test. The allowlist now holds
it and a test keeps the two vocabularies together. No grader reads trajectory
rows, so the run in flight stayed valid.

**Live verification of the fixed pipeline** (`rl-tc-001`, real route, own run):
`complete`, 19 external calls, 41 sources, 302 s, **$0.23**. Full three passes.
Ledger: 40 claims over 6 evidence, verdicts including `unsupported` and
`temporally_invalid` — the temporal rule fired on a real source, a 2025
announcement offered in support of a 2026 claim — and a verifier outcome of
`insufficient_evidence`, which is the first-class refusal §2 asks for rather than
a crash. That is the phase's core capability demonstrated end to end.

The corpus-wide run was then re-taken at **concurrency 6**, which is the
condition the Phase 1 baseline artifact records, so the two runs are comparable.

### Open finding handed to the product owner: the router reaches 4 of 40 cases

Routing the release corpus through `lanes.route_reason` offline gives
**36 light / 4 deep**. The four are three `thesis_check` cases and one
`fact_verification`. `event_memo` and `source_conflict` — two of the four jobs
§1 built the deep pipeline for — route light, because their questions never say
"memo" or "kiểm chứng" and fall under the 240-character length rule.

This is the routing-quality question Phase 3 explicitly handed to Phase 6, and
it is a two-way door under §9. It is **not** being changed here, and the reason
is the measurement: widening the keywords mid-run would produce a baseline
describing a system nobody ran. The number belongs in the decision — a Phase 6
gate run in which 90% of the corpus never reaches the capability the phase built
cannot be read as a verdict on that capability.

## Review record

Self-reviewed on 2026-09-02 against roadmap Phase 6, §2 truth contract, §6
dependency rules, §9 preflight and the verified Phase 5 implementation. The
plan has executable gates, a code-verified hand-off, named assumptions with
fail-closed fallbacks and an additive rollback path. It introduces no later-
phase capability and is ready for implementation. The paid golden gate remains
explicitly conditional on the product owner supplying a monetary ceiling; that
condition does not block the implementation slices that precede it.

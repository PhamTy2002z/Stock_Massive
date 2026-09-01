# Phase 5 — Permission, guardrails, web security

Status: **Ready**  
Branch: `feat/phase-05-permission-guardrails-web-security`  
Opened: 2026-09-01  
Authority: [`docs/roadmap.md`](../../docs/roadmap.md), Phase 5 and §9

## Brainstorm contract

### Outcome

Every capability call is admitted by a typed capability/resource policy, and
the existing web-research surface can broaden fan-out without letting indirect
content escalate permission, cross tenant scope, evade SSRF/size/time bounds,
poison a durable write in the same Turn, or place a raw credential in the tool
trace.

### Constraints

- Preserve the five-tool catalog: `web_search`, `fetch_url`, `session_search`,
  `remember_fact`, `recall_facts`.
- Preserve the public HTTP/SSE contract and database schema.
- Keep permission, approval, deployment availability/kill switch, sandbox and
  tenant authorization as separate decisions. No approval UI or sandbox is
  introduced in this phase.
- Preserve SSRF validation, connect-time DNS pinning, redirect re-validation,
  fetch byte/time bounds, one-call-one-result, stable ordering and terminal
  Turn settlement.
- Scanner failure is advisory and fail-open for answering; authorization,
  tenant scope, schema integrity, secret-bearing egress and durable side effects
  fail closed.
- Quality precedes speed and cost. Egress bounds terminate abusive/repeating
  work; they are not a reason to narrow legitimate research.
- No subagent is used, per the product owner's instruction for this run.

### Non-goals

- No new capability, market-data SDK, local analysis path, shell, file write,
  MCP, delegation or compute sandbox.
- No durable approval request/card flow; `ask` settles as a typed
  `approval_required` result until a later accepted scope owns that flow.
- No change to the declared default permission of any shipped capability. In
  particular, `remember_fact` remains explicitly allowed for an uncontaminated
  Turn; changing that default is a §9 one-way-door decision.
- No Phase 6 evidence ledger, source ranking or three-pass research pipeline.
- No Phase 10 queue/coalescing redesign. The existing Redis single-flight and
  product-cache window remain the fleet deduplication mechanism.

### Observable acceptance criteria

1. Permission is a typed ordered rule set over capability and resource. Last
   matching rule wins; no match and unknown capability deny. An `ask` rule is
   valid only for a capability declared with a real write effect.
2. The model is not offered a globally denied/approval-only capability; a
   resource-narrowed capability is checked again with parsed, schema-valid
   arguments at dispatch.
3. Arguments are validated against the exact frozen JSON schema offered to the
   model before any handler runs. Missing/extra/wrong-type/out-of-range values
   settle one `invalid_arguments` result.
4. A successful untrusted external read taints the Turn. A later durable write
   in that Turn is refused before dispatch, so a page cannot turn its text into
   a memory mutation. Reads and an earlier explicit write keep their behavior.
5. A secret-shaped or encoded secret-bearing web query/URL is rejected before
   DNS or provider I/O. Tool traces recursively redact credential-shaped values
   in arguments, results and error text while the live result remains usable.
6. The web lane enforces both the existing fleet allowance and a Redis-backed
   per-domain allowance; fresh-cache/single-flight hits do not spend either.
   The per-Turn logical egress ceiling remains `MAX_EXTERNAL_TOOL_CALLS`.
7. Indirect injection in plain, percent/HTML-encoded, zero-width and bidi-marked
   text produces a content-light risk verdict. Scanner exception/timeout still
   returns `unknown` and never removes the answer.
8. The adversarial suite reports 0 permission escalation and 0 raw secret in
   trace. Its benign corpus has 0 blocked cases (baseline locked at 0/20).
9. Focused security tests, the full API suite, compileall, web lint/type/test/
   build and `git diff --check` pass. No public HTTP/SSE or DB contract changes.

## Scout evidence

### Project and relevant owners

- Python 3.12/FastAPI/SQLAlchemy backend under `apps/api`; Next.js/TypeScript
  projection under `apps/web`.
- Unified declaration and frozen surface: `src/agent/registry.py`,
  `definitions.py`, `toolsets.py`.
- Single dispatch choke point: `src/agent/executor.py`; Turn ownership and
  logical external-call budget: `src/agent/loop.py`.
- Repetition ladder: `src/agent/guardrails.py` already distinguishes exact
  failure, same-tool failure and no-progress.
- Trust boundary and advisory scanner: `src/agent/untrusted.py`,
  `threat_patterns.py`.
- Web boundary: `src/agent/tools/web.py`; shared Redis cache/single-flight and
  fleet allowance: `src/core/web_lane.py`.
- Tenant-scoped memory SQL: `src/agent/tools/memory.py`; trusted `user_id`
  arrives out-of-band in `ToolContext`.
- Durable trace: executor → loop `_trace_writer` →
  `AgentPersistence.record_tool_call` → `agent_tool_call`.

### Existing contracts and baseline

- Phase 4 hand-off is present in code: frozen `ResolvedToolSurface`, deep/light
  lanes, context engine, terminal Turn settlement and exactly five registered
  tools.
- Existing focused baseline on 2026-09-01:
  `184 passed` for capability/executor/guardrail/web/untrusted/threat/memory/
  auth tests.
- SSRF/DNS/redirect/page-size/time protections are already tested and will be
  extended, not replaced.
- Existing permission is one enum per declaration; it has no resource match,
  no no-match decision, and `ask` shares `permission_denied` with `deny`.
- Existing trace stores raw argument/result strings. The LLM error layer has a
  proven credential redactor, but the tool trace does not use it.
- Existing `WebLane` is Redis-backed, single-flight per cache key and globally
  rate-limited, but the allowance key has no domain dimension.
- OpenCode supplies the useful rule shape (ordered typed rules and resource
  patterns) but its default `ask`/agent-wide `allow` is not copied: roadmap
  Phase 5 explicitly requires no-match/unknown deny.
- Hermes supplies the hard-wrapper/advisory-scan split and secret-egress lesson;
  the repository already adopted the wrapper and declaration-driven trust.

## Design

### Typed permission policy

Add a small pure `agent/permissions.py` module containing `ToolPermission`,
`PermissionRule`, `PermissionPolicy` and content-escalation state. A declaration
owns a non-empty tuple of rules plus an optional argument name used as the
resource. Resolution freezes those rules into the same surface as schema and
handler. Evaluation is deterministic and content-free: ordered rules,
`fnmatchcase`, last match wins, no match denies.

The executor parses and validates arguments, derives the resource from the
frozen declaration, evaluates permission, then runs guardrails and handler.
Global deny/ask-only declarations do not enter `offered_schemas`; declarations
with at least one possible `allow` remain visible and are checked per resource.
`ask` produces `approval_required`, not an invented approval.

### Hard and advisory guardrails

The permission state records only the fact that an untrusted result completed;
it never stores attacker text. Once set, a later `WRITE` call is refused. This
is a hard boundary beside (not inside) the advisory scanner. Existing
allow/warn/block/halt repetition logic remains unchanged.

Schema validation is a compact validator for the JSON Schema subset the
registry actually emits: object, required/additional properties, string,
integer/number/boolean/array, enum and scalar length/range bounds. Unsupported
schema keywords fail registration rather than being silently ignored.

### Web and trace security

Use the existing credential redactor through a recursive trace-only projection.
The result returned to the model is not replaced by the trace projection.
Before any search/DNS/download, decode bounded percent/HTML obfuscation, strip
invisible/bidi controls and reject credential-shaped outbound text.

Extend `WebLane.read` with a normalized domain dimension. A real cache miss
spends the global Redis window and its per-domain window; a cache hit spends
neither. Keep the existing per-Turn logical call ceiling in the executor/loop.
Phase 10 remains owner of scale tuning and richer fleet queuing.

## Preflight §9

### 1. Runnable gates and numeric thresholds

```bash
cd apps/api && pytest tests/test_agent_security_adversarial.py -q
cd apps/api && pytest tests/test_agent_capability_contract.py \
  tests/test_agent_tool_registry.py tests/test_agent_tool_executor.py \
  tests/test_agent_guardrails.py tests/test_agent_web_tools.py \
  tests/test_agent_untrusted_results.py tests/test_threat_patterns.py \
  tests/test_agent_memory_tools.py tests/test_auth_security.py -q
cd apps/api && pytest -q
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint && pnpm --dir apps/web type-check \
  && pnpm --dir apps/web test && pnpm --dir apps/web build
git diff --check
```

The adversarial file encodes the phase thresholds: escalation `0`, raw secret
in trace `0`, benign false-positive blocks `0/20`. SSRF/redirect/oversize and
scanner fail-open stay binary contract tests in the focused suite.

### 2. Verified Phase 4 hand-off

Verified directly on branch `feat/phase-04-context-engine` at `cae8732` before
opening this branch: frozen surface resolution, typed Turn/tool lifecycle,
stable-order executor, real lane profiles, context engine and terminal owners
are present. The focused baseline above is green; Phase 4 is not trusted only
because its roadmap label says Done.

### 3. Named assumptions and fallback

| Assumption | Fallback if false |
|---|---|
| A1. The five shipped schemas use only the validator subset named above. | Registration tests enumerate every keyword. If a legitimate keyword is found, implement and test it before enabling dispatch; never ignore it. |
| A2. A write after untrusted content is uncommon and safe to defer to a clean next Turn. | Measure typed `content_escalation_blocked` rows. If legitimate usage is material, open a separate approval-flow decision; do not weaken the guard silently. |
| A3. Domain can be derived from the target URL, while search provider egress is `api.tavily.com`. | A call without a normalized domain is charged to `unknown`; it is never exempt from the fleet tier. |
| A4. The proven LLM credential patterns cover the credential shapes this deployment holds. | Add a pattern only with a failing adversarial fixture and rerun the 20-case benign corpus; do not paste secret values into configuration or tests. |
| A5. Per-domain fixed windows plus existing per-key single-flight are enough for Phase 5. | If load evidence shows hot-key contention or cross-region races, record it for the Phase 10 queue/coalescing owner; the security boundary still fails closed on allowance-store failure. |

### 4. Rollback

No migration, table, endpoint or SSE event is added. Stop by reverting this
branch. Existing trace rows and cache keys remain readable; new per-domain
allowance keys expire within their one-minute window. Permission declarations
are code-only and atomic with their frozen surface, so rollback restores the
old resolver without data conversion.

## One-way-door audit

- Public HTTP/SSE: unchanged.
- Database/data retention: unchanged; no migration or drop.
- Default permissions: unchanged for all five shipped tools.
- Tool catalog: unchanged.
- Truth contract and legal research/advice boundary: unchanged.

## Implementation slices

1. Add typed permission/resource rules, frozen surface identity, schema
   validation and distinct deny/approval/content-escalation results.
2. Add trace-only recursive credential redaction and outbound web secret guard.
3. Add encoded/bidi scan normalization and lock the benign baseline.
4. Add per-domain Redis fleet allowance while retaining cache/single-flight and
   per-Turn egress ceilings.
5. Build the adversarial gate, run focused/full verification, self-review every
   changed caller and contract, then write the phase report and update roadmap.

## Review record

Plan reviewed against roadmap Phase 5, §6 dependency rules and §9 preflight on
2026-09-01. All four preflight questions have executable/evidenced answers, no
one-way door is crossed, and implementation may start.

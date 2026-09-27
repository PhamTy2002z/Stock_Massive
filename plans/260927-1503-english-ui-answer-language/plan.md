# English webapp, answers in the user's language

Status: done 2026-09-27 · Branch: feat/host-owned-numbers

Result: web lint/tsc/vitest (614) green; api 2753 pass, the 128 failures all
`agent_turn.heartbeat_at does not exist` on the Homebrew Postgres the host suite
reads, which is behind alembic head (not this plan's change).

## Outcome
- Every UI string in `apps/web` is English (chrome, narration, errors, locale formats).
- Backend strings the UI renders as chrome are English (tool display names and
  call summaries, chart labels, question-card frame text, HTTP error details).
- The answer follows the language of the user's question (owner decision
  2026-09-27). Text the host writes *into* an answer — figure labels, notes, the
  sources heading, the claim ledger, repair prompts that make the model rewrite —
  follows the answer's language (vi or en).

## Rules
1. Chrome / system narration → English always.
2. Inside the answer → the answer's language, detected from the answer text.
3. Model-facing-only text (system prompt, tool results) may stay Vietnamese, but
   no model call whose output reaches the user may force Vietnamese.
4. Stored answers keep their Vietnamese labels; the web parses both label sets.

## Phases
| # | Scope | Owner |
|---|-------|-------|
| 1 | Shared web copy (`copy.ts`, `failure.ts`, `format.ts`, `market-session.ts`) | controller |
| 2 | Web settings/auth, shell/e2e, message/app/ui, lib tests | 4 parallel agents |
| 3 | Grounding + host answer labels by answer language, English figure recognition | agent |
| 4 | Backend UI-facing strings → English, deep-lane templates by language | agent |
| 5 | `figure-markers.ts` parses vi+en labels; DESIGN.md / CLAUDE.md language notes | controller |

## Acceptance
- No Vietnamese diacritics left in `apps/web/src` except fixtures standing for
  user input or backend answer text, and the vi label set the parser accepts.
- `pnpm --dir apps/web lint type-check test` pass; `make test` passes in `apps/api`.
- An English answer gets English labels/heading/ledger; a Vietnamese one keeps
  Vietnamese; the web renders both as chips and a sources pill.

## Non-goals
Rewriting the system prompt into English; changing tool result formats.

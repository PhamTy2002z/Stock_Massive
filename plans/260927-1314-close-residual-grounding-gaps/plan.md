# Close the residual grounding gaps

Status: delivered, live re-check partial (kiro quota 402 from 14:09) · Branch: `feat/host-owned-numbers` (uncommitted, shared tree)
Source: `plans/reports/research-260927-1259-harness-integration-candidates.md`
Follows `plans/260927-1018-close-delivery-gaps/`.

## Outcome
The gaps the 27/09 selftest rounds still measured on `kiro-glm-5` are closed by
the host, not by prompt: a tool call in a past year the question never named is
refused before it spends a request; a recency search returns dated news; the
calendar (weekday, "phiên hôm nay" on a closed day) is checked in the answer; a
market figure only an older row prints, or a reported ratio called "priced
today", is held to its period; and invariants of the figure check run over
generated answers without golden answers.

## Decisions (owner delegated all choices, 2026-09-27)
1. **Refuse, don't rewrite, a stale-year call** — once per distinct call; the
   identical call again runs (the model insisting is the escape for a question
   the scope reader missed). `BLOCKED_CALL`, no new public error code.
   Scope = this year, years the question names, and years a stated horizon
   reaches ("3 năm qua", "cùng kỳ", "năm ngoái"). Last year is refused only as a
   date or month, never as a bare year or quarter (the latest full year).
2. **Tavily `topic: news` when `recency_days` is set.** Measured: `days` is
   ignored on the general index and only news returns `published_date`.
3. **Calendar facts go through the existing label + one repair round**, not a
   silent rewrite; the repair note names the right weekday.
4. **No new dependency for property tests**: seeded `random`, not Hypothesis.
5. Figure IDs issued by the host (model echoes an ID, host prints the number)
   deferred: the new period rules closed every mis-attribution the rounds
   measured; revisit if a round shows a class the literal check cannot see.

## Non-goals
Weekday in the runtime tail (the selftest session owns it), prompt changes,
paid data, UI.

## Changes
| Where | What |
|---|---|
| `evidence/source_policy.py` | `years_in_scope`, `stale_year` |
| `registry.py`, `loop.py`, `executor.py` | `ToolContext.question_years`; refusal before dispatch |
| `tools/web.py` | news index for recency searches; `recency_days` description |
| `evidence/grounding.py` | weekday check; no-session-today check; older-row market figure on an undated line; reported ratio "priced today"; market conflict scoped to the named ticker/index; source-side down words ("giảm 1,31%" = -1,31%); future periods on pages; a range's start takes its end's unit; currency glued to digits and English month dates read on pages; a counted noun is not a price; price paths and "so với Q…" are history/comparison |
| `tests/` | policy + executor tests, live-derived grounding tests, `test_agent_grounding_properties.py` (1200 generated cases) |
| `ARCHITECTURE.md` | §6 row, §9 row |

## Acceptance
- Unit + property suites green (grounding 1244, executor/policy 75).
- Live re-ask of the round-2 questions on kiro-glm-5 with no wrong-year tool
  argument, no weekday error, no "phiên hôm nay" on Sunday, and fewer
  `không rõ ngày` web labels than round 2.

## Result
Found while delivering, fixed in the same place (all from replaying live Turns):
page figures the check wrongly refused — a VN30 close "contradicted" by
VN-Index's row, "-1,31%" against "giảm 1,31%", FTSE's planned "20% vào tháng
3/2027", "9,1-9,3%", "VND64.2 trillion" and "September 30" on English pages,
"9.200 căn" read as a price, a price path "17.600 → 21.650", "so với Q3/2025".

Live, kiro-glm-5, 27/09/2026 (Sunday):
- Question set fb1 (13:35): 5/5 complete; the three rules targeted (week
  question, weekday/today, P/B "hiện tại", volume of the latest session) clean;
  recency searches returned dated news (`[2 · 23/09/2026]` instead of
  `không rõ ngày`).
- Round-2 anchors re-asked (13:45): A3 issued `end=2025-06-23`, was refused,
  and re-called with 2026 — in round 2 the same question ran three 2025 reads
  and a 2025 search. N1–N10 hit the route's cooldown (not code).
- Selftest r4 (another session, 14:00, this code): A1, A2, A3, N1 pass every
  automatic criterion (A3 failed Năm and Ngày in rounds 1 and 2); N2 (NVL)
  had four 2024 searches refused. Replayed with the final code, N2's
  unverified figures drop from 16 to 2, both self-computed percentages.
- Replay of every round-2/3/4 Turn with full tool output: the only verdicts
  the new rules change on live answers are the two targeted mis-attributions
  (N1 P/B "theo giá gần nhất", N6 volume of 16/07).
- Backend 2766 passed; api redeployed 14:18.

Second live pass (14:33–15:17, quota back), round-2 N questions on this code:
- Số 8/10 (round 2: 4/10), Ngày 7/10 (3/10), Năm 8/10 (8/10; both misses are
  deep-lane searches for a bare "2025", which the policy allows on purpose).
  N2 (DGC table) failed only because the model put "%" in the column header;
  fixed (a cell takes its column header's bracketed unit) — replay clean.
- Deep lane: the research pass on kiro-glm-5 writes the reader's answer in
  prose and the strict recovery comes back prose too, so every deep Turn ended
  `research_draft_schema_invalid` with no answer (0/2 in round 2). Now:
  `pipeline._object_text` reads an object out of prose/`</think>`/fences, and
  when no draft can be read the prose becomes the answer under the light-lane
  figure check and ledger (never the verifier's "verified"). Live: N7 and N10
  both answer (2/2), invented figures labelled.
- Chart for that path: `visual.build_visual` admitted reads only by the
  pipeline's evidence id, which the figure check's ledger never carries; it
  now also admits the feed a grounded figure cited. Replayed N10: chart built.
  **Not yet live** — deploy waits for another session's `agent_turn.heartbeat_at`
  migration (model has the column, DB does not; restarting now breaks Turns).
- Seen once, not reproduced: a deep Turn (2efefc7a, pre-fallback code) stayed
  `running` 16 min after its pipeline failed; no exception, no DB wait, low CPU.
  Swept on restart. Another session is adding a Turn heartbeat.
- Still open: signal-desk research pass that hits its tool-round ceiling while
  the route keeps returning tool calls publishes the lead-in sentence (r4 N9);
  needs a tool-free answering call, not the prose fallback.

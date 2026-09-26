# P0 — host-owned figures

## Cause (proved on Turn f82f272c, 2026-09-26)
Model asked `get_market_data` for 2024-01-01→2025-01-20 although the prompt said
today = 2026-09-26; wrote "hiện tại 35.000–38.000đ" while its own tool returned
56.500 (and the real latest close is 76.500); light lane never ran any figure
check, so the ledger held a row for 1 of 15 Turns.

## Changes
1. `tools/market_data.py` — `start`/`end` optional; host defaults end = today
   (ICT), start = end − 92 days. A requested `end` more than 7 days before today
   with no reason in the question returns `date_note` ("hôm nay là …"). Payload
   and excerpt lead with `latest` (session date, close, change vs previous
   session, volume, whether today had a session).
2. `tools/web.py` — a `web_search` query naming a year before the current one
   gets `year_note` in its result (query is not rewritten).
3. `evidence/grounding.py` (new) — extract financial figures from the answer
   (dates, years, quarters, list markers and bare counts skipped), match each
   against this Turn's evidence (market rows, fetched pages, search snippets,
   later: statements and calculations) with unit normalisation (`56.500`,
   `56,5 nghìn`, `56.5k`, tỷ/nghìn tỷ, %) and rounding tolerance at the
   precision the answer wrote. Each figure gets a date: market row session or
   page publication. Statuses: grounded · `nguồn cũ` (web older than the
   window) · `chưa kiểm chứng` (absent, or its sentence names a period no
   matching source is in, or it says "hiện tại" and matches only older sessions).
   Numbers from the user's own question or memory tools are exempt.
4. `loop.py` — at settle on every lane: ground → if unsupported figures and no
   repair yet, one tool-free repair call with the draft and the list → ground
   again → annotate each figure in place (`[1 · 25/09/2026]`,
   `[2 · 07/01/2026 · nguồn cũ]`, `[chưa kiểm chứng]`) plus a dated sources
   footer; write a claim ledger for every Turn (one claim per figure).
5. `prompt/sections.py` — rules: copy figures exactly from tool results with
   their date; tool error/empty ⇒ say data is missing; conflicting sources ⇒
   prefer structured tool data, then newer, and state the conflict; non-trading
   day ⇒ "hiện tại" is the latest session, named.

## Edge cases → where handled
Non-trading day: `latest.session_today` + prompt · formats/rounding: grounding
normaliser · self-computed %: unmatched ⇒ labelled (P1 routes them through the
calculator) · tool error/empty: no evidence ⇒ any figure labelled + prompt ·
conflicts: prompt now, structured-vs-web check in P1.

## Validation
Unit tests for grounding (formats, tolerance, dates, periods, exemptions),
market defaults/latest/date_note, web year_note, loop repair + ledger on light
lane; full API + web suites; live re-run of the 4 questions on kiro-glm-5 and a
DB query showing a ledger row per Turn.

## Risk / rollback
Repair adds ≤1 model call per Turn with unsupported figures. Figure check can
false-accept a fabricated figure that coincides with a real one in a large
source (known ceiling of literal matching); the period rule narrows it.
Rollback = revert the branch; no schema change.

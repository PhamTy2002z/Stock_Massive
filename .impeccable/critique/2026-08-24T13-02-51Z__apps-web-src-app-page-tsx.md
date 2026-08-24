---
target: primary VisgniteAI workspace
total_score: 23
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
timestamp: 2026-08-24T13-02-51Z
slug: apps-web-src-app-page-tsx
---
Method: dual-agent (A: /root/critique_design_review · B: /root/critique_detector)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3/4 | Loading and refusal states are present, but consequential market figures do not consistently expose as-of time or freshness. |
| 2 | Match System / Real World | 3/4 | Vietnamese market conventions are strong; English and legacy Alpha Desk terms interrupt the Vietnamese-first model. |
| 3 | User Control and Freedom | 2/4 | Draft preservation, cancellation, and panel closing work; deletion has no undo and several prominent flows end at disabled actions. |
| 4 | Consistency and Standards | 3/4 | Tokens and core patterns are coherent, but navigation semantics and VisgniteAI/Alpha Desk naming diverge. |
| 5 | Error Prevention | 2/4 | Invalid submission is prevented, but immediate deletion and live-looking sample figures create avoidable risk. |
| 6 | Recognition Rather Than Recall | 3/4 | Labels, history, search, and persistent context help; some actions remain hover-dependent or hidden in icon menus. |
| 7 | Flexibility and Efficiency | 2/4 | Shortcuts and contextual inspection help experts; price-board rows and inspector resizing lack keyboard equivalents. |
| 8 | Aesthetic and Minimalist Design | 2/4 | The visual system is disciplined, but unavailable navigation, attachments, voice, alerts, and sharing produce nonfunctional chrome. |
| 9 | Error Recovery | 2/4 | Some failures are actionable, while symbol-detail errors expose raw messages without retry and clipboard failures disappear silently. |
| 10 | Help and Documentation | 1/4 | The investment caution helps, but evidence semantics, analysis states, shortcuts, and unfamiliar concepts lack contextual guidance. |
| **Total** | | **23/40** | **Acceptable foundation; material trust, accessibility, and hierarchy work remains.** |

## Design Specificity Verdict

**Authored, but not yet fully credible.** The cool tonal ladder, rationed amber, Vietnamese market palette, monospaced figures, and persistent three-region workspace make this recognizably VisgniteAI. It is not a generic dashboard reskin. The interaction layer remains closer to familiar AI-chat conventions than the product positioning promises, and the interface inconsistently expresses its defining point-in-time, evidence-backed character at the exact moment users inspect data.

**Independent design assessment:** The spatial model is unusually well matched to research: users retain a question, transcript, draft, and symbol context while opening evidence beside the work. Specificity falls away where controls imitate future capability and where figures omit source, freshness, or quality context.

**Deterministic scan:** The CLI detector scanned 80 markup files and reported one warning: `layout-transition` at `apps/web/src/app/globals.css:329`, where sidebar motion transitions `width`, `margin`, `left`, and `right`. This corroborates a real performance risk rather than a strong false positive. The live detector initially reported nine findings during loading: four layout-property animations, one overflow, one Inter-overuse notice, one em-dash-overuse notice, and two shape-assembled illustration notices. The settled count varied with loading state. Inter is the documented body face, em dashes are the specified missing-data treatment, and the illustration alerts appeared to target injected development controls; those are false positives. Transient overflow alerts were not stable enough to elevate.

**Visual overlays:** Mutable injection and overlay rendering were verified in a fresh headless Chromium page, but no persistent user-visible **[Human]** browser tab could be presented because the session exposed no native browser visibility surface. There is therefore no reliable overlay left open for the user; the verified screenshot and temporary browser state were cleaned up.

## Overall Impression

This is a serious, product-specific foundation with stronger visual judgment than most early financial interfaces. Its biggest opportunity is not more styling. It is closing the credibility gap between an evidence-led promise and an interface that still displays unsupported figures and invites users into unavailable actions.

## What's Working

1. **The workspace fits research behavior.** Sidebar memory, a fluid central workspace, and a contextual inspector preserve the user's question and evidence during comparison instead of forcing page churn.
2. **The visual vocabulary is genuinely market-specific.** Slate surface steps, tabular mono figures, the trần/tham chiếu/sàn palette, and separation of market color from brand amber create a calm Vietnamese-market instrument rather than casino-like fintech.
3. **Operational details show care.** Draft preservation, cancellation, reduced-motion handling, empty states, accessible names, and persistent analysis context remove meaningful friction.

## Priority Issues

### [P1] Unsupported financial figures look operational

**Why it matters:** Hardcoded liquidity, foreign-flow, and index-contribution figures retain normal numeric hierarchy and red/green semantics. A small “Số liệu mẫu” note does not neutralize the trust risk because investors scan the figure before its footnote. This directly conflicts with the product's evidence contract.

**Fix:** Remove unsupported figures from operational views. Replace them with an explicit unavailable state naming the missing source or calculation. When real figures return, attach source, as-of time, freshness, unit, and quality beside the value.

**Suggested command:** `$impeccable harden`

### [P1] Nonfunctional controls dominate too much of the shell

**Why it matters:** Disabled screener and report navigation, four disabled thread actions, seven unavailable attachment actions, voice input, price alerts, and a Share dialog with a disabled completion action repeatedly convert curiosity into refusal. The product feels staged rather than dependable.

**Fix:** Remove unavailable actions from everyday workflows. If roadmap visibility matters, consolidate it into one explicitly labeled preview or capability-status surface.

**Suggested command:** `$impeccable distill`

### [P1] Core market interactions lack keyboard equivalence

**Why it matters:** Clickable price-board `<tr>` elements cannot be focused or activated from the keyboard; the semantic inspector separator supports pointer drag but not keyboard resize; custom dialogs do not demonstrate focus containment or restoration. These are blockers in core research paths, not peripheral polish.

**Fix:** Put real focusable controls in table rows, support keyboard resizing with value semantics, and use a dialog primitive that traps and restores focus. Raise undersized 28–34px touch controls where motor use demands it.

**Suggested command:** `$impeccable audit`

### [P2] Navigation mixes modes, destinations, and creation actions

**Why it matters:** “Hỏi đáp / Bảng giá” reads as a mode switch, while “Trò chuyện mới / Tin tức” appears as adjacent navigation. News activates neither segment, and conversation actions remain visible over board and news contexts. Users must infer the location model.

**Fix:** Establish one primary navigation grammar, separate creation from destinations, and make the top bar contextual to the active view.

**Suggested command:** `$impeccable shape`

### [P2] Trust language and recovery are inconsistent

**Why it matters:** English greeting copy, “Ask Alpha Desk,” and “Stop” conflict with a Vietnamese-first VisgniteAI product. Raw symbol-detail errors and silent clipboard failures make the careful brand voice disappear precisely when reassurance is needed.

**Fix:** Standardize product naming and operational copy in Vietnamese. Replace transport errors with concise explanations, retry paths, and preservation of the user's current context.

**Suggested command:** `$impeccable clarify`

## Persona Red Flags

**Alex — Impatient power user:** Command-K and settings shortcuts exist but are weakly taught. VN30 rows work by mouse but not keyboard. Disabled controls slow scanning, and Share, attachment, and thread menus consume clicks before revealing that no task can be completed.

**Sam — Accessibility-dependent user:** Price-board rows are unreachable by keyboard; inspector resizing is pointer-only; custom dialogs lack demonstrated focus containment/restoration; several controls are below comfortable motor/touch targets; smooth scrolling needs a CSS reduced-motion override.

**Riley — Deliberate stress tester:** Hardcoded figures can be mistaken for current values. Sharing scope looks consequential despite link creation being impossible. Symbol errors may expose technical details without retry. Clipboard refusal fails silently. Consequential figures cannot consistently answer “as of when, from where, and with what quality?”

## Minor Observations

- Typography should support Vietnamese naturally instead of using English copy to accommodate a display treatment.
- “Tuỳ chọn hội thoại” remains visible over market-board and news titles.
- Hover/focus-revealed row actions remain difficult to discover on touch devices.
- Horizontal table overflow plus an open inspector can push decision-relevant columns out of view.
- The sidebar transition at `globals.css:329` animates layout properties; prefer transform-based motion or remove the animation if spatial continuity does not justify its cost.
- Market color is usually paired with signs and figures, which is a meaningful accessibility strength.

## Questions to Consider

- If evidence integrity is the defining promise, why is any unsupported number allowed to render, even with a sample footnote?
- What would the shell feel like if every visible control worked today?
- Is the primary opening decision “ask a question” or “inspect the market,” and what chrome can defer until that choice is made?
- Can every consequential figure answer “as of when, from where, and with what quality” without opening another surface?
- Should this feel like AI chat with market tools, or a research desk whose conversational layer happens to be AI?

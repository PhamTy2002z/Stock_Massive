---
title: Refine conversation sidebar
date: 2026-09-27
summary: "Compact sidebar spacing, bounded recent history, and accessible conversation search."
---

# Refine conversation sidebar

## Changes

Added labeled search, conditional pinned group, 20 recent unpinned chats, and a plain Xem tất cả button that opens the complete search list. Removed unavailable destinations. Added keyboard search selection, empty-result recovery, and floating sidebar dismissal. Reduced desktop rows to 36px while retaining 44px coarse-pointer targets.

## Validation

Focused sidebar, menu, shell, and settings tests passed: 34 passed, 4 existing skips. Type-check and targeted lint passed. A fresh browser reached the login screen, so authenticated visual verification remains unavailable. Existing unrelated workspace changes were preserved.

## Scope

Archive and saved-result features remain future work, as proposed before implementation. No database changes. Updated DESIGN.md navigation description. AgentWiki publish skipped.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

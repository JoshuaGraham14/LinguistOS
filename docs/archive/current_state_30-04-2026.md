# LinguistOS Current State Spec

> Date: 30/04/2026  
> Status: Live snapshot (concise)

## 1) Current App State

LinguistOS is currently a **word-first language learning app** with:

- Canonical vocab model (`lemma`, `surface_form`, `surface_forms`, gloss fields, metadata).
- Workspace-scoped data ownership and local-user auth guardrails.
- Mastery tracking (Leitner-style) per word.
- Sentence persistence with word links.
- Lexicon table view, flashcards, sentence practice, Word Home.
- Quick capture + selection capture for low-friction word intake.

## 2) What Was Recently Added

Recent merged work introduced **word-atom flexibility (MVP+ thin)** plus a major **workspace + shell UX pass**:

- New token APIs:
  - `POST /api/tokens/resolve`
  - `POST /api/tokens/action`
- Persistent `word_occurrences` model for token-context evidence.
- Shared token UI primitives:
  - `TokenizedText`
  - `ClickableToken`
  - `WordActionPopover`
- Cross-surface clickable token behavior in key sentence/word surfaces.
- Thin disambiguation path for multi-match tokens.
- Debounced backend token resolution + lightweight token telemetry counters.
- Large Word quick-view modal with blurred backdrop, opened from word chips.

Recent workspace/shell/product polish now live:

- App-level top bar and app history provider:
  - In-app back/forward controls now track internal navigation only.
  - On workspace switch, history is reset and the app routes to dashboard (`/`) as a fresh context.
- Workspace switch UX overhaul:
  - Full-screen blur pulse on real workspace switches only (not tab/page navigation).
  - Expanded and collapsed workspace pickers with row action menus.
  - Inline rename flow in picker rows.
  - In-app delete confirmation modal (replaces browser `confirm`).
  - Active workspace highlighting refined (subtle inset ring, no clipping).
  - Nested popup behavior fixed in collapsed mode (workspace flyout remains stable when moving into action menu).
- Workspace state synchronization hardening:
  - Cross-hook sync event for workspace list updates (create/rename/delete) to prevent stale list drift between multiple `useWorkspaces()` consumers.
  - Delete edge case fixed: deleting the active workspace switches to a valid remaining workspace.
  - DELETE API client handling fixed for `204 No Content` responses.
- Layout consistency pass:
  - Learn, Flashcards, and Sentences now use consistent top-left title/subtitle structure.
  - Redundant in-page back buttons removed from Flashcards/Sentences (top-bar nav is canonical).
  - Right sidebar is no longer hidden on Settings.
- Modal/overlay rendering improvements:
  - Modal rendering portaled to `document.body` with corrected z-index layering for stacked popups and confirmations.

## 3) Validation Status

- Frontend TypeScript: passing.
- Frontend production build (`next build --no-lint`): passing.
- Backend workspace delete route integrated and working with keep-at-least-one guard.
- Main branch updated and pushed with workspace UX, layout consistency, and state-sync hardening.

## 4) Known Constraints (By Design)

- Domain-specific architecture is retained (no generic Notion-style block engine).
- Token infrastructure is intentionally thin for MVP+ (not full ranking/offline/analytics platform yet).


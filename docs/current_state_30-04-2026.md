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

Recent merged work introduced **word-atom flexibility (MVP+ thin)**:

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

## 3) Validation Status

- Frontend TypeScript: passing.
- Backend tests: passing (token tests included).
- Main branch updated and pushed with phased implementation + review/refactor hardening.

## 4) Known Constraints (By Design)

- Domain-specific architecture is retained (no generic Notion-style block engine).
- Token infrastructure is intentionally thin for MVP+ (not full ranking/offline/analytics platform yet).


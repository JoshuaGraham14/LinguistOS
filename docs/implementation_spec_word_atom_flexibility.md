# Implementation Spec: Word-Atom Flexibility + Global Clickable Tokens

> Status: Draft v0.1
> Branch: `feat/word-atom-flexibility-plan`
> Companion: [docs/product_direction.md](product_direction.md)
> Scope: planning-only spec for Notion-style flexibility adapted to LinguistOS domain constraints.

---

## 1. Scope

This spec defines a **domain-first flexibility upgrade** where the smallest atomic unit remains the **target-language word**. It intentionally avoids a generic Notion-like block engine.

Primary outcomes:

1. Every target-language token rendered in learning surfaces is hover-highlightable and clickable.
2. Click actions are context-aware:
   - Known word: open Word Home, practice, quick edit.
   - Unknown word: add to word bank quickly.
3. Occurrences of words are captured consistently so "forms seen" and "sentences seen" become reliable and extensible.
4. Client state is structured to avoid duplicated fetches and stale action state.

Out of scope:

- Replacing current relational schema with a universal `blocks` table.
- Collaborative realtime transaction engine.
- Generic page/document editor semantics.

### 1.1 MVP+ Thin Vertical Slice (updated scope)

For this release, we include a **thin but real** version of the platform-critical
items, not just UI-only primitives.

Mandatory in MVP+:

1. **Shared `AtomRef` contract across surfaces**
   - Canonical token reference shape used by rendering and actions.
2. **Tokenization + vocab-linking pipeline**
   - Deterministic known/unknown token spans for target-language text.
3. **Global `ClickableToken` primitive**
   - Unified hover/click/accessibility/action behavior for tokens.
4. **New backend token endpoints (thin)**
   - `POST /api/tokens/resolve`
   - `POST /api/tokens/action`
5. **Persistent occurrence model (thin)**
   - Add `word_occurrences` with minimal fields and append-only writes.
6. **Cross-surface rollout beyond core page**
   - Ship across top-priority surfaces, not only one page.
7. **Advanced disambiguation (thin)**
   - Multi-match chooser with user selection, no heavy ranking engine.
8. **Performance guardrails (thin)**
   - Memoization, request coalescing/debounce, and basic latency instrumentation.

Deferred beyond MVP+:

- Full confidence calibration pipelines
- Broad all-pages rollout with complete edge-case language handling
- Full analytics dashboards and offline sync complexity

---

## 2. Product Principles For This Phase

1. **Word stays atomic**: no abstraction should hide or weaken canonical `Vocab` identity.
2. **Composable in-domain only**: add flexibility for language-learning workflows, not arbitrary content modeling.
3. **One token interaction model**: all target-language token UI behavior must route through a shared renderer.
4. **Additive migrations only**: preserve existing APIs and data paths; extend without breaking current surfaces.
5. **Fast capture**: unknown token -> word bank should be one/two clicks, with optional enrichment later.

---

## 3. Target UX

### 3.1 Global token behavior

For supported learning surfaces (`sentences`, `dialogues`, `reading`, previews):

- Hover over target-language token -> highlight with known/unknown color treatment.
- Click token -> open action popover.

### 3.2 Popover actions

If token resolves to known vocab:

- Open Word Home
- Practice this word (flashcards/sentences)
- Quick actions (tag, note, mark known/unknown)

If token is unknown:

- Add to word bank (surface-form capture)
- Add with optional gloss
- Dismiss

### 3.3 Accessibility

- Token interactions must support keyboard focus + Enter/Space actions.
- Popover has ESC close + focus trap semantics.

---

## 4. Data/Model Plan (Additive)

### 4.1 Keep existing canonical models

Continue using current core entities:

- `Vocab`
- `Sentence`
- `SentenceWordLink`
- `WordMastery`

### 4.2 Add a portable occurrence concept (MVP+ thin)

Add an additive table to unify where a word appears across surfaces.

Proposed model: `word_occurrences`

- `id`
- `workspace_id`
- `vocab_id`
- `context_type` (`sentence`, `dialogue_line`, `generated_preview`, etc.)
- `context_id`
- `surface_token`
- `char_start` / `char_end` (or token index)
- `source` (`manual`, `llm`, `token_matcher`)
- `meta` (JSON)
- `created_at`

MVP+ thin requirements:

- Minimal index set only (optimize writes first; add read indexes incrementally).
- Append-only writes from token actions and sentence-link creation.
- Dedupe policy: `(workspace_id, vocab_id, context_type, context_id, surface_token, char_start)`.

This is the domain analogue of Notion's reusable relationship graph without
introducing generic blocks.

### 4.3 Preserve current sentence links

`SentenceWordLink` remains primary for sentence storage and integrity.

Occurrence table can be introduced in parallel and backfilled incrementally from sentence links.

---

## 5. API Plan

### 5.1 Token resolution endpoint (new, MVP+ thin)

`POST /api/tokens/resolve`

Input:

- `workspace_id`
- `language`
- raw `text` or token list
- optional context metadata

Output (minimum):

- token spans
- known/unknown status
- `vocab_id` when matched
- `confidence` (coarse float, optional)

MVP+ thin behavior:

- Deterministic tokenization and matching for target-language strings.
- No heavy morphological ranking engine required in this phase.

### 5.2 Token action endpoint (new, MVP+ thin)

`POST /api/tokens/action`

Actions (minimum):

- `open_word` (UI helper response)
- `add_to_vocab`
- `record_occurrence`

This keeps token flows explicit and testable instead of embedding logic ad hoc
in each page.

MVP+ thin behavior:

- `add_to_vocab` supports optional gloss and returns created/resolved vocab.
- `record_occurrence` writes append-only row to `word_occurrences`.
- `open_word` returns a normalized destination payload for UI routing.

### 5.3 Existing endpoints (no breaking changes)

- Keep `/api/vocab`, `/api/sentences`, `/api/vocab/{id}/mastery/*` unchanged.
- Only additive response fields where useful.

---

## 6. Frontend Architecture Plan

### 6.1 Shared token primitives

Add:

- `TokenizedText` renderer
- `ClickableToken` atom
- `WordActionPopover` component

All target-language text in scoped surfaces must go through `TokenizedText`.

Also define shared `AtomRef` shape:

```ts
type AtomRef = {
  vocabId?: number;
  surfaceToken: string;
  lemma?: string;
  language: string;
  sourceContext: {
    type: string;
    id?: number | string;
  };
};
```

### 6.2 State and data providers

Introduce provider-level state to avoid duplicated network fetches:

- `WorkspacesProvider`
- `VocabProvider`
- optional `TokenInteractionsProvider`

Rule: feature components consume provider data; utility components do not instantiate parallel `useVocab/useWorkspaces` trees.

### 6.3 Styling semantics

- Known token: brand/fuchsia accent
- Unknown token: amber accent
- Hover/focus styles consistent app-wide

---

## 7. Delivery Phases

### Phase A — Foundation (low risk)

- Add `TokenizedText`, `ClickableToken`, `WordActionPopover`
- Wire sentence practice + word home sentence list to shared renderer
- Add unknown-token quick-add flow
- Add provider-level integration where currently duplicated
- Define and adopt `AtomRef` contract in target surfaces

Success criteria:

- Selectionless token click add works in sentence practice.
- Known tokens open Word Home consistently.

### Phase B — Data reliability (MVP+ thin infra)

- Add token resolution endpoint
- Introduce `word_occurrences` model + API write path (thin, append-only)
- Persist occurrence context for token interactions
- Add token action endpoint (`add_to_vocab`, `open_word`, `record_occurrence`)

Success criteria:

- "Sentences seen" and "forms seen" remain consistent across edits and generated content.

### Phase C — Surface expansion + disambiguation

- Apply token renderer to additional pages (dialogue/reading/task text)
- Add keyboard interaction parity
- Add quick action telemetry
- Add thin multi-match disambiguation flow in popover
- Add performance guardrails (memoized tokenization + debounced resolve calls)

Success criteria:

- All scoped target-language text surfaces support identical hover/click behavior.

---

## 8. Testing Strategy

### Backend

- Unit tests for token resolution correctness (known/unknown/disambiguation)
- API tests for token action flows
- Regression tests for sentence link + occurrence consistency

### Frontend

- Component tests for token hover/focus/click states
- Integration tests for popover actions (known/unknown branches)
- E2E smoke: sentence page -> click unknown token -> add -> appears in vocab list and Word Home

---

## 9. Risks and Mitigations

1. **Over-generalization risk**
   - Mitigation: no generic block table in this phase; domain entities remain first-class.
2. **Tokenization ambiguity (morphology, punctuation, contractions)**
   - Mitigation: confidence scoring + user disambiguation in popover.
3. **Performance from tokenizing large texts on render**
   - Mitigation: memoized tokenization and server-assisted resolution for heavy surfaces.
4. **State divergence from duplicated hooks**
   - Mitigation: provider architecture as explicit prerequisite.

---

## 10. Definition of Done

This effort is done when:

1. Every target-language token in scoped surfaces is hover-highlightable and clickable.
2. Unknown tokens can be added to vocab from click flow without 422 or stale state issues.
3. Known tokens open consistent actions and Word Home navigation.
4. Sentence/occurrence evidence is persisted and visible in word-centric views.
5. Architecture remains domain-first and does not introduce generic block-engine complexity.

---

## 11. Phased TODO Checklist

### Phase A — Foundation

- [ ] Define `AtomRef` in shared frontend types.
- [ ] Implement `TokenizedText` renderer and `ClickableToken`.
- [ ] Implement `WordActionPopover` with known/unknown branches.
- [ ] Route sentence practice text through `TokenizedText`.
- [ ] Route Word Home sentence snippets through `TokenizedText`.
- [ ] Ensure unknown token quick-add works without page navigation.
- [ ] Ensure `WordChip`/quick-view interactions are consistent with token actions.

### Phase B — MVP+ Thin Infra

- [ ] Add backend schema for `word_occurrences` (additive migration only).
- [ ] Add `POST /api/tokens/resolve` (minimum payload/response contract).
- [ ] Add `POST /api/tokens/action` (`open_word`, `add_to_vocab`, `record_occurrence`).
- [ ] Persist occurrence writes from token actions.
- [ ] Backfill strategy defined from `SentenceWordLink` (can run post-release).
- [ ] Add regression tests for token endpoints and occurrence writes.

### Phase C — Expansion + Guardrails

- [ ] Expand token renderer to one additional high-traffic surface (dialogue or reading).
- [ ] Add thin disambiguation chooser for multi-match tokens.
- [ ] Add memoization/debounce guardrails for tokenization + resolve calls.
- [ ] Add minimal telemetry counters: click, add success, add failure, resolve latency.
- [ ] Add keyboard/focus accessibility QA pass for token interactions.

### Release Readiness Gate

- [ ] Unknown token -> add flow success rate acceptable in QA.
- [ ] Known token -> Word Home navigation/action flow stable.
- [ ] No duplicated/stale state from parallel workspace/vocab hook trees.
- [ ] Core API contracts documented and versioned in spec.


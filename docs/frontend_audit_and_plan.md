# Frontend Audit & Feature Plan

Date: 2026-04-28
Scope: `frontend/` (Next.js Learning Mode app)
Goal: capture what works, what's broken, and what to build next so the user-facing app is a credible demo surface for the dissertation pipeline (controlled candidate generation → linguistic validation → scoring).

---

## 0. Project context (so the plan makes sense)

LinguistOS is a dissertation project. The **thesis is the pipeline** — controlled morpho-syntactic sentence generation, candidate validation, and scoring across languages. The frontend is **a vehicle to show the pipeline doing useful work in a real learning loop**. Implications for what to build:

- Anything that makes the pipeline's contribution visible (constraint controls, candidate ranking, score breakdowns, evaluation feedback) is **on-thesis**.
- Anything that pulls the project toward "another flashcard SaaS" (auth, accounts, social, leaderboards, persistence infra) is **off-thesis**.
- Persistence stays in `localStorage`. Backend stays stateless. Spanish first.

Sidebar currently has 4 entries: Dashboard, Words, Learn, Settings. (The earlier "Games / Leaderboard / Duel / Surprise" placeholders are gone — fine.)

---

## 1. Audit — what's currently in the app

Verified by reading every file under `frontend/`, running `tsc --noEmit` (clean), and booting `next dev` (all 6 pages return 200, no runtime warnings).

### 1.1 Pages

| Route | File | Status |
|---|---|---|
| `/` Dashboard | [app/page.tsx](frontend/app/page.tsx) | renders, but several stats hardcoded |
| `/words` | [app/words/page.tsx](frontend/app/words/page.tsx) | works: add/edit/delete/import/search/tag filter/sort |
| `/learn` | [app/learn/page.tsx](frontend/app/learn/page.tsx) | works as a method picker; 2/4 tiles are "Coming soon" stubs |
| `/learn/flashcards` | [app/learn/flashcards/page.tsx](frontend/app/learn/flashcards/page.tsx) | works, but completion flow is buggy (see 1.3) |
| `/learn/sentences` | [app/learn/sentences/page.tsx](frontend/app/learn/sentences/page.tsx) | works in mock mode + when backend is up; UX has gaps |
| `/settings` | [app/settings/page.tsx](frontend/app/settings/page.tsx) | works; mirrors the popover |

### 1.2 Storage / API / types

- [lib/storage.ts](frontend/lib/storage.ts) — `useVocab`, `usePracticeSettings`, hydration-safe; ships a 100-word seed bank.
- [lib/api.ts](frontend/lib/api.ts) — `generateOrMock`. Falls back to a tiny hand-coded mock bank if the backend errors or returns no candidates.
- [lib/types.ts](frontend/lib/types.ts) — `VocabItem`, `PracticeSettings`, `SentenceCandidate`. Clean.

### 1.3 Bugs / half-finished behaviour found in the code

| # | Where | Issue |
|---|---|---|
| B1 | `flashcards/page.tsx:95,73-93` | **Completion flow is broken.** `atEnd = index >= total-1 && revealed`. As soon as the user hits "I Knew It" / "Didn't Know" on the last card, `handleNext` resets `revealed=false`, so `atEnd` flips back to `false` and the summary card disappears. In practice the summary almost never sticks — and there's no way to actually finish or restart the deck. |
| B2 | `flashcards/page.tsx` | No "Restart" / "Reshuffle" / "Start over" affordance. |
| B3 | `flashcards/page.tsx:54-59` | Timer starts on hydrate and never stops or resets between sessions. |
| B4 | `flashcards/page.tsx` | No keyboard shortcuts (Space to flip, ←/→ to navigate, J/K for known/unknown). Standard expectation for flashcards. |
| B5 | `flashcards/page.tsx:84-85` | "Didn't Know" only increments a transient counter; nothing persisted. "I Knew It" sets `learned: true` but there's no way to flip back to "unlearned" (toggle exists in storage but UI doesn't expose it here). |
| B6 | `app/page.tsx:48-49` | "Current Streak" is hardcoded to `0`, "Time Studied" hardcoded to `0m 31s`. Zero connection to actual usage. |
| B7 | `app/page.tsx:53-66` | "No word for today" card is static — never updates regardless of vocab state or sessions. |
| B8 | `app/page.tsx:31`, `Sidebar.tsx:60` | "Hello, Joshy G!" / "Joshy G — Beginner" hardcoded; no settable profile name even though the layout invites one. |
| B9 | `settings/page.tsx:85-95`, `SettingsPopover.tsx:88-99` | "Practice Mode" dropdown offers `multiple-choice` but no page implements it. The setting is dead. |
| B10 | `learn/sentences/page.tsx:258` | Dead code: `dir={pair.promptLanguage === "es" ? "ltr" : "ltr"}` — both branches are `ltr`. |
| B11 | `learn/sentences/page.tsx:121-132` | Every prev/next on a word triggers a fresh generation call. Going back to a word you just practiced loses its sentence and burns another OpenAI request. |
| B12 | `lib/api.ts:39-64` | `MOCK_BANK` only contains entries for `correr`, `olor`, `dulce`. The other 97 seed words fall through to a 2-line fallback bank — without the backend, demo mode is essentially the same two sentences repeated. |
| B13 | `learn/sentences/page.tsx` | After a correct answer there's no auto-advance and no clear "Next" button — the user has to find the chevron. |
| B14 | Words page | No way to mark/unmark `learned` from here. No filter by learned/unlearned. No bulk actions. No export. No "clear all". |
| B15 | None | No practice history is captured anywhere. Knew / didn't-know events are lost on refresh. The thesis explicitly calls out evaluation hooks (logging inputs/outputs); we have nowhere to log them. |
| B16 | `learn/sentences/page.tsx:101` | Always requests `num_candidates: 1`. The pipeline's whole point is to *rank candidates*; the UI never shows there's a ranking. |
| B17 | `learn/sentences/page.tsx` | Generation constraints (tense/person/number) are global. Practicing 30 words back-to-back at "3rd person singular present" is monotonous and pedagogically thin. |

Nothing else is broken — the surfaces that do exist render and behave; the gaps are around completeness and "doing the thesis-relevant thing."

---

## 2. Recommended work, ordered by priority

Each item has a rough size (S = <1h, M = a few hours, L = ≥half a day). Items are grouped by intent — fix what's broken, then improve UX, then pull in pipeline-showcase features.

### Tier 1 — Bug fixes (must) 

| ID | Task | Size | Notes |
|---|---|---|---|
| F1 | Fix flashcards completion flow (B1, B2). Track session state separately from `revealed`; show summary once the deck is exhausted; offer **Restart** + **Reshuffle**. | S | Simple state machine: `inProgress` → `done`. |
| F2 | Stop & reset flashcards timer on completion / restart (B3). | S | |
| F3 | Add keyboard shortcuts on flashcards (B4): Space = flip, ←/→ = prev/next, J = "didn't know", K = "knew it". | S | Plain `useEffect` listener. Improves feel a lot. |
| F4 | Remove dead code (B10), the unused multiple-choice option in settings *or* implement it (see UX2). | S | Easiest: hide the option until implemented. |
| F5 | Cache generated sentences per word for the session so prev/next doesn't regenerate (B11). | S | `Map<wordId, candidate>` in component state, optionally persisted to `sessionStorage`. |
| F6 | Drop the hardcoded streak / time / "no word for today" cards on the dashboard — replace with values that *can* be computed (B6, B7). If not computable yet, hide rather than fake. | S | |
| F7 | Make "Joshy G" a settable profile name (B8). One field on `/settings`, persisted to localStorage. | S | |

### Tier 2 — Core UX upgrades the user will actually feel (should)

| ID | Task | Size | Notes |
|---|---|---|---|
| UX1 | **Words page: learned filter + manual mark/unmark**, plus a count badge ("23 / 100 learned"). Surfaces the existing `learned` flag (B14). | S | |
| UX2 | **Multiple-choice mode for sentence practice** (or: remove it from settings). MC pulls 3 distractors from same-tag vocab. Implements the dead setting and gives a lower-friction practice mode. | M | |
| UX3 | **Auto-advance + clearer Next on sentence page** (B13). After "correct", short pause then advance; "incorrect" requires explicit click. | S | |
| UX4 | **Per-word sentence cache + "regenerate" button.** When the cache is good, prev returns instantly; when the user wants a different sentence they can ask for one. | S | Pairs with F5. |
| UX5 | **Vocabulary export** (CSV download mirroring the import format) and **clear-all** confirmation (B14). | S | |
| UX6 | **Session summary on sentence practice** (mirrors flashcards F1): X correct / Y skipped / Z hinted, with restart. | S | |
| UX7 | **Per-word "Practice this" deep-link** from the Words page → Flashcards or Sentences scoped to a single word. | S | URL param `?word=<id>` filters the deck. |
| UX8 | **Profile + study target on settings** (e.g. "20 min/day target"). Daily-streak math is honest the moment we have practice events to count. | S | |
| UX9 | **Better mock bank.** Either expand `MOCK_BANK` to cover the seed list, *or* drop the bank and just show "backend offline — start the API or set OPENAI_API_KEY" (B12). For thesis demos this matters: a no-backend reviewer sees a real learning loop, not the same fallback sentence twice. | S–M | I'd lean *expand*: ~3 sentences × 100 seed words ≈ 300 entries; cheap to write, even with an LLM. |

### Tier 3 — Pipeline-showcase features (would — these are the thesis-relevant ones)

The dissertation's specific contribution is *controlled* generation with *automatic validation and scoring*. The frontend currently hides all of that. These features make the pipeline visible to the user and to a thesis reviewer.

| ID | Task | Size | Notes |
|---|---|---|---|
| P1 | **Show ≥3 candidates per word with rank + score**, instead of always asking for 1 (B16). UI: the prompt is the top-ranked sentence; a small "see alternatives" affordance reveals the others, each with its score. Visually separates "what the model produced" from "what the pipeline picked." | M | Backend already supports `num_candidates`; default to 3. |
| P2 | **Score breakdown panel** on each candidate. Tooltip / expandable row showing the components from `docs/hybrid_system_spec.md` §6 (lemma match, tense, person, number, grammar errors). The pipeline already returns `features`; just render them. | M | Even when the score is fake/baseline, this scaffolding is what the dissertation evaluation hooks need. |
| P3 | **Per-card constraint randomisation toggle.** "Mix tenses / persons / numbers automatically" — when on, each generation call gets randomised constraints from a chosen subset (e.g. only past tenses). Solves B17 and produces more varied practice. | S–M | |
| P4 | **Practice log + "history" page.** Every knew/didn't-know on a flashcard, every correct/incorrect/skipped/hinted on a sentence, every regenerate, gets recorded with `{wordId, mode, settings, candidate, outcome, timestamp}` in localStorage. Persists across sessions, basis for streaks/time/progress, and is exactly the evaluation data the thesis wants. The Streamlit research dashboard (later) reads the same log. | M | This is the single highest-leverage thesis-aligned task on this list. |
| P5 | **"Was this sentence good?" thumbs up/down** on the sentence page, optionally with a reason chip ("not natural", "wrong tense", "wrong word"). Logged to the practice log. Cheap, high-value evaluation hook. | S | |
| P6 | **Pipeline-status pill** in the corner: "Backend: online / offline / mock". Already half-there via the `Demo mode` chip; promote it. Unambiguous for thesis demos. | S | |
| P7 | **Learning Mode dashboard widgets that *only* show real data**: words known, last session, candidate-quality histogram (from the practice log). Fixes the hardcoded stats *and* showcases pipeline-quality data. | M | Depends on P4. |

### Tier 4 — Stretch (could, only after the above)

| ID | Task | Size | Notes |
|---|---|---|---|
| S1 | Light SRS (Leitner box) for flashcards: reschedule next exposure based on knew/didn't-know. | M | Off-thesis but aligns with "real learning loop." |
| S2 | Verb-conjugation drill mode (the existing stub). Needs paradigm tables — could lean on the pipeline (`/api/conjugate` endpoint). | L | |
| S3 | TTS for Spanish prompts via the Web Speech API (no backend). | S | |
| S4 | Voice-practice page: ASR with Web Speech API, fuzzy-match against expected. | M | The "Voice Practice" tile is already a stub. |
| S5 | Theme toggle (the gradient bg is opinionated; many users want neutral). | S | |
| S6 | Hebrew-readiness flag in the data model (just plumb `language` into the UI so adding Hebrew later is a matter of adding words, not refactoring). | S | |

### Explicitly *not* on the list (off-thesis, per scope decisions)

- Auth, accounts, multi-user features.
- Server-side database, sync, sharing.
- Leaderboards, social, gamification beyond a personal streak.
- Mobile app shells.
- Replacing localStorage with anything more complex.

---

## 3. Suggested sequencing

A single coherent first iteration that ships the most user-facing benefit and unblocks the thesis-relevant work:

1. **F1–F7** — small bug-fix sweep, ~half a day. Result: every page does what it claims; nothing fake on the dashboard.
2. **P4** — the practice log. ~half a day. Once this exists, every later feature gets to read/write a single source of truth.
3. **UX1, UX3, UX5, UX6, UX7** — the "feels like a real app" pass. ~half a day.
4. **P1 + P2 + P5 + P6** — the "looks like a thesis demo" pass. ~one day. After this the user-facing app is genuinely showcasing the pipeline rather than hiding it.
5. **UX2, UX9, P3, P7** — round out the practice loop with multiple-choice, a real demo-mode, randomised constraints, and a dashboard backed by P4 data.
6. Anything from Tier 4 only as the thesis schedule allows.

---

## 4. Open questions to confirm before implementing

- **Streaks**: define a "study day" — any practice event in a calendar day (UTC? local?)? Confirm before P4/P7.
- **Mock bank**: keep + expand, or replace with an honest "offline" state? (UX9 — pick one.)
- **Practice Mode setting**: implement multiple-choice (UX2) or remove the option (F4)?
- **Profile name**: does anything else need to know the username (P5 reason chips? practice log entries)? If yes, plumb it through the log schema from day one.

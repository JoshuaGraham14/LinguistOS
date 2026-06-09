# Thesis claims — automatic evaluation (June 2026)

> Evidence from live GPT runs on `spanish_basic` and `spanish_challenging` via the
> research-mode evaluation pipeline (`research/`). Human ratings deferred.
> Full session context: [`eval_session_handoff.md`](eval_session_handoff.md).

---

## Claim 1 — The pipeline detects constraint violations that general grammar checkers miss

**Claim:** A multi-layer automatic evaluation stack is necessary for controlled generation.
`expected_form_match` catches pedagogical constraint failures that `grammar_languagetool`
passes, because internally coherent Spanish can still use the wrong person, tense, or
surface form.

**Evidence:**
- *vivir / future / 3rd / singular* on `spanish_basic` long: GPT produced
  *"Cuando termine mis estudios, **viviré**..."* (1st person) instead of **vivirá**
  (exp 14, 17 — 93% EF, 100% LT).
- LanguageTool scored **1.0** on those sentences; `expected_form_match` and prompt
  inspection caught the person slip.
- Same pattern on `spanish_challenging` long without explicit subject: infinitive
  (*me cuesta **dormir***) and periphrastic (*voy a **pedir***) forms pass LT but fail EF.

**Implication:** For a conjugation drill system, headline quality cannot be LT pass rate
alone; constraint-specific checking is required.

---

## Claim 2 — Sentence length is a valid, controllable generation parameter

**Claim:** GPT reliably produces sentences within requested token bands, and longer bands
produce more clausal structure — length functions as both a size and complexity control.

**Evidence (`spanish_basic` length grid, exps 12–17):**

| Length | Mean tokens (baseline) | Mean clauses (baseline) | `length_in_band` |
|--------|------------------------|-------------------------|------------------|
| short  | 2.8                    | 0.87                    | 100%             |
| medium | 6.3                    | 1.00                    | 100%             |
| long   | 13.2                   | 1.93                    | 100%             |

- LT grammar: **100%** across all six runs.
- EF slips only on long (93% — viviré case), not on short/medium.

**Implication:** The app can offer short / medium / long practice modes with reasonable
confidence in length compliance; long mode additionally increases syntactic complexity.

---

## Claim 3 — Batched vs individual generation trade-offs depend on sentence length

**Claim:** Method comparison is not one-dimensional. Batched generation (baseline) produces
more diverse output at short lengths; the diversity gap narrows at longer lengths where
individual calls have more room to vary phrasing.

**Evidence (`spanish_basic` length grid):**

| Length | baseline `self_bleu` | individual `self_bleu` | baseline `uniqueness` | individual `uniqueness` |
|--------|----------------------|------------------------|-------------------------|-------------------------|
| short  | 0.27                 | **0.80**               | 1.00                    | **0.60**                |
| medium | 0.13                 | 0.50                   | 1.00                    | 0.87                    |
| long   | 0.13                 | 0.37                   | 1.00                    | 1.00                    |

Default-length comparison (exps 9–10) shows the same direction: all five diversity metrics
separate methods (baseline more diverse).

**Implication:** Default to batched generation for short drill items; individual generation
is weakest exactly where single-item generation might be used.

---

## Claim 4 — Targeted prompt anchoring fixes constraint slips on complex morphology

**Claim:** Constraint failures on long, morphologically challenging sentences are often
prompt-engineering problems, not model incapacity. Requiring an explicit subject matching
person/number eliminates the dominant failure modes without changing the evaluation stack.

**Evidence (`spanish_challenging` long, 24 sentences per run):**

| Preset | EF pass | LT pass |
|--------|---------|---------|
| `baseline_long` (no hint, exp 22) | **71%** | 100% |
| `individual_long` (no hint, exp 21) | 83% | 100% |
| `baseline_long_explicit` (exp 23) | **100%** | 100% |
| `individual_long_explicit` (exp 24) | **100%** | 88% band |

Failures without hint clustered on:
- **dormir** — infinitive instead of *duermo*
- **pedir** — *voy a pedir* instead of *pido*
- **decir** — wrong form (*dijeron*, infinitive) instead of *dije*

With explicit subject (*Yo duermo…*, *Yo pido…*, *Yo dije…*): **100% EF** on all eight
constraint types for both methods.

**Implication:** Production prompts should anchor person with an overt subject (or pass
`expected_form` directly) when generating long practice items on irregular/challenging verbs.

---

## Claim 5 — spaCy verb morphology is diagnostic, not a headline metric

**Claim:** UD-based morph tagging (`verb_morphology`) systematically under-reports constraint
satisfaction on correct Spanish and should not gate generation or headline method comparison.

**Evidence:**
- Mock probe: 15/15 EF pass vs 10–11/15 VM pass across `es_core_news_sm/md/lg`.
- Live runs: VM pass rates 46–75% while EF pass rates 71–100% on the same sentences.
- Persistent VM failures on clearly correct forms (*Comimos pan.*, *Corro todas las mañanas.*).

**Implication:** Report `pass_rate::expected_form_match` as the headline constraint column;
keep `verb_morphology` in `details` for tool-reliability analysis only.

---

## Summary table (headline automatic results)

| Axis | Primary metric | Key finding |
|------|----------------|-------------|
| Constraint satisfaction | `expected_form_match` | 93–100% basic; 71% challenging long without hint → 100% with explicit subject |
| Grammar quality | `grammar_languagetool` | 100% across all reported live runs |
| Length compliance | `length_in_band` | 93–100%; mean tokens track bands |
| Syntactic complexity | `mean_clauses` | Monotonic increase short → long |
| Batch diversity | `self_bleu`, `uniqueness_ratio` | Baseline wins at short; gap closes at long |
| Tool reliability | `verb_morphology` vs EF | Systematic dissociation; EF is headline |

---

## Limitations (automatic evaluation only)

- Sample size: 3 sentences × 5–8 constraint sets per run (15–24 sentences).
- Single model (`gpt-5.4-nano`), single temperature (0.7).
- Mock fixtures do not reflect length bands — live data required for length evaluation.
- No human judgements of acceptability or pedagogical fit (deferred).
- `spanish_challenging` has no 3rd-singular constraint — vivir-style person slips tested on `spanish_basic` only.

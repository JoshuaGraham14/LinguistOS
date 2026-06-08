# Evaluation work — session handoff (June 2026)

> **For the next chat:** start here for context on research-mode sentence evaluation.
> Detailed plan: [`evaluation_metrics_implementation_plan.md`](evaluation_metrics_implementation_plan.md).
> spaCy evaluator notes: [`eval_verb_morphology_plan.md`](eval_verb_morphology_plan.md).

---

## Git state (as of push to `main`)

**`main`** is at `33f5f3d` on `origin/main` — clean, synced.

```
*   33f5f3d  Merge research/eval-verb-morphology: expected_form and verb_morphology evaluators.
|\  
| * 9c73e4a  parser disagreement diagnostics (expected_form candidate locator)
| * b211bff  verb_morphology + morph configs
| * 3797539  expected_form gold labels + expected_form_match
| * 34b3e53  evaluation metrics implementation plan
|/  
* 787ce57  (previous main)
```

**Feature branches** (still on remote; work is merged into `main`):

| Branch | Tip | Notes |
| --- | --- | --- |
| `research/eval-expected-form` | `3797539` | Fully contained in verb-morphology branch |
| `research/eval-verb-morphology` | `9c73e4a` | Superset of expected-form; use this or `main` for continued work |

**Branching pattern:** `research/*` feature branch → `--no-ff` merge to `main` with
`Merge research/<branch>: …` message (visible fork in history).

---

## What is implemented

### Data layer

- `expected_form` column on `ConstraintSet` (`research/db/models.py`)
- Gold labels on `research/benchmarks/spanish_basic.yaml` (comimos, vivirá, hablas, …)
- `reset_db()` in `research/db/database.py` for clean reloads
- Benchmark loader syncs `expected_form` on reload (`research/benchmarks/loader.py`)

### Evaluators (registered in `DEFAULT_EVALUATORS`)

| `name` | Role | File |
| --- | --- | --- |
| `expected_form_match` | **Primary constraint metric** — whole-token match on gold surface form | `sentence/expected_form.py` |
| `verb_morphology` | **Diagnostic only** — spaCy morph check + `parser_disagreement` in `details` | `sentence/verb_morphology.py` |
| `grammar_languagetool` | **Secondary grammar quality** — LanguageTool rule check (filtered categories) | `sentence/languagetool.py` |

### Distribution metrics (LT-related)

- `lt_error_breakdown` / `lt_error_breakdown_experiment` — category histogram from LT `details`
- Roll-ups: `pass_rate::grammar_languagetool` (EFSR), `errors_per_100w::grammar_languagetool`

### Benchmarks

- `spanish_basic` — evaluation benchmark (live + mock)
- `spanish_grammar_probe` — `mock_only: true` fixture for LT vs `expected_form_match` disagreement

### Morph configs

- `research/evaluation/morph_configs/es.yaml` — tense/person/number → UD features, `es_core_news_sm`
- `load_morph_config()` in `research/evaluation/morph_configs/__init__.py`

### Tests

- `research/tests/test_evaluation.py` — expected_form + verb_morphology (incl. spaCy quirk docs)
- `research/tests/test_morph_configs.py`
- `research/tests/test_evaluation.py` — expected_form, verb_morphology, grammar_languagetool
- **149+ tests** passing; run `python3 -m pytest research/tests/ -q`

### Mock data

- `research/fixtures/mock_outputs.py` — 15 Spanish sentences (3 per verb × 5 verbs)
- All 15 pass `expected_form_match`; ~10–11 pass `verb_morphology` depending on spaCy model

---

## Key decisions (do not re-litigate without reason)

1. **Headline constraint satisfaction = `expected_form_match`**, not spaCy morph tags.
   Generation goal is “use the word in *this* form”; gold surface form is the direct check.

2. **spaCy is not reliable enough for pass/fail** on Spanish mock outputs (~67–73% on
   correct sentences across `es_core_news_sm` / `md` / `lg`). Keep `verb_morphology` in
   the registry for tool-reliability analysis (`parser_disagreement` in `details`); do not
   use `pass_rate::verb_morphology` as the headline method-comparison column.

3. **Grammar quality = LanguageTool (Phase C).** Secondary metric, independent of spaCy.
   Not ground truth; catches agreement/concordance slips `expected_form_match` misses.
   Full pipeline mapping documented in plan (Stage 1 / 2a / 2b).

4. **Rejected for now:** `llm_morph_match`, paradigm lookup, Stanza as primary, bigger spaCy models as fix,
   LLM-only primary metric without human validation, `constraint_bundle`, `translation_pair`,
   `fluency_heuristic` (LLM outputs are already fluent-looking; heuristics don't catch
   grammar slips or unnatural phrasing).

---

## spaCy model probe (June 2026, 15 mock sentences)

| Model | `verb_morphology` pass | `expected_form_match` pass |
| --- | --- | --- |
| `es_core_news_sm` | 10/15 | 15/15 |
| `es_core_news_md` | 10/15 | 15/15 |
| `es_core_news_lg` | 11/15 | 15/15 |

Persistent failures: `Ayer comimos paella juntos`, `Corro todas las mañanas`; model-specific
errors on `Hablas español muy bien`, some `correr`/`hablar` sentences.

Install: `python3 -m spacy download es_core_news_sm` (see `research/README.md`).

---

## Next steps (recommended order)

1. **Run mock + live experiment** on `spanish_basic`; notebook pivots
   `pass_rate::expected_form_match` vs `pass_rate::verb_morphology`

2. **Phase B** — distribution metrics (`self_bleu`, `distinct_n`, …) for batched vs
   individual comparison

3. **Phase D** — human ratings for naturalness / acceptability (the only reliable check
   for "slightly off" or unnatural phrasing)

---

## Useful commands

```bash
# Tests
python3 -m pytest research/tests/ -q

# Mock experiment (from repo root)
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_default

# Reset research DB after benchmark schema changes
python3 -c "from research.db.database import reset_db; reset_db()"
```

---

## Files to read first in a new chat

- `research/evaluation/sentence/expected_form.py`
- `research/evaluation/sentence/verb_morphology.py`
- `research/evaluation/sentence/__init__.py` (registry)
- `research/benchmarks/spanish_basic.yaml`
- `docs/evaluation_metrics_implementation_plan.md`

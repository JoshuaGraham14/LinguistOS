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

### Distribution metrics (Stage 2b)

| `name` | Role | File |
| --- | --- | --- |
| `uniqueness_ratio` | Exact-string duplicate rate (higher = more diverse) | `distribution/uniqueness.py` |
| `self_bleu` | Mean sentence BLEU vs rest of batch (lower = more diverse) | `distribution/self_bleu.py` |
| `template_rate` | Share with same first-k-token prefix (higher = mode collapse) | `distribution/template_rate.py` |
| `distinct_1` / `distinct_2` | Unique unigrams / bigrams ÷ total (higher = more diverse) | `distribution/distinct_ngram.py` |
| `lt_error_breakdown` | LT category histogram | `distribution/lt_error_breakdown.py` |

Each diversity metric registers `constraint_set` and `_experiment` scopes (12 group-metric
instances total across 6 metric types). Shared tokenization: `distribution/tokens.py`
(strips `¿¡` and standard punctuation).

**Self-BLEU:** sacrebleu with `tokenize='intl'`, `smooth_method='exp'`,
`effective_order=True`; score stored on 0–1 scale. Batches with fewer than 2 sentences
return `0.0` with `details.skipped=true`.

**Template rate:** default `k=3`; sentences shorter than k use their full token list as prefix.

### Benchmarks

- `spanish_basic` — evaluation benchmark (live + mock)
- `spanish_challenging` — morphology live benchmark (stem-change, irregular preterite/conditional, orthographic)
- `spanish_grammar_probe` — `mock_only: true` fixture for LT vs `expected_form_match` disagreement

### Morph configs

- `research/evaluation/morph_configs/es.yaml` — tense/person/number → UD features, `es_core_news_sm`
- `load_morph_config()` in `research/evaluation/morph_configs/__init__.py`

### Tests

- `research/tests/test_evaluation.py` — expected_form, verb_morphology, grammar_languagetool
- `research/tests/test_group_metrics.py` — diversity metrics (repetitive / varied / near-duplicate batches)
- `research/tests/test_morph_configs.py`
- **165 tests** passing; run `python3 -m pytest research/tests/ -q`

### Mock data

- `research/fixtures/mock_outputs.py` — canned outputs for `spanish_basic`, `spanish_challenging`, `spanish_grammar_probe`
- `spanish_basic`: 15 sentences; all pass `expected_form_match`; ~10–11 pass `verb_morphology` depending on spaCy model
- Mock runs use identical canned data per benchmark regardless of method — diversity metrics only diverge on **live** output

### Analysis notebooks

- `research/explore_live_spanish_basic.ipynb` — method comparison pivot incl. diversity columns
- `research/explore_live_spanish_challenging.ipynb` — same for morphology benchmark

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

4. **Batch diversity = four complementary metrics.** Headline method-comparison columns are
   experiment-wide: `uniqueness_ratio_experiment`, `self_bleu_experiment`,
   `template_rate_experiment`, `distinct_1_experiment`, `distinct_2_experiment`. All should
   point the same direction (baseline more diverse than individual). Skipped: `length_cv`,
   parser batch diagnostics (`morph_failure_mode`, `parse_failure_rate`).

5. **Removed from scope:** `llm_morph_match`, `keyword_presence`, `alignment`, `fluency_heuristic`.
   Also deferred: parser batch diagnostics, Stanza-as-primary, bigger spaCy models as fix.

6. **Sentence length (Phase F):** bands are short 2–5, medium 5–9, long 10–16 tokens.
   New evaluators: `length_in_band`, `clause_count`. Grid: 6 live runs on `spanish_basic`
   (`baseline_{short,medium,long}` × `individual_{short,medium,long}`).
   Plan: [`eval_sentence_length_plan.md`](eval_sentence_length_plan.md).

---

## Live diversity validation (`spanish_basic`, June 2026)

Fresh live runs (experiments id=9 baseline, id=10 individual) — all five diversity metrics
separate methods as expected:

| Metric | `baseline_default` | `individual_default` |
| --- | --- | --- |
| `uniqueness_ratio_experiment` | 1.00 | 0.67 |
| `self_bleu_experiment` | 0.26 | 0.77 |
| `template_rate_experiment` | 0.00 | 0.80 |
| `distinct_1_experiment` | 0.70 | 0.47 |
| `distinct_2_experiment` | 0.91 | 0.51 |

Individual shows exact duplicates (`"Yo corro todos los días."` ×2, `"Él vivirá en Madrid."` ×2)
and shared openings (`template_rate` 0.67–1.0 per constraint set). Baseline keeps all strings
unique with varied openings. Stored DB values match direct recomputation.

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

1. ~~**Phase A** — constraint core + live analysis notebooks~~ **Done**

2. ~~**Phase B** — diversity metrics (`self_bleu`, `template_rate`, `distinct_1/2`)~~ **Done**

3. ~~**Phase F** — sentence length wiring + evaluators~~ **Done** (code + six method YAMLs).
   Run live 6-grid on `spanish_basic` to populate DB. Plan: [`eval_sentence_length_plan.md`](eval_sentence_length_plan.md).

4. **Phase D** — human ratings (acceptability, naturalness, pedagogical fit by length band)

---

## Useful commands

```bash
# Tests
python3 -m pytest research/tests/ -q

# Mock experiment (from repo root)
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_default

# Live method comparison (populates diversity metrics)
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_default --live
python3 -m research.run_experiment --benchmark spanish_basic --method individual_default --live

# Length grid (Phase F — after method configs exist)
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_short --live
python3 -m research.run_experiment --benchmark spanish_basic --method individual_long --live

# Reset research DB after benchmark schema changes
python3 -c "from research.db.database import reset_db; reset_db()"
```

---

## Deferred refactors (post-merge backlog)

### Shared live-analysis module (planned)

Extract duplicated notebook logic into `research/analysis/live_experiments.py`:

- `load_live_experiments(session, benchmark, method_names=None)`
- `metric_pivot(experiments, metrics)`
- `constraint_pass_table(experiment_id)`
- `disagreement_rows(experiment_id)`
- `length_grid_summary(benchmark)`

Then thin `explore_live_spanish_basic.ipynb` and `explore_live_spanish_challenging.ipynb`
to parameterised shells. **Status:** not started; challenging notebook still missing
experiments 22–24.

### Method loader YAML sync (deferred — not merge-blocking)

`load_method_config` is **insert-only**: after the first load, edits to a preset YAML
are ignored until `reset_db()`. This is a **footgun**, not a correctness bug — existing
experiments keep their stored `generation_meta`; only *new* runs are affected.

**When it bites:** you change `temperature` or `explicit_subject_required` in
`methods/baseline/long.yaml` and re-run `--method baseline_long` without resetting the DB.

**Workaround today:** `reset_db()` then re-run, or use a new preset `name`.

**Proper fix (later):** upsert `MethodConfig.config` when YAML content changes.

---

## Files to read first in a new chat

- `research/evaluation/sentence/expected_form.py`
- `research/evaluation/sentence/verb_morphology.py`
- `research/evaluation/distribution/__init__.py` (group metric registry)
- `research/evaluation/distribution/self_bleu.py`, `template_rate.py`, `distinct_ngram.py`
- `research/benchmarks/spanish_basic.yaml`
- `research/explore_live_spanish_basic.ipynb`
- `docs/evaluation_metrics_implementation_plan.md`
- `docs/eval_sentence_length_plan.md`
- `research/methods/README.md` (preset layout, `random` length)
- `research/methods/run_config.py` (`MethodRunConfig`)

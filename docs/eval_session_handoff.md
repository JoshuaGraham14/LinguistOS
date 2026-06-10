# Evaluation work — session handoff (June 2026)

> **For the next chat:** start here for context on research-mode sentence evaluation.
> Thesis claims (automatic only): [`eval_thesis_claims.md`](eval_thesis_claims.md).
> Detailed plan: [`evaluation_metrics_implementation_plan.md`](evaluation_metrics_implementation_plan.md).
> spaCy evaluator notes: [`eval_verb_morphology_plan.md`](eval_verb_morphology_plan.md).

---

## Git state (as of push to `main`)

**`main`** is at `baeb8d2` on `origin/main` — clean, synced.

```
*   baeb8d2  Merge research/eval-sentence-length: sentence length control and explicit-subject prompts.
|\  
| * 9f38f9f  simplify method presets (self-contained YAML in subfolders)
| * 6dca044  YAML extends, random length, MethodRunConfig, experiment naming
| * 6f13fd7  Phase F length evaluators + explicit-subject prompts
|/  
*   47582c9  Merge research/eval-diversity-metrics
```

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
| `length_in_band` | **Length compliance** — token count within band | `sentence/length_in_band.py` |
| `clause_count` | **Syntactic complexity** — normalised clause count (spaCy) | `sentence/clause_count.py` |

### Distribution metrics (Stage 2b)

| `name` | Role | File |
| --- | --- | --- |
| `uniqueness_ratio` | Exact-string duplicate rate (higher = more diverse) | `distribution/uniqueness.py` |
| `self_bleu` | Mean sentence BLEU vs rest of batch (lower = more diverse) | `distribution/self_bleu.py` |
| `template_rate` | Share with same first-k-token prefix (higher = mode collapse) | `distribution/template_rate.py` |
| `distinct_1` / `distinct_2` | Unique unigrams / bigrams ÷ total (higher = more diverse) | `distribution/distinct_ngram.py` |
| `mean_token_count` | Mean token count per batch | `distribution/mean_token_count.py` |
| `length_cv` | Coefficient of variation of token counts | `distribution/length_cv.py` |
| `mean_clauses` | Mean normalised clause score | `distribution/mean_clauses.py` |
| `lt_error_breakdown` | LT category histogram | `distribution/lt_error_breakdown.py` |

Diversity metrics: 12 group-metric instances (6 types × 2 scopes). Length metrics add 6 more
(3 types × 2 scopes). Total **54 group-metric rows** per full experiment on `spanish_basic`.

### Method presets

Self-contained YAML under `methods/baseline/` and `methods/individual/` (see
[`methods/README.md`](../research/methods/README.md)). CLI uses preset `name`:

- `baseline_{default,short,medium,long,random,long_explicit}`
- `individual_{default,short,medium,long,random,long_explicit}`

`MethodRunConfig` (`methods/run_config.py`) parses config; `random` draws a band per sample.

Experiment names: `{benchmark}__{preset_name}__{live|mock}` (e.g.
`spanish_challenging__baseline_long_explicit__live`).

### Generation prompts

Optional `explicit_subject_required: true` adds a person/number-specific subject hint
(e.g. *yo*, *él/ella*, *nosotros*) — see `generation/baseline_gpt.py`.

### Benchmarks

- `spanish_basic` — evaluation benchmark (live + mock)
- `spanish_challenging` — morphology live benchmark (stem-change, irregular preterite/conditional, orthographic)
- `spanish_grammar_probe` — `mock_only: true` fixture for LT vs `expected_form_match` disagreement

### Tests

**195 tests** passing; run `python3 -m pytest research/tests/ -q`

### Analysis notebooks

- `research/explore_live_spanish_basic.ipynb` — default comparison + §4 length grid (exps 12–17)
- `research/explore_live_spanish_challenging.ipynb` — default comparison + §4 long / explicit-subject (exps 22–24)

---

## Key decisions (do not re-litigate without reason)

1. **Headline constraint satisfaction = `expected_form_match`**, not spaCy morph tags.

2. **spaCy is diagnostic only** (~67–73% VM on mock sentences that are 100% EF). Report
   `pass_rate::verb_morphology` for tool-reliability analysis only.

3. **Grammar quality = LanguageTool.** 100% on all reported live runs; does not catch
   constraint-specific person/form slips when sentences are internally coherent.

4. **Batch diversity = four complementary metrics** at experiment scope.

5. **Sentence length bands:** short 2–5, medium 5–9, long 10–16 tokens; `random` draws per sample.

6. **Explicit-subject prompt anchoring** fixes long challenging EF (71% → 100%) without
   evaluator changes.

7. **Removed from scope:** `llm_morph_match`, `keyword_presence`, `alignment`, `fluency_heuristic`.

---

## Live experiment reference

### `spanish_basic`

| Exp | Preset | EF | Notes |
| --- | --- | --- | --- |
| 9 | `baseline_default` | 93% | Diversity baseline |
| 10 | `individual_default` | 100% | Diversity baseline |
| 12–17 | length grid | 93–100% | 6 runs: method × {short,medium,long} |
| 18–19 | `*_long_explicit` (early 3rd-sg-only hint) | 80–100% | Superseded by generalized hint |

### `spanish_challenging`

| Exp | Preset | EF | Notes |
| --- | --- | --- | --- |
| 5–6 | `*_default` | 100% | Early default-length runs |
| 20–22 | `baseline_long` | 71–79% | No explicit subject |
| 21 | `individual_long` | 83% | No explicit subject |
| 23 | `baseline_long_explicit` | **100%** | Generalized explicit subject |
| 24 | `individual_long_explicit` | **100%** | Generalized explicit subject |

---

## Completed phases

1. ~~**Phase A** — constraint core + live analysis notebooks~~ **Done**
2. ~~**Phase B** — diversity metrics~~ **Done**
3. ~~**Phase C** — LanguageTool grammar~~ **Done**
4. ~~**Phase F** — sentence length + clause metrics + live grids~~ **Done**
5. ~~**Explicit-subject prompts** — generalized person/number anchoring~~ **Done**

## Next steps

1. **Dissertation write-up** — use [`eval_thesis_claims.md`](eval_thesis_claims.md)
2. **Phase E — Hebrew** — see [`eval_hebrew_plan.md`](eval_hebrew_plan.md) (E0 spike → E1 benchmark + clitic matcher → E2 Stanza → E5 gendered prompts)
3. **Phase D** — human ratings (deferred)
4. **Shared analysis module** — extract notebook helpers (deferred; Hebrew plan folds this into E1/E5 via `research/analysis/live_experiments.py`)

---

## Useful commands

```bash
# Tests
python3 -m pytest research/tests/ -q

# Live method comparison
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_default --live
python3 -m research.run_experiment --benchmark spanish_basic --method individual_default --live

# Length grid
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_long --live

# Challenging + explicit subject
python3 -m research.run_experiment --benchmark spanish_challenging --method baseline_long_explicit --live

# Reset research DB after schema changes
python3 -c "from research.db.database import reset_db; reset_db()"
```

---

## Deferred refactors (post-merge backlog)

### Shared live-analysis module (planned)

Extract duplicated notebook logic into `research/analysis/live_experiments.py`.
**Status:** not started.

### Method loader YAML sync (deferred — not merge-blocking)

`load_method_config` is **insert-only**: YAML edits after first load are ignored until
`reset_db()`. Workaround: reset DB or use a new preset `name`.

---

## Files to read first in a new chat

- [`eval_thesis_claims.md`](eval_thesis_claims.md) — headline claims + evidence
- [`eval_hebrew_plan.md`](eval_hebrew_plan.md) — Phase E Hebrew implementation (if starting multilingual work)
- `research/evaluation/sentence/expected_form.py`
- `research/evaluation/distribution/__init__.py`
- `research/explore_live_spanish_basic.ipynb`
- `research/explore_live_spanish_challenging.ipynb`
- `research/methods/README.md`
- `docs/eval_sentence_length_plan.md`

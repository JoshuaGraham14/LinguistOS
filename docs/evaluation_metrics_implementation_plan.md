# Evaluation Metrics — Implementation Plan

> Build evaluators that answer the dissertation's core question: can we **reliably generate**
> vocabulary-in-context sentences that **satisfy explicit morpho-syntactic constraints**,
> and are those outputs **useful as a batch of practice items**?
>
> See also: [`research_mode_implementation_plan.md`](research_mode_implementation_plan.md) for
> pipeline and database design; [`thesis_description.md`](thesis_description.md) for research goals.

---

## Dissertation evaluation goals

The thesis evaluates controlled sentence generation along four axes:

| Axis | Question | Primary metric layer |
| --- | --- | --- |
| **Constraint satisfaction** | Does the output use the target word in the requested tense, person, and number? | Sentence evaluators |
| **Tool reliability** | How often do spaCy / Stanza / LanguageTool agree with human judgement? | Sentence `details` + distribution diagnostics |
| **Output quality** | Are sentences fluent and pedagogically suitable? | Sentence evaluators (+ human ratings) |
| **Batch usefulness** | Does a run produce varied, non-repetitive practice material? | Distribution metrics |

Where possible, combine **automatic evaluation** (this pipeline) with **human judgement**
(on a stratified sample) to validate automatic scores.

---

## Current state (May 2026)

### Implemented

| Component | Location | Status |
| --- | --- | --- |
| Sentence evaluator interface | `research/evaluation/sentence/base.py` | Done |
| `GrammarEvaluator` stub | `research/evaluation/sentence/grammar.py` | Stub (keyword stem + non-empty checks) |
| Distribution metric interface | `research/evaluation/distribution/base.py` | Done |
| `UniquenessRatioMetric` | `research/evaluation/distribution/uniqueness.py` | Done (constraint-set + experiment scopes) |
| Roll-ups | `research/evaluation/rollups.py` | Done (`mean::`, `min::`, `std::`, `pass_rate::`) |
| Registries | `sentence/__init__.py`, `distribution/__init__.py` | Done |
| Pipeline hooks | `research/pipeline.py` | Stage 1 → 2b → 2a |

### Not yet implemented

- Real morpho-syntactic parsing (spaCy / Stanza)
- LanguageTool integration
- Self-BLEU, distinct-n, template detection
- Human rating import
- Hebrew benchmark + evaluators
- Gold reference sentences for alignment metrics

---

## Evaluation granularity (recap)

Three layers already exist in the pipeline. This plan fills in **what to add** at each layer.

| Kind | What it measures | Code hook | Storage | Roll-up? |
| --- | --- | --- | --- | --- |
| **Per-sentence (Stage 1)** | One generated output | `BaseEvaluator.evaluate(...)` | `sentence_evaluations` | Yes → Stage 2a |
| **Distribution (Stage 2b)** | Whole batch jointly | `BaseGroupMetric.compute(...)` | `experiment_metrics` | No |
| **Roll-up (Stage 2a)** | Summary of sentence scores | `aggregate_sentence_eval_rollups()` | `experiment_metrics` | N/A (is the roll-up) |

**Rule:** Distribution metrics must not be derivable from a single sentence row (e.g. self-BLEU).
Roll-ups must not duplicate joint metrics (e.g. `pass_rate::constraint_bundle` vs a separate
`constraint_pass_rate` group metric — pick one source of truth).

Runner order when both enabled: **Stage 1 → Stage 2b → Stage 2a**.

---

## Sentence-level evaluators (Stage 1)

Each evaluator is one module under `research/evaluation/sentence/`, registered in
`DEFAULT_EVALUATORS`. Scores are floats in `[0, 1]` unless noted. Rich `details` JSON is
**required** for thesis error analysis and tool-reliability chapters.

### Shared conventions

**Inputs** (from `ConstraintSet.to_constraints_dict()`):

- `keyword`, `translation`, `tense`, `person`, `number`
- `target_language`, `cefr_level`
- `extra_constraints` (optional JSON)

**`details` schema** (recommended fields — omit when not applicable):

```json
{
  "tool": "spacy",
  "parse_ok": true,
  "expected": {"tense": "Past", "person": "1", "number": "Plur"},
  "observed": {"tense": "Past", "person": "1", "number": "Plur"},
  "token_index": 2,
  "matched_lemma": "comer",
  "checks": {"tense": true, "person": true, "number": true},
  "error": null
}
```

**Constraint value mapping:** YAML uses human-readable values (`past`, `1st`, `plural`).
Implement a single shared mapper (e.g. `research/evaluation/morph_mapping.py`) from
constraint dict → expected UD / spaCy morph features. All morphology evaluators use it.

**Pass semantics:** Composite evaluators may use partial credit (e.g. 2/3 morph features → 0.67).
Document the chosen scheme in each evaluator's module docstring. Default roll-up pass threshold
remains `0.5` (`DEFAULT_PASS_THRESHOLD` in `rollups.py`).

---

### Tier 1 — Core thesis (implement first)

These directly address morpho-syntactic control.

| Evaluator | Module (proposed) | `name` | What it checks | Implementation |
| --- | --- | --- | --- | --- |
| Keyword presence | `sentence/keyword.py` | `keyword_presence` | Target lemma appears in sentence | spaCy/Stanza lemma match on a token; fallback to normalized string only if parse fails |
| Verb morphology | `sentence/verb_morphology.py` | `verb_morphology` | Tense, person, number on constrained verb | Parse sentence; locate token whose lemma matches `keyword`; compare `Morph` features to mapped expected set |
| Constraint bundle | `sentence/constraint_bundle.py` | `constraint_bundle` | All hard constraints satisfied | AND of `keyword_presence` + `verb_morphology` (+ `extra_constraints` when present); score = fraction of sub-checks passed |
| Translation pair | `sentence/translation_pair.py` | `translation_pair` | Valid sentence–translation pair | Non-empty both sides; target ≠ translation string; optional script/language sanity check |

**Deprecating `grammar_stub`:** Keep during early development as a fast smoke test, or replace
with `translation_pair` + a no-parser `keyword_presence_heuristic`. Remove from
`DEFAULT_EVALUATORS` once Tier 1 evaluators are stable.

**Spanish first:** Use spaCy `es_core_news_sm` (or `md`). Add model to `research/requirements.txt`
and document download step in `research/README.md`.

---

### Tier 2 — Quality and tool reliability

| Evaluator | Module (proposed) | `name` | What it checks | Implementation |
| --- | --- | --- | --- | --- |
| LanguageTool grammar | `sentence/languagetool.py` | `grammar_languagetool` | Surface grammaticality | LanguageTool API on target sentence; score = 1 if no rule matches above severity threshold |
| Fluency heuristic | `sentence/fluency.py` | `fluency_heuristic` | Not degenerate / template-like | Token count bounds, type-token ratio, max repeated trigram within sentence |
| CEFR lexical | `sentence/cefr_lexical.py` | `cefr_lexical` | Vocabulary band | Only when `cefr_level` set; compare token frequencies against CEFR word list |
| Alignment | `sentence/alignment.py` | `alignment` | Translation quality | Phase 1: lexical overlap; Phase 2: COMET or BLEU vs gold reference if benchmark provides one |

**Tool disagreement logging:** When both `verb_morphology` and `grammar_languagetool` run,
store both verdicts in各自的 `details`. Notebook analysis can measure correlation and
disagreement rate — central to the "NLP tools are imperfect" thesis narrative.

---

### Tier 3 — Human-in-the-loop

| Evaluator | Module (proposed) | `name` | What it checks | Implementation |
| --- | --- | --- | --- | --- |
| Human rating | `sentence/human_rating.py` | `human_rating` | Acceptability | Import from CSV keyed by `sentence_id` or `(experiment_id, sample_index)`; no-op score if unrated |

Human evaluation protocol (to define before collection):

- Sample size: e.g. 50–100 sentences stratified by constraint set and method
- Scale: binary acceptable / unacceptable **or** Likert 1–5 (affects correlation analysis)
- Raters: at least one fluent speaker per target language

---

## Distribution-wide metrics (Stage 2b)

Each metric is one module under `research/evaluation/distribution/`, registered in
`DEFAULT_GROUP_METRICS`. Most metrics register **two instances**: `constraint_set` and
`experiment` scope (same pattern as `UniquenessRatioMetric`).

### Tier 1 — Diversity and method comparison

| Metric | Module (proposed) | `name` (constraint_set / experiment) | What it measures | Notes |
| --- | --- | --- | --- | --- |
| Uniqueness ratio | `uniqueness.py` | `uniqueness_ratio` / `uniqueness_ratio_experiment` | Distinct strings / N | **Done** |
| Self-BLEU | `self_bleu.py` | `self_bleu` / `self_bleu_experiment` | Mean BLEU of each sentence vs rest of batch | Lower = more diverse; key for batched vs individual GPT comparison |
| Distinct-n | `distinct_n.py` | `distinct_1` / `distinct_1_experiment` | Unique unigrams / total unigrams (tokenized) | Standard NLG diversity metric |
| Length CV | `length_cv.py` | `length_cv` / `length_cv_experiment` | Coefficient of variation of token counts | Flags uniform-length batches |
| Template rate | `template_rate.py` | `template_rate` / `template_rate_experiment` | Share sharing same first-k tokens | Detects mode collapse ("Yo como…" × N) |

---

### Tier 2 — Batch-level constraint diagnostics

These summarize failure **patterns** across a batch. Prefer computing from sentence
`details` where possible rather than re-parsing.

| Metric | Module (proposed) | `name` | What it measures | Notes |
| --- | --- | --- | --- | --- |
| Morph failure mode | `morph_failure_mode.py` | `morph_failure_mode` | Counts of tense vs person vs number mismatches | Reads `verb_morphology` eval `details` for the batch; `breakdown` JSON holds histogram |
| Parse failure rate | `parse_failure_rate.py` | `parse_failure_rate` / `_experiment` | Fraction where `parse_ok: false` | Tool reliability at batch level |
| All-fail keyword | `all_fail_keyword.py` | `all_fail_keyword` | 1.0 if every sample misses keyword | Flags broken runs |

**Overlap with roll-ups:** `pass_rate::constraint_bundle` per constraint set already measures
batch constraint satisfaction. Do **not** duplicate as a separate group metric unless the
group metric adds a non-redundant `breakdown` (e.g. failure-mode histogram).

---

## Roll-ups (Stage 2a) — no new code required

Once sentence evaluators exist, `aggregate_sentence_eval_rollups()` automatically produces:

| Metric name pattern | Meaning |
| --- | --- |
| `mean::<evaluator>` | Average score |
| `min::<evaluator>` | Worst sentence in batch |
| `std::<evaluator>` | Score spread |
| `pass_rate::<evaluator>` | Fraction ≥ 0.5 (configurable threshold) |

Scopes: per `constraint_set` and pooled `experiment`-wide (weighted by sentence count).

**Dissertation tables:** Compare methods via experiment-wide `pass_rate::constraint_bundle`,
`mean::verb_morphology`, and distribution metrics (`self_bleu_experiment`, etc.) in
`research/explore.ipynb`.

**Future roll-ups (optional):** median, p25/p75 — add to `rollups.py` only if needed for tables.

---

## Implementation phases

### Phase A — Spanish morphology core

**Goal:** Replace stub evaluation with real constraint checking.

1. Add `research/evaluation/morph_mapping.py` (YAML tense/person/number → UD features)
2. Add spaCy dependency + model download docs
3. Implement `keyword_presence`, `verb_morphology`, `constraint_bundle`, `translation_pair`
4. Unit tests with fixed sentences (correct + deliberate violations per constraint dimension)
5. Register in `DEFAULT_EVALUATORS`; keep or remove `grammar_stub`
6. Run mock + live experiments on `spanish_basic`; inspect `details` in notebook

**Done when:** `pass_rate::constraint_bundle` and per-set breakdowns are meaningful on live GPT output.

---

### Phase B — Distribution metrics for generation comparison

**Goal:** Quantify diversity differences between methods.

1. Implement `self_bleu` (constraint_set + experiment)
2. Implement `distinct_n` or `template_rate` (pick at least one beyond uniqueness)
3. Tests with known repetitive vs diverse fixture batches
4. Compare `baseline_default` vs `individual_default` in notebook

**Done when:** Experiment pivot shows distinct diversity signatures per method.

---

### Phase C — Tool reliability and quality layer

**Goal:** Support thesis claims about imperfect but usable NLP tooling.

1. Add `grammar_languagetool` (Spanish)
2. Add `fluency_heuristic`
3. Add distribution `parse_failure_rate` and `morph_failure_mode`
4. Optional: `cefr_lexical` when benchmarks include `cefr_level`

**Done when:** Notebook can report parser failure rate and LT vs morphology disagreement.

---

### Phase D — Human validation

**Goal:** Ground automatic metrics in human judgement.

1. Export sentence sample CSV from notebook
2. Implement `human_rating` import evaluator
3. Compute correlation (automatic vs human) in notebook
4. Write up agreement / disagreement patterns for dissertation

**Done when:** At least one table correlating `constraint_bundle` with human acceptability.

---

### Phase E — Multilingual (Hebrew)

**Goal:** Cross-language generalisability.

1. Hebrew benchmark YAML (morphologically rich constraint sets)
2. Stanza `he` pipeline for `verb_morphology` (spaCy Hebrew support may differ)
3. Re-run Phases A–C on Hebrew subset
4. Compare tool reliability Spanish vs Hebrew in notebook

**Done when:** Same evaluator interfaces, language-specific parser config, comparable metric columns.

---

## Evaluation matrix for dissertation chapters

| Chapter / claim | Sentence evaluators | Distribution metrics | Human |
| --- | --- | --- | --- |
| We can enforce morpho-syntax | `verb_morphology`, `constraint_bundle` | `morph_failure_mode` | Spot-check sample |
| Automatic tools are imperfect but usable | `grammar_languagetool` vs `verb_morphology` `details` | `parse_failure_rate` | Required subset |
| Batched vs individual generation differs | Roll-up `pass_rate::constraint_bundle` | `self_bleu`, `uniqueness_ratio`, `template_rate` | Optional |
| Spanish vs Hebrew | Same evaluators, different parser | Same metrics, per-language runs | Yes for Hebrew |

---

## Open decisions (resolve before Phase A coding)

| Decision | Options | Recommendation |
| --- | --- | --- |
| **Partial vs binary scoring** | Partial credit per morph feature vs strict all-or-nothing | Partial credit for analysis; report `pass_rate::` with threshold 1.0 as strict column in notebook |
| **Keyword matching** | Inflected form only vs any lemma inflection | Require **correct inflection** matching tense/person/number (matches constraint semantics) |
| **Human scale** | Binary vs Likert 1–5 | Likert for nuance; binary for inter-rater agreement (Cohen's κ) |
| **Gold references** | Hand-written per constraint set vs reference-free | Start reference-free; add optional `reference_sentence` field to benchmark YAML later for `alignment` |
| **Parser on failure** | Score 0 vs skip sentence | Score 0 with `parse_ok: false` in `details` (supports `parse_failure_rate`) |

---

## Adding a new evaluator or metric (checklist)

### Sentence evaluator

1. Create `research/evaluation/sentence/<name>.py` extending `BaseEvaluator`
2. Implement `name` property and `evaluate(sentence, translation, constraints)`
3. Return `EvaluationResult(score=..., details={...})`
4. Register instance in `DEFAULT_EVALUATORS` (`sentence/__init__.py`)
5. Add tests in `research/tests/test_evaluation.py`
6. Re-run experiment; confirm roll-ups appear as `mean::<name>`, etc.

### Distribution metric

1. Create `research/evaluation/distribution/<name>.py` extending `BaseGroupMetric`
2. Implement `name`, `scope`, and `compute(sentences)`
3. Register instance(s) in `DEFAULT_GROUP_METRICS` (`distribution/__init__.py`)
4. Add tests in `research/tests/test_group_metrics.py`
5. Confirm rows in `experiment_metrics` with correct `scope` and `constraint_set_id`

---

## Dependencies (anticipated)

| Package | Used by | Notes |
| --- | --- | --- |
| `spacy` + `es_core_news_sm` | Tier 1 Spanish evaluators | Pin version; document `python -m spacy download` |
| `stanza` | Hebrew (Phase E) | Separate model download |
| `language-tool-python` | `grammar_languagetool` | May need Java / remote API decision |
| `sacrebleu` or `nltk` | `self_bleu` | Prefer sacrebleu for consistency |
| `pandas` | Human rating import | Already used in notebook |

Add to `research/requirements.txt` incrementally per phase — avoid pulling all NLP deps for mock-only runs if optional imports are preferred.

---

## Data flow (evaluation-only)

```
generated_sentences
        |
        v
  [Stage 1: sentence evaluators]
        |
        v
 sentence_evaluations  ──────────────────>  [Stage 2a: roll-ups]  ──>  experiment_metrics
        |                                              (mean::, pass_rate::, ...)
        |
        +── details JSON ──>  [Stage 2b: distribution metrics]  ──>  experiment_metrics
                                    (self_bleu, morph_failure_mode, ...)
```

Analysis and dissertation figures: **`research/explore.ipynb`** (no separate `analysis.py`).

---

## Deliberately out of scope (for now)

- ML-learned scoring models
- RL from evaluation feedback
- Frontend / Streamlit wiring (`research/app.py` remains a stub)
- Alembic migrations for eval schema (JSON `details` is flexible)
- Median / percentile roll-ups (add if tables require them)

---

## Success criteria

The evaluation layer is **dissertation-ready** when:

1. **`constraint_bundle`** produces interpretable pass rates on live GPT runs across `spanish_basic`
2. **`details`** support error analysis (which constraint dimension fails most often)
3. **At least two distribution metrics** distinguish batched vs individual generation
4. **Human ratings** on a sample validate automatic constraint scores
5. **Notebook** can pivot experiment-wide metrics for method and language comparison

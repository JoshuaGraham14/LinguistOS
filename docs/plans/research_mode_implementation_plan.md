# Research Mode -- Implementation Plan

> Start with the baseline GPT generation that already works.
> Build each pipeline component around it, one at a time.
> The database grows with each phase -- only add tables when you need them.

---

## Current State (May 2026)

- Phases 1–6 complete
- 7 SQLite tables: `benchmarks`, `constraint_sets`, `method_configs`, `experiments`, `generated_sentences`, `sentence_evaluations`, `experiment_metrics`
- Benchmarks from YAML (`research/benchmarks/*.yaml`); method configs from YAML (`research/methods/*.yaml`)
- `Experiment` is a thin run record linking to a `Benchmark` and a `MethodConfig`
- Two generators: `BaselineGPTGenerator` (batched N in one call) and `IndividualGPTGenerator` (one call per sample)
- **Stage 1** — `BaseEvaluator` → `sentence_evaluations` (idempotent per experiment on re-run). **Stage 2b** — `BaseGroupMetric` → `experiment_metrics`. **Stage 2a** — `aggregate_sentence_eval_rollups()` → `experiment_metrics`.
- CLI: `python -m research.run_experiment` (`--benchmark`, `--method`, `--live`, `--no-eval`, `--no-metrics`). Orchestration: `research/pipeline.py` (`run_experiment()`). Mock data: `research/fixtures/mock_outputs.py`
- 97 unit tests (`research/tests`)
- `research/explore.ipynb` — interactive analysis over `research.db` (experiments, sentences, evals, metrics)
- Separate `research.db`, isolated from backend
- Roll-ups: `mean::`, `min::`, `std::`, `pass_rate::` per evaluator (constraint-set + experiment scope)

### Recent refactors

Structural improvements; behaviour for a normal CLI run is unchanged.

1. **`ConstraintSet.to_constraints_dict()`** — Evaluators receive constraint fields from one method on the model (keyword, tense, person, number, translation, target language, CEFR, and `extra_constraints` when set).

2. **`DEFAULT_EVALUATORS` registry** — Default sentence evaluators in `research/evaluation/sentence/__init__.py` (same pattern as generators and group metrics).

3. **Idempotent Stage 1** — `_evaluate_sentences` clears existing eval rows for the experiment’s sentences before insert, so re-runs do not duplicate scores or skew roll-ups.

4. **Pipeline split** — `research/pipeline.py` holds orchestration (`run_experiment`, stage helpers). `research/run_experiment.py` is CLI only. Mock sentences live in `research/fixtures/mock_outputs.py`.

---

## Evaluation granularity (per-sentence vs distribution vs roll-ups)


| Kind                                | What it measures                                                          | Code hook                                  | Storage                                                                    | Example metric names                                                 |
| ----------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| **Per-sentence (Level 1)**          | One generated sentence at a time                                          | `BaseEvaluator.evaluate(...)` + `ConstraintSet.to_constraints_dict()` | `**sentence_evaluations`** — one row per `(sentence_id, evaluator_name)` per eval pass; re-run replaces rows for that experiment | `grammar_stub`                                                       |
| **Distribution / joint (Level 2b)** | All samples in a batch together (per constraint set, or whole experiment) | `BaseGroupMetric.compute(list[sentences])` | `**experiment_metrics`** only (`scope` = `constraint_set` or `experiment`) | `uniqueness_ratio`, `self_bleu`, `template_rate`, `distinct_1`, `distinct_2`, `lt_error_breakdown` (+ `_experiment` scopes) |
| **Roll-up / aggregate (Level 2a)**  | Summary statistics **computed from** per-sentence rows                    | `aggregate_sentence_eval_rollups()`        | `**experiment_metrics`** (`metric_name` prefix `mean::`)                   | `mean::grammar_stub`                                                 |


Distribution metrics **never** write to `sentence_evaluations`. Roll-ups **only** run when Stage 1 has produced `sentence_evaluations` (same run: `evaluate=True`).

Runner order when both are enabled: Stage 1 → Stage 2b (group) → Stage 2a (roll-ups).

**Package layout:** `research/evaluation/sentence/` — `base.py` plus **one module per sentence evaluator** (e.g. `grammar.py`). `research/evaluation/distribution/` — `base.py` plus **one module per joint metric** (e.g. `uniqueness.py`); register metrics in `distribution/__init__.py` (`DEFAULT_GROUP_METRICS`). `research/evaluation/rollups.py` — Stage 2a roll-up aggregation (`aggregate_sentence_eval_rollups`).

---

## Generation Direction Principle

The generator always produces a **target language sentence** (e.g. Spanish) with a
**source language translation** (English) together in a single prompt. Both are
first-class outputs stored as a pair in `GeneratedSentence`.

The constraint set defines the target word and its grammatical constraints in the
target language. The source language keyword/translation is passed into the prompt
alongside it, but the sentence is designed and difficulty-calibrated for the
**target language**, not the source language.

Direction (English->Spanish or Spanish->English) is a **learning mode concern,
not a generation concern**. The same generated sentence pair serves both
directions -- the app decides which side to show first and which side is the
"answer." The generator does not need to know about direction.

The prompt and generator are **language-agnostic**: the target language is read
from the constraint set's `target_language` field and injected into the prompt, so
swapping to a new language (e.g. Hebrew) requires only new constraint sets, not
new generator code.

---

## Phase 1 -- Baseline Generation (DONE)

Take the existing GPT prompt from `backend/app/api/generate.py` and make it runnable as a standalone research script, outside of FastAPI.

**What was built:**

- `research/db/database.py` -- SQLAlchemy engine + session for `research/research.db`
- `research/db/models.py` -- 3 tables:
  - `constraint_sets` (keyword, tense, person, number)
  - `experiments` (name, method, status, config, timestamps)
  - `generated_sentences` (sentence, translation, sample_index) -- FK to experiment + constraint set
- `research/generation/baseline_gpt.py` -- prompt-building and parsing logic extracted from `backend/app/api/generate.py` as a plain function
- `research/run_experiment.py` -- CLI script that:
  1. Creates constraint sets (e.g. comer+past+1pl)
  2. Runs baseline GPT generation for each
  3. Stores the generated sentences in SQLite

**DB at this point:**

```
constraint_sets --< generated_sentences >-- experiments
```

---

## Phase 2 -- Evaluation (DONE)

Add the ability to score each generated sentence.

**What was built:**

- `research/db/models.py` -- added `SentenceEvaluation` table:
  - `sentence_evaluations` (evaluator_name, score, details JSON) -- FK to generated_sentence
  - Cascade-deletes when parent sentence is removed
  - `evaluations` relationship on `GeneratedSentence`
- `research/evaluation/sentence/base.py` -- shared `**BaseEvaluator`** + `**EvaluationResult**`
- `research/evaluation/sentence/grammar.py` -- `**GrammarEvaluator**` stub (keyword stem + non-empty checks)
- `run_experiment.py` updated:
  - `_evaluate_sentences()` runs all evaluators against every sentence in an experiment (idempotent: clears existing eval rows for that experiment first)
  - `DEFAULT_EVALUATORS` in `research/evaluation/sentence/__init__.py` (currently `[GrammarEvaluator()]`)
  - `--no-eval` skips Stage 1 only (group metrics + roll-ups unchanged unless `--no-metrics`)
  - `--no-metrics` skips group metrics and roll-ups (Phase 3)
  - Summary output shows per-sentence scores inline
- Tests for models, evaluators, and pipeline integration (extended further in Phase 3)

**Adding a new sentence evaluator:** Add `research/evaluation/sentence/<name>.py` with a class extending `BaseEvaluator` from `sentence/base.py`, then register an instance in `DEFAULT_EVALUATORS` in `research/evaluation/sentence/__init__.py`. One evaluator class per file keeps additions modular.

**Distribution metrics** (diversity, self-BLEU, etc.) do **not** use
`sentence_evaluations`; implement `**BaseGroupMetric`** from `research/evaluation/distribution/base.py` in a new module under `distribution/`, add it to `**DEFAULT_GROUP_METRICS**` in `research/evaluation/distribution/__init__.py`. Stored only in `**experiment_metrics**`.

**DB at this point:**

```
constraint_sets --< generated_sentences >-- experiments
                          |
                          v
                  sentence_evaluations
```

---

## Phase 3 -- Metrics and Aggregation (DONE)

`experiment_metrics` stores **two different metric families** (same table, distinguished by `metric_name` and `scope`):

1. **Distribution metrics** — joint over a multiset of outputs (`BaseGroupMetric`; **not** derivable from a single `sentence_evaluations` row).
2. **Roll-ups** — `mean::<evaluator>` summaries derived entirely from `**sentence_evaluations`** (`aggregate_sentence_eval_rollups`).

Persist roll-ups and distribution metrics as follows.

**What was built:**

- `research/db/models.py` — `experiment_metrics`:
  - `metric_name`, `value`, `scope` (`experiment` | `constraint_set`), nullable `constraint_set_id`, `breakdown` JSON
  - FK `experiment_id` CASCADE; optional FK `constraint_set_id` CASCADE
  - `Experiment.metrics` relationship
- `research/evaluation/rollups.py` — `aggregate_sentence_eval_rollups(session, experiment_id)`:
  - Inserts `mean::<evaluator_name>` rows per constraint set and one experiment-wide row per evaluator (weighted mean across all sentence evaluations)
- `research/evaluation/distribution/base.py` — `**BaseGroupMetric`**, `**GroupMetricResult**`
- `research/evaluation/distribution/uniqueness.py` — `**UniquenessRatioMetric**` stub (constraint-set + experiment-wide instances registered in `distribution/__init__.py` as `**DEFAULT_GROUP_METRICS**`)
- `run_experiment.py` — after Stage 1: `_compute_and_store_group_metrics()` (Stage 2b), then roll-ups when evaluations exist (Stage 2a); `--no-metrics` to skip both

**Done when:** After an experiment finishes, `experiment_metrics` holds roll-ups and group metrics queryable by `scope` and `metric_name`.

**DB at this point:**

```
constraint_sets --< generated_sentences >-- experiments
                          |                      |
                          |                      +---< experiment_metrics
                          v
                  sentence_evaluations
```

---

## Phase 4 -- Benchmarks (DONE)

Formalise constraint set groups so experiments are repeatable and comparable.

**What was built:**

- `research/db/models.py` — added `Benchmark` model (`name` UNIQUE, `language`, `description`):
  - `constraint_sets` now FK to `benchmarks` (CASCADE delete)
  - `experiments` has nullable `benchmark_id` FK (SET NULL on delete, nullable for pre-Phase-4 rows)
  - `Benchmark.constraint_sets` and `Benchmark.experiments` relationships
- `research/benchmarks/loader.py` — `load_benchmark(session, path)`:
  - Parses YAML, validates required fields, inserts `Benchmark` + `ConstraintSet` rows
  - Idempotent: returns existing benchmark if one with the same name already exists
  - Runnable as `python -m research.benchmarks.loader <path>`
- `research/benchmarks/spanish_basic.yaml` — starter benchmark (5 constraint sets: comer, vivir, hablar, escribir, correr)
- `run_experiment.py` updated:
  - `--benchmark <name>` required flag replaces hardcoded `PHASE1_CONSTRAINT_SETS` / `_ensure_constraint_sets`
  - `_resolve_benchmark()` loads YAML on first use, then cached in DB
  - Experiment name includes benchmark: `baseline_gpt_<benchmark>_<mode>`
  - Experiment record links to benchmark via `benchmark_id`
- `pyyaml>=6.0` added to `requirements.txt`
- Tests: `test_benchmarks.py` (10 tests — loading, idempotency, validation, CEFR pass-through, language override, real YAML smoke test); existing tests updated for new `benchmark_id` FK

**DB at this point:**

```
              benchmarks
             /          \
            v            v
   constraint_sets    experiments ──< experiment_metrics
            \           /
             v         v
         generated_sentences
                |
                v
        sentence_evaluations
```

---

## Phase 5 -- Generation Methods and Experiment Refactor (DONE)

Separated "what generation method + config" from "a specific run." `Experiment` no longer carries `method`, `samples_per_case`, or `config` — those moved to a new `MethodConfig` table. An experiment is now a thin run record pointing to both a benchmark and a method config.

**What was built:**

- `research/db/models.py` — added `MethodConfig` model (`name` UNIQUE, `method`, `samples_per_case`, `config` JSON):
  - `Experiment` slimmed to: `id`, `benchmark_id`, `method_config_id`, `name`, `status`, timestamps
  - `method_config_id` FK (SET NULL, nullable for backward compat)
- `research/generation/base.py` — `**BaseGenerator`** ABC (`name` property, `generate()` method)
- `research/generation/baseline_gpt.py` — added `**BaselineGPTGenerator**` class extending `BaseGenerator` (batched: asks for N candidates in one API call)
- `research/generation/individual_gpt.py` — `**IndividualGPTGenerator**` (one API call per sample, N calls total)
- `research/generation/__init__.py` — `**GENERATOR_REGISTRY**` mapping method names to classes
- `research/methods/loader.py` — `load_method_config(session, path)` with validation and skip-if-exists idempotency
- `research/methods/baseline_default.yaml` — baseline config (batched, 3 samples, gpt-4o, temp 0.7)
- `research/methods/individual_default.yaml` — individual config (per-sample, 3 samples, gpt-4o, temp 0.7)
- `run_experiment.py` updated:
  - `--method <name>` required flag (replaces `--samples`); `--benchmark` still required
  - `_resolve_method_config()` + `_build_generator()` look up method config and instantiate the generator from the registry
  - `Experiment` links to both benchmark and method config
- Tests: `test_generation.py` (17 tests — ABC, generators, registry, method config loader, validation, YAML smoke tests); existing tests updated for `MethodConfig` FK

**DB at this point:**

```
              benchmarks         method_configs
             /          \           /
            v            v         v
   constraint_sets      experiments ──< experiment_metrics
            \              /
             v            v
         generated_sentences
                |
                v
        sentence_evaluations
```

---

## Phase 6 -- Richer roll-ups (DONE)

Extend what gets stored automatically after each run. **Comparison and exploration stay in `research/explore.ipynb`** — no dedicated `analysis.py` or `--compare` CLI.

**What was built:**

- `research/evaluation/rollups.py` — roll-ups beyond mean:
  - `min::<evaluator>`, `std::<evaluator>`, `pass_rate::<evaluator>` (default threshold 0.5)
  - Same `scope` / `metric_name` pattern as `mean::`; idempotent delete of all rollup prefixes before insert
- `run_experiment.py` unchanged hook (still calls `aggregate_sentence_eval_rollups` after sentence eval)
- Tests: extended `test_analysis.py` (+2 tests); integration test counts updated
- `explore.ipynb` / `explore_live_spanish_*.ipynb` — experiments table uses `MethodConfig` / `Benchmark`; **Compare experiments** pivot of experiment-wide metrics including roll-ups and diversity columns (`uniqueness_ratio_experiment`, `self_bleu_experiment`, `template_rate_experiment`, `distinct_1_experiment`, `distinct_2_experiment`)

**Deliberately not built:** `analysis.py`, `--compare` CLI, median/percentiles (can add later if needed for dissertation tables).

**Done when:** After a run, `experiment_metrics` includes mean, min, std, and pass-rate per evaluator (per constraint set and experiment-wide). Compare experiments in the notebook via experiment-wide metric pivot.

---

## What is deliberately left out

- No frontend (Streamlit stub in `research/app.py` only; not wired to the pipeline)
- No real grammar evaluation yet (stubs only -- spaCy/Stanza comes later)
- No Alembic migrations (`create_all` is fine during research iteration)

---

## Data Flow

```
[benchmarks] YAML → Loader → DB          [method_configs] YAML → Loader → DB
     |                                           |
     └→ Constraint Sets ──┐      ┌── Generator ←─┘
                          v      v
                    [generated_sentences]
                              |
    Stage 1: per-sentence ────┴──→ [sentence_evaluations]  ← sentence/BaseEvaluator
                              |
    Stage 2b: joint batch ────┼──→ [experiment_metrics]     ← distribution/BaseGroupMetric
                              |
    Stage 2a: from Stage 1 ───┘→  [experiment_metrics]      ← mean::<evaluator> roll-ups
```

Each `[bracket]` is a database table. Tables are added phase by phase, not all at once.
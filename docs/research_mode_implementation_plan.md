# Research Mode -- Implementation Plan

> Start with the baseline GPT generation that already works.
> Build each pipeline component around it, one at a time.
> The database grows with each phase -- only add tables when you need them.

---

## Current State (14 May 2026)

- Phases 1–4 complete and merged to **main**
- 6 SQLite tables: `benchmarks`, `constraint_sets`, `experiments`, `generated_sentences`, `sentence_evaluations`, `experiment_metrics`
- Benchmarks loaded from YAML (`research/benchmarks/*.yaml`); constraint sets and experiments FK to benchmark
- **Stage 1** — `BaseEvaluator` → `sentence_evaluations`. **Stage 2b** — `BaseGroupMetric` → `experiment_metrics` (per constraint set + optional experiment-wide). **Stage 2a** — `aggregate_sentence_eval_rollups()` → `experiment_metrics` (`mean::<evaluator>` rows).
- Runner: `--benchmark <name>` (required), `--live`, `--samples`, `--no-eval`, `--no-metrics`
- 72 unit tests (research/tests)
- Separate `research.db`, isolated from backend

---

## Evaluation granularity (per-sentence vs distribution vs roll-ups)

| Kind | What it measures | Code hook | Storage | Example metric names |
| --- | --- | --- | --- | --- |
| **Per-sentence (Level 1)** | One generated sentence at a time | `BaseEvaluator.evaluate(...)` | **`sentence_evaluations`** — one row per `(sentence_id, evaluator_name)` | `grammar_stub` |
| **Distribution / joint (Level 2b)** | All samples in a batch together (per constraint set, or whole experiment) | `BaseGroupMetric.compute(list[sentences])` | **`experiment_metrics`** only (`scope` = `constraint_set` or `experiment`) | `uniqueness_ratio`, `uniqueness_ratio_experiment`; future: self-BLEU |
| **Roll-up / aggregate (Level 2a)** | Summary statistics **computed from** per-sentence rows | `aggregate_sentence_eval_rollups()` | **`experiment_metrics`** (`metric_name` prefix `mean::`) | `mean::grammar_stub` |

Distribution metrics **never** write to `sentence_evaluations`. Roll-ups **only** run when Stage 1 has produced `sentence_evaluations` (same run: `evaluate=True`).

Runner order when both are enabled: Stage 1 → Stage 2b (group) → Stage 2a (roll-ups).

**Package layout:** ``research/evaluation/sentence/`` — ``base.py`` plus **one module per sentence evaluator** (e.g. ``grammar.py``). ``research/evaluation/distribution/`` — ``base.py`` plus **one module per joint metric** (e.g. ``uniqueness.py``); register metrics in ``distribution/__init__.py`` (``DEFAULT_GROUP_METRICS``). ``research/evaluation/rollups.py`` — Stage 2a roll-up aggregation (``aggregate_sentence_eval_rollups``).

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
- `research/evaluation/sentence/base.py` -- shared **`BaseEvaluator`** + **`EvaluationResult`**
- `research/evaluation/sentence/grammar.py` -- **`GrammarEvaluator`** stub (keyword stem + non-empty checks)
- `run_experiment.py` updated:
  - `_evaluate_sentences()` runs all evaluators against every sentence in an experiment
  - `DEFAULT_EVALUATORS` list (currently `[GrammarEvaluator()]`)
  - `--no-eval` skips Stage 1 only (group metrics + roll-ups unchanged unless `--no-metrics`)
  - `--no-metrics` skips group metrics and roll-ups (Phase 3)
  - Summary output shows per-sentence scores inline
- Tests for models, evaluators, and pipeline integration (extended further in Phase 3)

**Adding a new sentence evaluator:** Add ``research/evaluation/sentence/<name>.py`` with a class extending ``BaseEvaluator`` from ``sentence/base.py``, then register an instance in ``DEFAULT_EVALUATORS`` in ``run_experiment.py``. One evaluator class per file keeps additions modular.

**Distribution metrics** (diversity, self-BLEU, etc.) do **not** use
`sentence_evaluations`; implement **`BaseGroupMetric`** from ``research/evaluation/distribution/base.py`` in a new module under ``distribution/``, add it to **`DEFAULT_GROUP_METRICS`** in ``research/evaluation/distribution/__init__.py``. Stored only in **`experiment_metrics`**.

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
2. **Roll-ups** — `mean::<evaluator>` summaries derived entirely from **`sentence_evaluations`** (`aggregate_sentence_eval_rollups`).

Persist roll-ups and distribution metrics as follows.

**What was built:**
- `research/db/models.py` — `experiment_metrics`:
  - `metric_name`, `value`, `scope` (`experiment` | `constraint_set`), nullable `constraint_set_id`, `breakdown` JSON
  - FK `experiment_id` CASCADE; optional FK `constraint_set_id` CASCADE
  - `Experiment.metrics` relationship
- `research/evaluation/rollups.py` — `aggregate_sentence_eval_rollups(session, experiment_id)`:
  - Inserts `mean::<evaluator_name>` rows per constraint set and one experiment-wide row per evaluator (weighted mean across all sentence evaluations)
- `research/evaluation/distribution/base.py` — **`BaseGroupMetric`**, **`GroupMetricResult`**
- `research/evaluation/distribution/uniqueness.py` — **`UniquenessRatioMetric`** stub (constraint-set + experiment-wide instances registered in ``distribution/__init__.py`` as **`DEFAULT_GROUP_METRICS`**)
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

## Phase 5 -- Experiment Comparison

Query and compare results across multiple experiments.

**What to build:**
- Extend `research/evaluation/rollups.py` with additional aggregate functions beyond mean:
  - `min::<evaluator>` — worst-case output quality per evaluator
  - `std::<evaluator>` — consistency / variance of scores
  - `pass_rate::<evaluator>` — fraction of sentences above a configurable threshold (useful for binary/near-binary evaluators like grammar, tense accuracy)
  - Median and percentiles (p5, p25) as optional extras for dissertation analysis
  - All aggregates write to `experiment_metrics` with no schema changes needed
- Create `research/analysis.py` with query/comparison helpers (roll-up logic lives in `research/evaluation/rollups.py`):
  - `compare_experiments([id1, id2])` -- side-by-side metric tables
  - `get_sentences_for_constraint(experiment_id, constraint_set_id)` -- drill into individual outputs
  - `get_failure_analysis(experiment_id, evaluator)` -- sentences below a score threshold
- `research/run_experiment.py` gets a `--compare` mode that prints comparison output

**Done when:** You can run two experiments with different configs, see richer per-evaluator summaries (mean, min, std, pass-rate), and compare them side-by-side in the terminal.

---

## Phase 6 -- Second Generation Method

Add a new generator to compare against the baseline.

**What to build:**
- `research/generation/base.py` -- `BaseGenerator` abstract class (extracted from baseline)
- Refactor `baseline_gpt.py` to extend `BaseGenerator`
- `research/generation/[new_method].py` -- a second generation approach (e.g. constrained prompt, few-shot, or different model)
- Experiment config YAML so you can specify which generator to use:

```yaml
name: constrained_v1
method: constrained_gpt
samples_per_case: 5
generation:
  model: gpt-4o
  temperature: 0.7
```

**Done when:** You run the same benchmark with two different generators and compare their metrics.

---

## What is deliberately left out

- No frontend (Streamlit or otherwise)
- No real grammar evaluation yet (stubs only -- spaCy/Stanza comes later)
- No Alembic migrations (`create_all` is fine during research iteration)
- Generator ABC is deferred to Phase 6 -- baseline works as a plain function until then

---

## Data Flow

```
[benchmarks] YAML → Loader → DB
     |
     └→ Constraint Sets → Generator → [generated_sentences]
                                            |
          Stage 1: per-sentence only ───────┴──→ [sentence_evaluations]  ← sentence/BaseEvaluator
                                            |
          Stage 2b: joint batch ────────────┼──→ [experiment_metrics] ← distribution/BaseGroupMetric
                                            |
          Stage 2a: from Stage 1 only ──────┘→ [experiment_metrics] ← mean::<evaluator> roll-ups
```

Each `[bracket]` is a database table. Tables are added phase by phase, not all at once.

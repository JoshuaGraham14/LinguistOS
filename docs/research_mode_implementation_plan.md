# Research Mode -- Implementation Plan

> Start with the baseline GPT generation that already works.
> Build each pipeline component around it, one at a time.
> The database grows with each phase -- only add tables when you need them.

---

## Current State (13 May 2026)

- Phase 1 complete and merged to main
- Phase 2 complete (per-sentence evaluation); merged to **main**
- Phase 3 complete on **`research/pipeline-phase-3`**: `experiment_metrics`, roll-ups, distribution metrics
- 5 SQLite tables: `constraint_sets`, `experiments`, `generated_sentences`, `sentence_evaluations`, `experiment_metrics`
- **Stage 1** — `BaseEvaluator` → `sentence_evaluations`. **Stage 2b** — `BaseGroupMetric` → `experiment_metrics` (per constraint set + optional experiment-wide). **Stage 2a** — `aggregate_sentence_eval_rollups()` → `experiment_metrics` (`mean::<evaluator>` rows).
- Mock/live runner: `--no-eval` skips Stage 1 only; `--no-metrics` skips Stage 2a+2b
- 61 unit tests (research/tests)
- Separate `research.db`, isolated from backend

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
from the constraint set's `language` field and injected into the prompt, so
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
- `research/evaluation/base.py` -- `BaseEvaluator` ABC with `name` property + `evaluate(sentence, translation, constraints) -> EvaluationResult`
- `research/evaluation/grammar.py` -- `GrammarEvaluator` stub that checks keyword stem presence, non-empty sentence, and non-empty translation (3 heuristic checks → score 0.0–1.0)
- `run_experiment.py` updated:
  - `_evaluate_sentences()` runs all evaluators against every sentence in an experiment
  - `DEFAULT_EVALUATORS` list (currently `[GrammarEvaluator()]`)
  - `--no-eval` skips Stage 1 only (group metrics + roll-ups unchanged unless `--no-metrics`)
  - `--no-metrics` skips group metrics and roll-ups (Phase 3)
  - Summary output shows per-sentence scores inline
- Tests for models, evaluators, and pipeline integration (extended further in Phase 3)

**Adding a new evaluator:** Create a class extending `BaseEvaluator` in
`research/evaluation/`, implement `name` and `evaluate()`, then add an instance
to `DEFAULT_EVALUATORS` in `run_experiment.py`. No schema change.

**Distribution metrics** (diversity, self-BLEU, etc.) do **not** use
`sentence_evaluations`; they extend `BaseGroupMetric` in
`research/evaluation/group.py`, register in `DEFAULT_GROUP_METRICS`, and write only to **`experiment_metrics`** (Phase 3).

**DB at this point:**

```
constraint_sets --< generated_sentences >-- experiments
                          |
                          v
                  sentence_evaluations
```

---

## Phase 3 -- Metrics and Aggregation (DONE)

Persist **roll-up** metrics (derived from per-sentence evaluations) and **distribution** metrics (joint over sample batches) in `experiment_metrics`.

**What was built:**
- `research/db/models.py` — `experiment_metrics`:
  - `metric_name`, `value`, `scope` (`experiment` | `constraint_set`), nullable `constraint_set_id`, `breakdown` JSON
  - FK `experiment_id` CASCADE; optional FK `constraint_set_id` CASCADE
  - `Experiment.metrics` relationship
- `research/analysis.py` — `aggregate_sentence_eval_rollups(session, experiment_id)`:
  - Inserts `mean::<evaluator_name>` rows per constraint set and one experiment-wide row per evaluator (weighted mean across all sentence evaluations)
- `research/evaluation/group.py` — `BaseGroupMetric`, `GroupMetricResult`, `UniquenessRatioMetric` stub (constraint-set + experiment-wide instances), `DEFAULT_GROUP_METRICS`
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

## Phase 4 -- Benchmarks

Formalise constraint set groups so experiments are repeatable and comparable.

**What to build:**
- `research/db/models.py` -- add 1 table:
  - `benchmarks` (name, language, description) -- constraint_sets now FK to benchmark
- `research/benchmarks/loader.py` -- reads a YAML file, inserts Benchmark + ConstraintSet rows
- `research/benchmarks/spanish_basic.yaml` -- starter benchmark (5-10 constraint sets)
- Update `run_experiment.py` to accept `--benchmark` flag instead of hardcoded constraint sets

**Done when:** You load a benchmark from YAML, run an experiment against it, and the experiment record links back to the benchmark.

**DB at this point (final schema):**

```
benchmarks --< constraint_sets --< generated_sentences >-- experiments
                                          |                      |
                                          v                      v
                                  sentence_evaluations    experiment_metrics
```

---

## Phase 5 -- Experiment Comparison

Query and compare results across multiple experiments.

**What to build:**
- Extend `research/analysis.py` with:
  - `compare_experiments([id1, id2])` -- side-by-side metric tables
  - `get_sentences_for_constraint(experiment_id, constraint_set_id)` -- drill into individual outputs
  - `get_failure_analysis(experiment_id, evaluator)` -- sentences below a score threshold
- `research/run_experiment.py` gets a `--compare` mode that prints comparison output

**Done when:** You can run two experiments with different configs and see a comparison printed to the terminal.

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
Constraint Sets → Generator → [generated_sentences]
                                    |
              Stage 1 per-sample ───┴──→ [sentence_evaluations]
                                    |
              Stage 2a roll-ups ────┼──→ [experiment_metrics]
              Stage 2b group-only ──┘         (mean::* + uniqueness_ratio*)
```

Each `[bracket]` is a database table. Tables are added phase by phase, not all at once.

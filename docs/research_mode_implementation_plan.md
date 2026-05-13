# Research Mode -- Implementation Plan

> Start with the baseline GPT generation that already works.
> Build each pipeline component around it, one at a time.
> The database grows with each phase -- only add tables when you need them.

---

## Current State (13 May 2026)

- Phase 1 complete and merged to main
- Phase 2 complete (evaluation framework)
- 4 SQLite tables: `constraint_sets`, `experiments`, `generated_sentences`, `sentence_evaluations`
- Baseline GPT generator extracted from backend, language-agnostic with optional CEFR level
- Evaluation framework: `BaseEvaluator` ABC + `GrammarEvaluator` stub
- Mock and live experiment runner via CLI (`python -m research.run_experiment`)
- 52 unit tests passing (models, generator, evaluators, pipeline integration)
- Separate `research.db` database, isolated from user-facing backend

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
  - `--no-eval` CLI flag to skip evaluation
  - Summary output now shows per-sentence scores inline
- 22 new tests (5 model, 14 evaluator, 3 integration)

**Adding a new evaluator:** Create a class extending `BaseEvaluator` in
`research/evaluation/`, implement `name` and `evaluate()`, then add an instance
to `DEFAULT_EVALUATORS` in `run_experiment.py`. No schema or pipeline changes needed.

**DB at this point:**

```
constraint_sets --< generated_sentences >-- experiments
                          |
                          v
                  sentence_evaluations
```

---

## Phase 3 -- Metrics and Aggregation

Aggregate per-sentence scores into experiment-level metrics.

**What to build:**
- `research/db/models.py` -- add 1 table:
  - `experiment_metrics` (metric_name, value, breakdown) -- FK to experiment
- `research/analysis.py` -- functions that compute and store aggregate metrics:
  - mean score per evaluator across all sentences in an experiment
  - per-constraint-set breakdown
- Update `run_experiment.py` to call aggregation after evaluation

**Done when:** After an experiment finishes, you can query `experiment_metrics` for a summary.

**DB at this point:**

```
constraint_sets --< generated_sentences >-- experiments
                          |                      |
                          v                      v
                  sentence_evaluations    experiment_metrics
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
Constraint Sets (hardcoded, then YAML, then benchmarks)
    |
    v
Generator (baseline GPT, then pluggable)
    |
    v
[generated_sentences] -------> Evaluators
                                    |
                                    v
                            [sentence_evaluations]
                                    |
                                    v
                              Aggregation
                                    |
                                    v
                           [experiment_metrics]
                                    |
                                    v
                             Analysis Queries
```

Each `[bracket]` is a database table. Tables are added phase by phase, not all at once.

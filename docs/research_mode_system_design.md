# Hybrid Morphological Constraint-Controlled Sentence Generation System

## Design Specification (v2.1)

> Changelog v1 → v2: constraint taxonomy split into lexical vs morphological with separate enforcement strategies (A2); independent gold evaluation set and parser-agreement reporting added (A3); fluency redefined via held-out LM perplexity (B6); human evaluation protocol added (B7); architecture phased — research infra before frontend (C11); cache semantics formalised with explicit identity key and reproducibility-vs-cost-saving split (C12).
>
> Changelog v2 → v2.1: §22 rewritten as a granular 9-phase implementation plan starting from the existing prompting endpoint. Phase 0–3 specify concrete file paths, YAML config schema, SQLite schema, metric definitions, and exit criteria. Single-source-of-truth principle adopted: production frontend and research runner share `/api/generate` with reproducibility parameters (`seed`, `temperature`) rather than maintaining a separate research code path. Gold set and human eval deferred to Phase 6 in favour of method-relative metrics early.

---

# 1. Project Overview

## Objective

This project explores morpho-syntactic constraint control for automatic sentence generation in language learning systems.

The system aims to generate pedagogically appropriate sentences that:

* include a target vocabulary word,
* satisfy grammatical constraints,
* maintain learner-appropriate complexity,
* remain fluent and diverse.

The project investigates multiple generation approaches, including:

* prompting baselines,
* generate-filter-rerank pipelines,
* constrained decoding,
* NeuroLogic-style symbolic decoding control,
* optional fine-tuning methods.

---

# 2. Core Research Questions

## Primary Research Question

How effectively can decoder-time symbolic constraints control morpho-syntactic structure during sentence generation?

---

## Secondary Questions

* Can constrained decoding outperform prompting-based approaches?
* What tradeoffs exist between:

  * constraint satisfaction,
  * diversity,
  * fluency,
  * latency,
  * cost?
* How should grammatical constraints be represented computationally?
* How does diversity change under increasing constraint complexity?

---

# 3. High-Level System Architecture

```text
                        ┌────────────────────┐
                        │   React Frontend   │
                        │   (Learning Mode)  │
                        └─────────┬──────────┘
                                  │
                                  ▼
                        ┌────────────────────┐
                        │      FastAPI       │
                        │    Core Backend    │
                        └─────────┬──────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
    ┌──────────────────┐                  ┌──────────────────┐
    │  Pipeline Engine │                  │     Database     │
    │                  │                  │                  │
    │ - Generation     │                  │ Experiments      │
    │ - Validation     │                  │ Outputs          │
    │ - Scoring        │                  │ Metrics          │
    │ - Constrainting  │                  │ Cache            │
    └─────────┬────────┘                  └──────────────────┘
              │
              ▼
    ┌──────────────────┐
    │     Streamlit    │
    │  Research Mode   │
    └──────────────────┘
```

---

# 4. Architectural Philosophy

The system separates:

* production learning functionality,
  from:
* experimental research infrastructure.

This allows:

* reproducible experimentation,
* systematic benchmarking,
* scalable evaluation,
* modular experimentation.

---

# 5. Modes of Operation

## 5.1 Learning Mode

### Purpose

Generate high-quality learner-facing practice sentences.

### Characteristics

* stochastic generation,
* diverse outputs,
* user-focused UX,
* low latency preferred.

### Frontend

* React / Next.js frontend.

### Behaviour

* generate single high-quality sentence,
* avoid repetition,
* maintain novelty.

---

## 5.2 Research Mode

### Purpose

Run controlled experiments and evaluate generation methods.

### Characteristics

* batch evaluation,
* reproducibility,
* statistical comparison,
* experiment tracking.

### Frontend

* Streamlit dashboard.

### Behaviour

* run N-sample experiments,
* store all generations,
* compute evaluation metrics,
* compare generation methods.

---

# 6. Core Pipeline Engine

The pipeline engine is the central research component.

## Responsibilities

* generation,
* constrained decoding,
* candidate filtering,
* grammar validation,
* scoring,
* experiment orchestration,
* caching.

---

# 7. Pipeline Components

## 7.1 Generator

Responsible for sentence generation.

### Supported Methods

* Prompting baseline,
* Generate-filter-rerank,
* NeuroLogic-style constrained decoding,
* Fine-tuned models (optional),
* Self-refinement pipelines (optional).

---

## 7.2 Constraint Engine

Responsible for enforcing morpho-syntactic constraints.

Constraints are split into two categories with **distinct enforcement strategies**, because Spanish is fusional — a single surface form (e.g. `comimos`) encodes lemma + tense + person + number simultaneously. Lexical constraints can be expressed at the token level; morphological constraints cannot.

### 7.2.1 Lexical Constraints

Enforced via token-level decoder-time mechanisms.

Examples:

* required keyword,
* lemma inclusion (expanded into the full inflection paradigm of surface forms),
* mandatory surface form.

Enforcement strategies:

* NeuroLogic-style constrained decoding,
* Dynamic Beam Allocation (DBA),
* `LogitsProcessor` / token-mask-based constraints.

### 7.2.2 Morphological Constraints

NOT enforceable as pure token-inclusion constraints. Enforced via **incremental grammar-aware validation** during decoding.

Examples:

* tense,
* person,
* number,
* gender / agreement.

Enforcement pipeline:

```text
beam expansion
   ↓
partial-sequence morphology analysis
   ↓
beam pruning  (hard)  OR  score penalty  (soft)
```

Tooling: spaCy / Stanza morphology features computed on partial hypotheses at chosen expansion checkpoints (full re-parse is expensive — see §7.4 latency notes).

### 7.2.3 Complexity Constraints

Treated as soft constraints / filters, not decode-time enforced.

Examples:

* CEFR-band proxy (frequency-list lookup + sentence-length cap — explicitly a *proxy*, not true CEFR),
* sentence length bounds,
* vocabulary complexity (frequency-band).

### 7.2.4 Constraint Representation Contract

Each constraint declares:

* `category` ∈ {lexical, morphological, complexity},
* `enforcement` ∈ {hard, soft, filter},
* `mechanism` ∈ {token_mask, incremental_parse, post_filter},
* `specification` (constraint payload).

This contract makes explicit which constraints participate in decoder-time control vs which are post-hoc filters.

---

## 7.3 Validator

Validates generated outputs.

### Validation Tasks

* grammar correctness,
* tense validation,
* agreement validation,
* keyword inclusion,
* parser consistency.

### Tools

* spaCy,
* Stanza,
* LanguageTool.

### 7.3.1 Circularity Hazard

The validator and the automatic scorer (§7.4) draw on the **same** parser stack. If a candidate is accepted because spaCy says its tense is correct, scoring tense accuracy with spaCy reports parser self-consistency, not ground truth.

Mitigations, all required:

1. **Tool separation per role.** Designate one tool as the *filter* (e.g. Stanza for morphology during validation) and a *different* tool as the *scorer* (e.g. spaCy + LanguageTool at evaluation time). Never the same tool in both roles for the same feature.
2. **Independent gold evaluation set** — see §17.2. All headline numbers are computed against gold labels, not the filter parser.
3. **Parser agreement reporting.** For every reported feature accuracy, also report the spaCy-vs-Stanza agreement rate on the same data. This is an upper bound on automatic-evaluation reliability.

---

## 7.4 Scorer

Computes evaluation metrics.

### Metrics

#### Constraint Satisfaction

* tense accuracy,
* agreement accuracy,
* keyword inclusion accuracy.

#### Linguistic Quality

* **fluency** — operationalised as token-level perplexity under a held-out Spanish language model (BERTIN / RoBERTa-bne or similar). The fluency LM is **fixed across all method comparisons** and is **never the generator** (avoids self-scoring bias). Reported as mean log-PPL with bootstrap CI.
* **grammaticality** — proportion of sentences passing LanguageTool with zero rule violations (independent of the filter parser; see §7.3.1).
* **parser confidence** — mean dependency-arc confidence from the scoring parser, reported alongside parser-agreement rate.
* **parser agreement** — spaCy-vs-Stanza agreement on key morphological features (tense / person / number), reported as a reliability bound on automatic evaluation.

#### Diversity

* lexical diversity,
* semantic diversity,
* n-gram uniqueness.

#### System Metrics

* latency,
* API cost,
* generation throughput.

---

# 8. Constraint Representation

Constraint representation is a central research problem.

---

## 8.1 Initial Constraint Representation

```json
{
  "keyword": "comer",
  "constraints": {
    "tense": "past",
    "person": "1pl",
    "complexity": "A1"
  }
}
```

---

## 8.2 Future Constraint Extensions

Potential future extensions:

* POS sequence constraints,
* dependency constraints,
* syntactic templates,
* symbolic grammar graphs.

---

# 9. Constrained Decoding

## Objective

Apply symbolic and grammar-aware constraints during decoder-time generation.

The framing is **incremental grammar-aware constrained decoding with partial morphological validation**, NOT pure symbolic token-only control. The system combines:

* token-level lexical constraints (NeuroLogic / DBA family),
* incremental morphological validation on partial beams.

---

## Proposed Decoder Architecture

```text
Prompt
   ↓
Constrained Beam Search
   ├── Lexical constraint state (CNF over inflection paradigm)
   └── Morphological validator (incremental parse at checkpoint k)
   ↓
Beam Pruning  (hard)  /  Score Penalty  (soft)
   ↓
Candidate Validation (full parse on completed beams)
   ↓
Output Selection
```

---

## Constraint Application Matrix

| Constraint kind  | Example         | Mechanism                                 | Hard/Soft |
| ---------------- | --------------- | ----------------------------------------- | --------- |
| Lexical (lemma)  | include `comer` | Token mask over inflection paradigm (DBA) | Hard      |
| Lexical (form)   | include `comimos` | Token mask over single surface form     | Hard      |
| Morphological    | 1pl past        | Incremental morph parse + beam prune      | Hard      |
| Morphological    | 1pl past        | Incremental morph parse + score penalty   | Soft      |
| Complexity (CEFR proxy) | A1 band  | Post-generation filter on completed beams | Filter    |

---

## MVP Implementation Phases

* **Phase 1** — Generate → validate → rerank baseline (no decoder-time enforcement).
* **Phase 2** — Beam-time incremental morphological validation (hard prune of one feature, e.g. tense).
* **Phase 3 (optional)** — FSM / regex-constrained decoding for richer morphological patterns via Outlines / `lm-format-enforcer` / `LogitsProcessor`.

Open-weights model required for Phase 2 onward (API-only models do not expose per-step logits or beam state).

---

# 10. Experimentation Framework

The research mode acts as a benchmark framework.

---

# 11. Experiment Configuration

Example configuration:

```json
{
  "method": "neurologic",
  "model": "gpt-4o-mini",
  "constraints": {
    "tense": "past",
    "person": "1pl"
  },
  "temperature": 0.7,
  "beam_width": 5,
  "samples": 100
}
```

---

# 12. Caching Philosophy

Caching has two distinct purposes with different policies. They are kept separate to avoid leaking cost-saving shortcuts into reported results.

## 12.1 Experiment Identity

An experiment is **uniquely identified** by:

```text
config_hash = SHA256(
  prompt
  + model_id            (pinned snapshot, e.g. gpt-4o-mini-2024-07-18)
  + decode_params       (temperature, top_p, top_k, beam_width, max_tokens, …)
  + constraint_spec     (full §7.2.4 contract, serialised canonically)
  + seed
)
```

Per stochastic run, the system records **one row per** `(config_hash, sample_index)`. This enables exact replay, per-sample tracking, and distribution-level evaluation.

## 12.2 Reproducibility Cache

Purpose: **exact replay** of any previously reported experiment.

* Deterministic capture of full config.
* Stored outputs, parser results, metrics, seeds, model snapshot ID, library versions.
* A cache hit corresponds to exact experiment replay.
* Never invalidated silently. Schema changes go through explicit migration.

All numbers in the thesis are sourced from this cache.

## 12.3 Cost-Saving Cache

Purpose: **fast iteration during development**.

* May relax the identity key (e.g. ignore seed, ignore minor prompt whitespace) at the developer's discretion.
* **Never** sourced for reported numbers. Reported numbers always re-run against the reproducibility cache.
* Cleared between experimental campaigns.

## 12.4 Stochasticity

Caching does NOT eliminate diversity. The unit of cache is the *experiment run* (a distribution of N samples under a fixed seed), not a single deterministic output.

---

# 13. Cached Components

## Cached Data

* experiment configurations (§12.1 identity key),
* prompts (verbatim, file path + content hash),
* generated outputs (per sample_index),
* parser results (filter parser AND scorer parser, stored separately),
* evaluation metrics,
* timestamps,
* model versions (pinned snapshots),
* random seeds,
* library versions (`transformers`, `torch`, `spacy`, `stanza`, `languagetool`).

---

# 14. Experiment Execution Flow

```text
Experiment Config
       ↓
Hash / Experiment ID
       ↓
Cache Lookup
       ↓
If Missing:
    Generate N Samples
       ↓
Validate
       ↓
Score
       ↓
Store Results
       ↓
Visualise Metrics
```

---

# 15. Database Design

## 15.1 Experiments Table

| Field     | Description           |
| --------- | --------------------- |
| id        | experiment ID         |
| method    | generation method     |
| model     | model used            |
| config    | serialized parameters |
| timestamp | execution time        |

---

## 15.2 Generations Table

| Field         | Description        |
| ------------- | ------------------ |
| experiment_id | parent experiment  |
| prompt        | input prompt       |
| output        | generated sentence |
| latency       | generation latency |

---

## 15.3 Metrics Table

| Field           | Description       |
| --------------- | ----------------- |
| generation_id   | parent generation |
| grammar_score   | grammar metric    |
| diversity_score | diversity metric  |
| fluency_score   | fluency metric    |

---

## 15.4 Parsed Features Table

| Field           | Description       |
| --------------- | ----------------- |
| generation_id   | parent generation |
| tense           | detected tense    |
| person          | detected person   |
| dependency_tree | parsed syntax     |

---

# 16. Diversity Evaluation

Diversity is treated as:

* a distribution-level property,
  NOT:
* a single-output property.

---

## Diversity Metrics

Potential metrics:

* Self-BLEU,
* distinct-n,
* embedding similarity,
* semantic entropy.

---

# 17. Research Evaluation Strategy

## 17.1 Baseline Ladder

### Phase 1

Prompting baseline.

### Phase 2

Generate-filter-rerank.

### Phase 3

Constrained decoding (lexical + incremental morphological — see §9).

### Phase 4

Optional fine-tuning.

---

## 17.2 Gold Evaluation Set

A held-out, **manually labelled** evaluation set is the source of ground truth. It is **independent of the validator parser** and is the basis for all headline numbers in the thesis.

### Scope

* 200–500 Spanish sentences.
* Target lemma stratified across CEFR bands and tense/person/number cells.
* Labels: target lemma present (Y/N), tense, person, number, agreement OK (Y/N), fluency (Y/N), and a coarse appropriateness band.

### Labelling

* Native or near-native speaker.
* Author cross-check pass.
* (Explicitly excluded: language-learner-only labelling — reliability too low.)

### Use

* All accuracy and grammaticality numbers are computed against gold labels.
* Parser-derived numbers are reported alongside as a comparison and as a parser-reliability bound.

---

## 17.3 Human Evaluation Study

Required to support the thesis's pedagogical claims.

### Design

* Sample: 50–100 generated sentences, balanced across methods and constraint configurations.
* Raters: 2–3 fluent / native Spanish speakers (blinded to method).
* Rating dimensions (5-point Likert):

  * grammatical correctness,
  * fluency / naturalness,
  * learner appropriateness,
  * CEFR-band suitability.

### Reliability

* Inter-rater agreement reported as **Fleiss' κ** (≥3 raters) or **Cohen's κ** (2 raters), with bootstrap CI.
* Disagreement cases logged and categorised in the error analysis.

### Output

* Per-method human-vs-automatic correlation table.
* Failure-class taxonomy from disagreement and low-rated cases.

---

# 18. Proposed Initial Scope

## Language

Spanish only.

---

## Initial Grammar Constraints

* tense,
* person,
* number.

---

## Complexity

Basic CEFR approximation.

---

# 19. Dataset Strategy

Initial system does NOT require large-scale training datasets.

### Primary Approach

Inference-time control.

### Optional Future Work

Semi-synthetic dataset creation:

* LLM generation,
* parser validation,
* automatic filtering.

---

# 20. Key Research Contribution

The project’s primary contribution is expected to be:

> A systematic framework for morpho-syntactic constraint control during sentence generation using decoder-time symbolic constraints.

---

# 21. Future Extensions

Potential future directions:

* multilingual evaluation,
* adaptive learner modelling,
* online learning,
* RL-based learner progression,
* symbolic grammar graphs,
* hybrid fine-tuning + constrained decoding.

---

# 22. Phased Implementation Plan

The build order is **research infrastructure first, frontend last**. The thesis is an NLP research project; web engineering is a vehicle, not a deliverable.

The plan assumes the prompting baseline already exists as a FastAPI endpoint (`/api/generate`, [backend/app/api/generate.py](backend/app/api/generate.py)). The first four phases extract research value from what is already built; later phases add new generation methods.

**Architectural principle (single source of truth).** Both the production frontend and the research runner call the same HTTP endpoint. Research mode is *not* a separate code path — it is the same endpoint exercised with explicit reproducibility parameters (`seed`, `temperature`). This avoids generator drift between production and research.

---

## 22.1 Phase 0 — Endpoint reproducibility extension

### Objective

Make the existing prompting baseline endpoint reproducible and parameterised for research use, without changing its production behaviour.

### Deliverables

* Modified [backend/app/api/generate.py](backend/app/api/generate.py).
* Updated [backend/tests/](backend/tests/) coverage.

### Specification

Extend `GenerateRequest` with two optional fields:

```python
seed: int | None = None
temperature: float | None = None
```

Pass both to `client.chat.completions.create(...)` when present. When absent, retain current production defaults so existing callers are unaffected.

### Exit criteria

* Two identical requests with the same `seed` and `temperature` return identical outputs (OpenAI `seed` is best-effort, but `system_fingerprint` should match).
* All existing tests still pass.
* New test: `test_generate_seed_reproducibility` asserts identical output across two calls with the same seed (mock or live, gated by API key).

### Out of scope

* No changes to generator behaviour, prompt template, or response shape.
* No new endpoints.

### Estimate

~30 minutes including tests.

---

## 22.2 Phase 1 — Research runner (CLI + SQLite cache)

### Objective

A re-runnable CLI that exercises `/api/generate` across an experiment grid, persists every output, and is idempotent on re-run (cache hits skip work).

### Deliverables

* `research/runner.py` — CLI entry point.
* `research/cache.py` — SQLite schema + read/write helpers.
* `research/configs/baseline_smoke.yaml` — first runnable experiment config.
* `research/experiments.db` — generated, gitignored.

### YAML config schema

```yaml
name: baseline_smoke
method: prompting           # generator method; later phases add 'rerank', 'constrained'
model: gpt-4o-mini-2024-07-18  # pinned snapshot
temperature: 0.7
seeds: [0, 1, 2]            # number of seeds → number of independent runs per cell
samples_per_seed: 100       # N per (config, seed) cell
grid:
  word:    [comer, hablar, vivir, beber, escribir]
  tense:   [present, past, future]
  person:  [1st, 3rd]
  number:  [singular, plural]
constraints:
  lexicon_constraint: off   # production-side LOS-502 constraint, separate from morphology
```

The Cartesian product of `grid` × `seeds` × `samples_per_seed` defines the full run. Each `(config, seed)` cell produces `samples_per_seed` rows.

### SQLite schema

```sql
CREATE TABLE experiments (
  config_hash    TEXT PRIMARY KEY,   -- §12.1 identity key
  name           TEXT NOT NULL,      -- human-readable experiment name
  method         TEXT NOT NULL,
  model          TEXT NOT NULL,
  config_json    TEXT NOT NULL,      -- full canonical config for replay
  created_at     TEXT NOT NULL       -- ISO8601 UTC
);

CREATE TABLE generations (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  config_hash    TEXT NOT NULL REFERENCES experiments(config_hash),
  sample_index   INTEGER NOT NULL,
  seed           INTEGER NOT NULL,
  word           TEXT NOT NULL,
  tense          TEXT NOT NULL,
  person         TEXT NOT NULL,
  number         TEXT NOT NULL,
  sentence       TEXT NOT NULL,
  translation    TEXT,
  latency_ms     INTEGER,
  raw_response   TEXT,                -- full JSON from endpoint, for replay
  UNIQUE (config_hash, sample_index)
);

CREATE INDEX idx_generations_config ON generations(config_hash);
```

Metrics live in a separate table (Phase 2). Parser features and human-eval results get their own tables when added (later phases).

### Cache key (§12.1)

```text
config_hash = sha256_hex(
  canonical_json({
    method, model, temperature,
    word, tense, person, number,
    seed, lexicon_constraint
  })
)[:16]
```

Canonical serialisation: keys sorted, no whitespace, UTF-8.

### CLI behaviour

```bash
cd research
python runner.py --config configs/baseline_smoke.yaml
python runner.py --config configs/baseline_smoke.yaml   # second run → all cache hits
python runner.py --config configs/baseline_smoke.yaml --force   # ignore cache
```

For each `(grid cell, seed)`:
1. Compute `config_hash`.
2. If `SELECT COUNT(*) FROM generations WHERE config_hash = ?` ≥ `samples_per_seed`, skip.
3. Otherwise, call `POST /api/generate` `samples_per_seed` times, insert rows in a single transaction at the end of the cell.
4. Log progress to stdout.

### Failure handling

* HTTP errors retry up to 3× with exponential backoff.
* On terminal failure of a cell, log and continue; partial cells are *not* committed (transactional insert at cell end).

### Exit criteria

* `runner.py --config configs/baseline_smoke.yaml` populates SQLite with the full grid.
* Second invocation completes in <1s (all cache hits).
* `sqlite3 experiments.db 'SELECT count(*) FROM generations;'` returns the expected count.

### Out of scope

* No metrics computation (Phase 2).
* No plots (Phase 3).
* No new generation methods (Phase 4+).

### Estimate

~3–4 hours including a runnable smoke config and one cached re-run.

---

## 22.3 Phase 2 — Metrics module

### Objective

Compute method-relative metrics on cached generations, without a gold set. Absolute (gold-anchored) metrics arrive in Phase 6.

### Deliverables

* `research/metrics/__init__.py`
* `research/metrics/diversity.py` — distinct-n, Self-BLEU.
* `research/metrics/constraint.py` — parser-based morphological satisfaction (Stanza).
* `research/metrics/fluency.py` — held-out LM perplexity (BERTIN or RoBERTa-bne).
* `research/metrics/run.py` — CLI that scores all uncomputed generations and writes a `metrics` table.

### SQLite extension

```sql
CREATE TABLE metrics (
  generation_id        INTEGER PRIMARY KEY REFERENCES generations(id),
  -- constraint satisfaction (parser-derived, NOT gold-anchored)
  tense_match          INTEGER,        -- 0/1, parser-detected
  person_match         INTEGER,
  number_match         INTEGER,
  keyword_present      INTEGER,
  -- fluency / quality
  log_perplexity       REAL,           -- held-out LM
  parser_confidence    REAL,
  -- bookkeeping
  scorer_version       TEXT NOT NULL,  -- e.g. 'stanza-1.8.2+bertin-v2'
  scored_at            TEXT NOT NULL
);

CREATE TABLE diversity_metrics (
  config_hash          TEXT PRIMARY KEY REFERENCES experiments(config_hash),
  distinct_1           REAL,
  distinct_2           REAL,
  distinct_3           REAL,
  self_bleu_4          REAL,           -- mean Self-BLEU across the sample set
  n_samples            INTEGER NOT NULL,
  scored_at            TEXT NOT NULL
);
```

`metrics` is per-sentence (joins to `generations`). `diversity_metrics` is per-config (a distribution-level property — see §16).

### Metric definitions

| Metric                | Definition                                                                                  | Scope     |
| --------------------- | ------------------------------------------------------------------------------------------- | --------- |
| `tense_match`         | `1` iff Stanza-parsed main-verb tense feature equals requested tense                        | per-sentence |
| `person_match`        | `1` iff Stanza-parsed main-verb person feature equals requested person                      | per-sentence |
| `number_match`        | `1` iff Stanza-parsed main-verb number feature equals requested number                      | per-sentence |
| `keyword_present`     | `1` iff any inflected form of the target lemma appears (`spacy` lemmatiser cross-check)     | per-sentence |
| `log_perplexity`      | mean log-PPL of the sentence under a fixed held-out Spanish LM (BERTIN)                     | per-sentence |
| `parser_confidence`   | mean dependency-arc score from the scoring parser                                           | per-sentence |
| `distinct_1/2/3`      | `\|unique n-grams\|` / `\|total n-grams\|` over all samples in the config                   | per-config |
| `self_bleu_4`         | mean pairwise BLEU-4 across all sample pairs in the config (lower = more diverse)           | per-config |

**Parser separation (per §7.3.1):** Stanza is the *scorer* parser. spaCy lemmatisation is used only for keyword cross-check. The filter parser introduced in Phase 4 (rerank) will be a *different* tool — spaCy proper — so the scorer is never the filter.

**Fluency LM:** fixed at module import time, never the generator. Currently: `bertin-project/bertin-roberta-base-spanish` for masked-LM pseudo-perplexity, OR a Spanish causal LM if available (decision logged in `scorer_version`).

### CLI behaviour

```bash
python -m research.metrics.run                 # score all unscored generations
python -m research.metrics.run --rescore       # ignore existing scores
python -m research.metrics.run --config-hash <hash>  # one config only
```

### Exit criteria

* `metrics` table populated for every row in `generations`.
* `diversity_metrics` table populated for every distinct `config_hash`.
* Re-run is idempotent (`scorer_version` unchanged → skip).
* Smoke check: `SELECT AVG(tense_match) FROM metrics JOIN generations USING(id)` returns plausible value (~0.7–0.95 for prompting baseline).

### Out of scope

* No gold-set validation (Phase 6).
* No human eval (Phase 6).
* No parser-agreement metric yet (added when spaCy is wired as a second scorer in Phase 4).

### Estimate

~1 day, dominated by getting Stanza + BERTIN running locally.

---

## 22.4 Phase 3 — First analysis notebook

### Objective

A single Jupyter notebook that loads the SQLite cache and produces the **first thesis figure**: a Pareto plot of constraint satisfaction vs diversity, faceted by tense/person.

### Deliverables

* `research/notebooks/01_baseline_analysis.ipynb`.
* Static export `research/figures/baseline_pareto.pdf`.

### Notebook structure

1. **Load.** `pandas.read_sql` over `experiments`, `generations`, `metrics`, `diversity_metrics`.
2. **Aggregate.** Per `(config_hash)`: mean of `*_match`, mean `log_perplexity`, joined to `distinct_2`, `self_bleu_4`.
3. **Per-seed CIs.** Bootstrap 95% CIs across seeds for every cell (≥3 seeds required).
4. **Plots.**

   * Figure 1: scatter of `mean(tense_match)` vs `distinct_2`, one point per `(word, tense, person, number)` cell, error bars from seed bootstrap.
   * Figure 2: bar chart of `mean(*_match)` per constraint dimension.
   * Figure 3: histogram of `log_perplexity` across samples.
5. **Sanity table.** Top-10 highest-PPL outputs (likely failures), top-10 lowest (likely fluent) — qualitative check.

### Exit criteria

* Notebook runs end-to-end on a fresh checkout (assuming `experiments.db` exists).
* `baseline_pareto.pdf` is a publication-quality figure (labelled axes, legend, CIs).
* At least one observation is written into the notebook text: e.g. "1st-person constraints satisfy at X%; 3rd-person at Y% — discuss."

### Out of scope

* No method comparison yet (only one method exists). The plot will have one curve.
* No statistical significance testing across methods (Phase 4+).

### Estimate

~half a day.

---

## 22.5 Phase 4 — Generate-filter-rerank

### Objective

Second generation method: over-generate `k` candidates, validate morphology with a parser, rerank, return top-1.

### Deliverables

* `backend/app/core/generators/rerank.py` — pure function, importable by both the endpoint and the runner.
* Extension to `/api/generate` accepting `method: "prompting" | "rerank"`.
* `research/configs/rerank_vs_baseline.yaml`.

### Specification

1. Call existing prompting generator with `num_candidates = k` (e.g. 10).
2. Parse each candidate with **spaCy** (the *filter* parser, distinct from Stanza which scores).
3. Score each candidate by morphological match against requested constraints.
4. Return top-1.

Filter parser is spaCy; scorer parser remains Stanza (per §7.3.1).

### Exit criteria

* Notebook now produces two Pareto curves (prompting vs rerank).
* Paired test (bootstrap, same prompts) reports the gap with 95% CI.

### Out of scope

* No decoder-time intervention. The OpenAI call is unchanged; the new logic sits outside the model.

### Estimate

~2 days.

---

## 22.6 Phase 5 — Decoder-time control (open-weights)

### Objective

Third generation method: lexical-constrained decoding (DBA over the lemma's inflection paradigm), then incremental morphological pruning (single feature — tense — first).

### Prerequisites

* GPU access confirmed (Imperial DoC cluster or HPC; quota verified).
* Open-weights model chosen and downloaded: Llama-3-8B-Instruct or Qwen2.5-7B-Instruct in 4-bit (bitsandbytes).
* Inflection paradigm lookup for Spanish verbs (`mlconjug3` or pre-computed CSV).

### Deliverables

* `backend/app/core/generators/constrained.py`.
* New endpoint route or extension of `/api/generate` accepting `method: "constrained"`.
* `research/configs/constrained_lexical.yaml`, `research/configs/constrained_morph.yaml`.

### Specification (sub-phases)

* **5A — Lexical (DBA).** `LogitsProcessor` masks all tokens not in the inflection paradigm of the target lemma until a paradigm token has been emitted. Hard constraint.
* **5B — Morphological (tense only, incremental).** At every `k = 4` tokens, parse the partial hypothesis with Stanza; prune beams whose detected tense disagrees with the target. Hard prune, single feature.

Person, number, gender are *evaluated* (in `metrics`) but **not** enforced at decode time in v1 of the thesis.

### Exit criteria

* Three Pareto curves now overlayed (prompting / rerank / constrained).
* Latency reported per method (expected: constrained ~10×–50× slower than prompting).
* The first concrete diversity-vs-constraint tradeoff observation appears in the thesis draft.

### Out of scope

* Soft constraints, hybrid constraints (deferred to thesis future-work).
* Multi-feature decoder-time enforcement (deferred).

### Estimate

~3 weeks. This is the thesis core. Allow slip.

---

## 22.7 Phase 6 — Gold set + human evaluation

### Objective

Anchor the (until-now-relative) automatic metrics to ground truth and validate pedagogical claims.

### Deliverables

* `research/data/gold_set.csv` — 200–500 sentences, manually labelled (§17.2).
* `research/data/human_eval.csv` — 50–100 sentences with Likert ratings from 2–3 raters (§17.3).
* `research/notebooks/02_gold_validation.ipynb`.
* `research/notebooks/03_human_eval.ipynb`.

### Specification

* Gold-set labelling protocol documented in `research/data/README.md`.
* Inter-rater agreement: Fleiss' κ (≥3 raters) or Cohen's κ (2 raters), bootstrap CI.
* Parser-agreement metric (spaCy vs Stanza) added to the metrics table at this point.

### Exit criteria

* All headline thesis numbers move from "parser-derived" to "gold-anchored."
* Human-vs-automatic correlation reported.
* Failure taxonomy (≥5 categories) derived from disagreement cases.

### Estimate

~2 weeks (mostly labelling time, not coding).

---

## 22.8 Phase 7 — Streamlit dashboard

### Objective

Visualise cached experiment results for thesis figures and viva demo.

Streamlit is **read-only** over the SQLite cache. It does not generate. It does not write. Every artefact in the dashboard is reproducible from `experiments.db`.

### Deliverables

* `research/app.py` — fleshes out the current 13-line stub.

### Estimate

~half a week.

---

## 22.9 Phase 8 — React integration (optional)

Only if Phase 5 lands on schedule. The user-facing app already exists; integrating a chosen method into the production endpoint is a configuration change, not new research.

---

## 22.10 Open issues from v2 review (still pending)

These are not blockers for Phase 0–3, but must be addressed before Phase 5 results are written up:

* **A1 — Closed-model + decoder-time control mismatch.** Resolved by Phase 5 prerequisite: open-weights model commitment.
* **B4 — Reproducibility contract.** Phase 1's `config_hash` is a partial fix. Full contract (pinned library versions, prompt file hashes) added in Phase 5.
* **B5 — Sample size & statistical testing.** Bootstrap CIs in Phase 3 notebook; paired tests in Phase 4 notebook.
* **B8 — CEFR proxy.** Defer until learner-facing claims become concrete (Phase 6 or later).
* **B9 — Pareto sweep design.** Implicit in Phase 3 and grows naturally through Phase 4–5.
* **D16 — Contribution claim.** Revisit framing after Phase 5 results land; soften §20 if the morphological-enforcement story is weaker than hoped.

---

# 23. Success Criteria

The project will be considered successful if it demonstrates:

* controllable grammatical generation,
* measurable constraint satisfaction,
* improved learner appropriateness,
* meaningful diversity/accuracy tradeoff analysis,
* reproducible evaluation methodology.

---

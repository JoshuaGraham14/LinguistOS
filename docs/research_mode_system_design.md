# Hybrid Morphological Constraint-Controlled Sentence Generation System

## Design Specification (v1)

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

### Initial Supported Constraints

#### Lexical Constraints

* required keyword,
* lemma inclusion.

#### Morphological Constraints

* tense,
* person,
* number,
* gender.

#### Complexity Constraints

* CEFR level,
* sentence length,
* vocabulary complexity.

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

---

## 7.4 Scorer

Computes evaluation metrics.

### Metrics

#### Constraint Satisfaction

* tense accuracy,
* agreement accuracy,
* keyword inclusion accuracy.

#### Linguistic Quality

* fluency,
* grammaticality,
* parser confidence.

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

# 9. NeuroLogic-Style Decoding

## Objective

Apply symbolic constraints during decoder-time generation.

---

## Proposed Decoder Architecture

```text
Prompt
   ↓
Constrained Beam Search
   ↓
Constraint State Tracking
   ↓
Candidate Validation
   ↓
Output Selection
```

---

## Constraint Types

### Hard Constraints

Invalid beams removed immediately.

### Soft Constraints

Constraint violations penalised during scoring.

### Hybrid Constraints

Combination of:

* hard lexical constraints,
* soft grammatical constraints.

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

Caching is designed for:

* reproducibility,
* reduced API cost,
* experiment tracking.

Caching is NOT intended to:

* eliminate generation diversity.

---

## Key Principle

The system caches:

* experiment runs,
  NOT:
* single deterministic outputs.

---

# 13. Cached Components

## Cached Data

* experiment configurations,
* prompts,
* generated outputs,
* parser results,
* evaluation metrics,
* timestamps,
* model versions,
* random seeds.

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

## Baseline Ladder

### Phase 1

Prompting baseline.

### Phase 2

Generate-filter-rerank.

### Phase 3

Constrained decoding.

### Phase 4

Optional fine-tuning.

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

# 22. Immediate Development Priorities

## Infrastructure

* experiment tracking,
* evaluation framework,
* caching layer.

---

## Baselines

* prompting,
* generate-filter-rerank.

---

## Core Research

* grammatical constraint representation,
* constrained decoding experiments.

---

# 23. Success Criteria

The project will be considered successful if it demonstrates:

* controllable grammatical generation,
* measurable constraint satisfaction,
* improved learner appropriateness,
* meaningful diversity/accuracy tradeoff analysis,
* reproducible evaluation methodology.

---

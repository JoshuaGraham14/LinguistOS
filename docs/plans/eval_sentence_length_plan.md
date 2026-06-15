# Sentence Length — Implementation Plan

> Wire `sentence_length` as a generation parameter and evaluate compliance, syntactic
> complexity, and downstream effects on constraint / grammar / diversity metrics.
>
> Parent plan: [`evaluation_metrics_implementation_plan.md`](evaluation_metrics_implementation_plan.md) (Phase F).

---

## Goal

Answer three questions for the dissertation:

1. **Compliance:** Does GPT produce sentences in the requested length band?
2. **Complexity:** Does `"long"` actually yield more clausal structure (not just more tokens)?
3. **Trade-offs:** How do length settings affect constraint satisfaction, grammar, and diversity?

---

## Length bands (token counts)

Tokenization: reuse `research/evaluation/distribution/tokens.py` (whitespace, lowercase,
strip `¿¡` and punctuation).

| Label | Min tokens | Max tokens | Intended use |
| --- | --- | --- | --- |
| `short` | 2 | 5 | Minimal drill items |
| `medium` | 5 | 9 | Standard practice sentences |
| `long` | 10 | 16 | Context-rich examples |

**Note:** `5` is in both `short` and `medium`. This is intentional — each experiment has
exactly one target band, so there is no per-sentence ambiguity. When comparing across
conditions, a 5-token output is in-band for both `short` and `medium` runs.

Store bands in `research/evaluation/length_bands.py`:

```python
LENGTH_BANDS = {
    "short":  (2, 5),
    "medium": (5, 9),
    "long":   (10, 16),
}
```

Prompt text should include numeric guidance, e.g. *"2–5 tokens"* not just *"short"*.

---

## Experiment grid (`spanish_basic`)

Six live runs (2 methods × 3 length settings):

| Method config | Generator | `sentence_length` |
| --- | --- | --- |
| `baseline_short` | `baseline_gpt` | `short` |
| `baseline_medium` | `baseline_gpt` | `medium` |
| `baseline_long` | `baseline_gpt` | `long` |
| `individual_short` | `individual_gpt` | `short` |
| `individual_medium` | `individual_gpt` | `medium` |
| `individual_long` | `individual_gpt` | `long` |

```bash
# Example (repeat for all six)
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_short --live
python3 -m research.run_experiment --benchmark spanish_basic --method individual_long --live
```

Experiment names should encode length, e.g.
`baseline_gpt_spanish_basic_live_short`, so notebook pivots can filter by suffix.

---

## New evaluators and metrics

### Stage 1 — Sentence evaluators

| `name` | Module | Score | `details` |
| --- | --- | --- | --- |
| `length_in_band` | `sentence/length_in_band.py` | 1.0 if token count in target band else 0.0 | `token_count`, `target_length`, `min`, `max`, `in_band` |
| `clause_count` | `sentence/clause_count.py` | Normalised count (see below) | `clause_count`, `token_count`, `parse_ok`, `tool` |

**`length_in_band` inputs:** `sentence_length` passed via `constraints` dict (pipeline adds
it from method config alongside `keyword`, `tense`, etc.).

**`clause_count` implementation (spaCy `es_core_news_sm`):**

Count clausal predicates as:

1. Start at 1 for the main clause (`ROOT` verb/aux).
2. Add 1 for each token with dep_ in `{ccomp, xcomp, advcl, relcl}` whose head is `VERB`/`AUX`.
3. Add coordinated verbs at clause level via `conj` chains on `VERB`/`AUX` (exclude conjuncts
   that are arguments of a single predicate).

Store raw integer in `details.clause_count`. Score: cap-normalise for roll-ups, e.g.
`min(clause_count, 4) / 4` so 4+ clauses → 1.0 (tunable).

On parse failure: `score=0.0`, `parse_ok=false`, `clause_count=null`.

### Stage 2b — Distribution metrics

| `name` | Module | What it measures |
| --- | --- | --- |
| `mean_token_count` / `_experiment` | `distribution/mean_token_count.py` | Mean tokens per sentence |
| `length_cv` / `_experiment` | `distribution/length_cv.py` | CV of token counts within batch |
| `mean_clauses` / `_experiment` | `distribution/mean_clauses.py` | Mean `clause_count` from evaluator `details` |

`length_cv` is **enabled for length experiments** (unlike the method-comparison skip) — it
measures whether a batch is uniformly on-target or mixes short and long outliers.

### Stage 2a — Roll-ups (automatic)

Existing roll-ups apply to new sentence evaluators:

- `pass_rate::length_in_band` — **headline compliance metric**
- `mean::clause_count` — average normalised complexity score

---

## Generation wiring (prerequisite)

`build_prompt()` already accepts `sentence_length` but the research pipeline does not pass it.

### 1. Method YAML

```yaml
name: baseline_short
method: baseline_gpt
samples_per_case: 3
config:
  model: gpt-5.4-nano
  temperature: 0.7
  sentence_length: short
```

Add six files under `research/methods/`. Keep `baseline_default` / `individual_default`
as `short` (or explicit `sentence_length: short`) for backward compatibility.

### 2. `BaseGenerator.generate()`

Add `sentence_length: str = "short"` keyword arg to `base.py`, `baseline_gpt.py`,
`individual_gpt.py`.

### 3. `build_prompt()`

Include numeric band in prompt:

```
Constraints: tense=..., person=..., number=..., length=short (2–5 tokens).
```

### 4. `pipeline.py`

- Read `sentence_length` from `method_config.config.get("sentence_length", "short")`.
- Pass to `generator.generate(..., sentence_length=...)`.
- Include in `generation_meta` on each `GeneratedSentence`.
- Append `_{sentence_length}` to experiment `name` for live/mock runs.
- Add `sentence_length` to constraints dict passed to evaluators.

### 5. `ConstraintSet.to_constraints_dict()` — no schema change

Pipeline merges runtime fields (`sentence_length`, `expected_form`) into the constraints
dict before calling evaluators (same pattern as today).

---

## Analysis notebook

Extend `explore_live_spanish_basic.ipynb` (or add `explore_length_grid.ipynb`):

**Pivot axes:** `method` (baseline vs individual) × `sentence_length` (short / medium / long)

**Headline columns per cell:**

| Question | Metrics |
| --- | --- |
| Length compliance | `pass_rate::length_in_band`, `mean_token_count_experiment` |
| Syntactic complexity | `mean::clause_count`, `mean_clauses_experiment` |
| Constraint cost | `pass_rate::expected_form_match` |
| Grammar cost | `errors_per_100w::grammar_languagetool` |
| Diversity | `self_bleu_experiment`, `distinct_1_experiment` |
| Human (Phase D) | Acceptability / pedagogical fit by length band |

---

## Implementation order

| Step | Task | Status |
| --- | --- | --- |
| 1 | `length_bands.py` + tests | **Done** |
| 2 | Wire `sentence_length` through generator + pipeline | **Done** |
| 3 | Six method YAMLs | **Done** |
| 4 | `length_in_band` evaluator + tests | **Done** |
| 5 | `clause_count` evaluator + tests | **Done** |
| 6 | Distribution metrics (`mean_token_count`, `length_cv`, `mean_clauses`) | **Done** |
| 7 | Register evaluators + metrics | **Done** |
| 8 | Mock smoke run on one length config | **Done** (`baseline_medium`) |
| 9 | Live 6-run grid on `spanish_basic` | **Done** (experiments id=12–17) |
| 10 | Notebook pivot (method × length) | **Done** (`explore_live_spanish_basic.ipynb` §4) |

---

## Tests (minimum)

- `length_in_band`: 4 tokens + `short` → pass; 8 tokens + `short` → fail; 12 tokens + `long` → pass
- `clause_count`: simple sentence → 1; sentence with `que` complement → 2+; mock spaCy in CI
- `mean_token_count` / `length_cv`: known token-length fixture batch
- Pipeline: method YAML `sentence_length` reaches prompt and `generation_meta`
- Experiment name includes length suffix

---

## Done when

1. All six grid runs complete on `spanish_basic` (live).
2. `pass_rate::length_in_band` is high (>0.8) for `short` and `medium`; `long` may be lower (document).
3. `mean_clauses_experiment` increases monotonically short < medium < long (on average).
4. Notebook pivot shows constraint / grammar / diversity trade-offs by length.
5. Human ratings (Phase D) stratified by length band — optional but recommended for write-up.

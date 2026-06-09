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
| **Constraint satisfaction** | Does the output use the target word in the requested tense, person, and number? | `expected_form_match` |
| **Length compliance** | Does the output match the requested sentence length band? | `length_in_band` (+ `mean_token_count`) |
| **Syntactic complexity** | Does longer generation produce more clausal structure? | `clause_count`, `mean_clauses` |
| **Tool reliability** | How often do parsers / LLM judges agree with gold surface forms? | `verb_morphology` `details`, LLM disagreement, distribution diagnostics |
| **Output quality** | Are sentences grammatically coherent and pedagogically suitable? | `grammar_languagetool` (+ human ratings) |
| **Batch usefulness** | Does a run produce varied, non-repetitive practice material? | Distribution metrics |

Where possible, combine **automatic evaluation** (this pipeline) with **human judgement**
(on a stratified sample) to validate automatic scores.

---

## Current state (June 2026)

### Implemented

| Component | Location | Status |
| --- | --- | --- |
| Sentence evaluator interface | `research/evaluation/sentence/base.py` | Done |
| `ExpectedFormMatchEvaluator` | `research/evaluation/sentence/expected_form.py` | Done — **primary constraint metric** |
| `VerbMorphologyEvaluator` | `research/evaluation/sentence/verb_morphology.py` | Done — **diagnostic only** (see below) |
| `LanguageToolGrammarEvaluator` | `research/evaluation/sentence/languagetool.py` | Done — **secondary grammar quality** |
| `LtErrorBreakdownMetric` | `research/evaluation/distribution/lt_error_breakdown.py` | Done |
| `grammar_stub` | `research/evaluation/sentence/grammar.py` | Retired from registry (module kept for reference) |
| Morph configs | `research/evaluation/morph_configs/` | Done (Spanish) |
| Distribution metric interface | `research/evaluation/distribution/base.py` | Done |
| `UniquenessRatioMetric` | `research/evaluation/distribution/uniqueness.py` | Done |
| `SelfBleuMetric` | `research/evaluation/distribution/self_bleu.py` | Done |
| `TemplateRateMetric` | `research/evaluation/distribution/template_rate.py` | Done |
| `DistinctNgramMetric` | `research/evaluation/distribution/distinct_ngram.py` | Done (distinct_1 + distinct_2) |
| Shared tokenization | `research/evaluation/distribution/tokens.py` | Done (strips `¿¡` + punctuation) |
| Roll-ups | `research/evaluation/rollups.py` | Done (`mean::`, `min::`, `std::`, `pass_rate::`, `errors_per_100w::`) |
| Registries | `sentence/__init__.py`, `distribution/__init__.py` | Done |
| Pipeline hooks | `research/pipeline.py` | Stage 1 → 2b → 2a |

### Evaluator strategy (decision note, June 2026)

**Primary constraint satisfaction:** `expected_form_match` — does the sentence contain the
requested surface form? This directly matches the generation goal (use the target verb in
*this* form). Deterministic, reproducible, and passes all mock gold outputs.

**spaCy (`verb_morphology`) — keep registered, not headline:** Empirical probing on
`spanish_basic` mock outputs (`es_core_news_sm` / `md` / `lg`) shows ~67–73% pass on
sentences that `expected_form_match` scores 100% on. spaCy cannot accept morph hints;
failures are parser mis-tags and homographs, not generation errors. Keep
`VerbMorphologyEvaluator` in `DEFAULT_EVALUATORS` for now so it runs on every experiment,
stores `details` (including `parser_disagreement`), and rolls up as
`pass_rate::verb_morphology` — useful for tool-reliability analysis until we fully drop
parser-based constraint scoring. It does **not** gate generation or other evaluators; report
`pass_rate::expected_form_match` as the headline constraint column.

### Not yet implemented

- Human rating import (Phase D)
- Sentence length parameter + evaluators (Phase F) — see [`eval_sentence_length_plan.md`](eval_sentence_length_plan.md)
- Hebrew benchmark + evaluators (Phase E)
- Parser batch diagnostics (`morph_failure_mode`, `parse_failure_rate`) — explicitly deferred

### Removed from scope (do not implement)

- `llm_morph_match` — LLM morph judge
- `keyword_presence` — redundant with `expected_form_match` for verb constraints
- `alignment` — translation/reference alignment (COMET, BLEU vs gold)
- `fluency_heuristic` — token-count / TTR heuristics

---

## Evaluation granularity (recap)

Three layers already exist in the pipeline. This plan fills in **what to add** at each layer.

| Kind | What it measures | Code hook | Storage | Roll-up? |
| --- | --- | --- | --- | --- |
| **Per-sentence (Stage 1)** | One generated output | `BaseEvaluator.evaluate(...)` | `sentence_evaluations` | Yes → Stage 2a |
| **Distribution (Stage 2b)** | Whole batch jointly | `BaseGroupMetric.compute(...)` | `experiment_metrics` | No |
| **Roll-up (Stage 2a)** | Summary of sentence scores | `aggregate_sentence_eval_rollups()` | `experiment_metrics` | N/A (is the roll-up) |

**Rule:** Distribution metrics must not be derivable from a single sentence row (e.g. self-BLEU).
Roll-ups must not duplicate joint metrics (e.g. `pass_rate::expected_form_match` vs a separate
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
| Expected form match | `sentence/expected_form.py` | `expected_form_match` | Gold surface form present as whole token | **Done** — primary constraint metric |
| Verb morphology | `sentence/verb_morphology.py` | `verb_morphology` | Tense, person, number on constrained verb | **Done** — diagnostic only; parse sentence, compare `Morph` features to mapped expected set |
| Length in band | `sentence/length_in_band.py` | `length_in_band` | Token count within target band | **Phase F** — see [`eval_sentence_length_plan.md`](eval_sentence_length_plan.md) |
| Clause count | `sentence/clause_count.py` | `clause_count` | Clausal predicates via spaCy deps | **Phase F** |

**Retired `grammar_stub`:** Removed from `DEFAULT_EVALUATORS`; superseded by
`expected_form_match` and `grammar_languagetool`.

**Spanish first:** Use spaCy `es_core_news_sm` (or `md`). Add model to `research/requirements.txt`
and document download step in `research/README.md`.

---

### Tier 2 — Quality and tool reliability

| Evaluator | Module (proposed) | `name` | What it checks | Implementation |
| --- | --- | --- | --- | --- |
| LanguageTool grammar | `sentence/languagetool.py` | `grammar_languagetool` | Surface grammaticality | LanguageTool on target sentence; binary score; rich `details` for roll-ups and breakdown (see **Phase C — LanguageTool**) |
| CEFR lexical | `sentence/cefr_lexical.py` | `cefr_lexical` | Vocabulary band | Optional — only when `cefr_level` set; compare token frequencies against CEFR word list |

**Removed — `alignment`, `keyword_presence`, `llm_morph_match`:** Not needed for thesis evaluation.

**Rejected — `fluency_heuristic`:** Token-count / TTR / trigram checks target degenerate
NLG collapse. GPT-class generators already produce fluent-looking sentences; the real quality
gaps are subtle grammar errors and unnatural phrasing — use `grammar_languagetool` and human
ratings instead.

**Tool disagreement logging:** When both `verb_morphology` and `grammar_languagetool` run,
store both verdicts in their respective `details`. Notebook analysis can measure correlation and
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
| Self-BLEU | `self_bleu.py` | `self_bleu` / `self_bleu_experiment` | Mean BLEU of each sentence vs rest of batch | **Done** — sacrebleu `intl` tokenizer, smoothed; lower = more diverse |
| Distinct-n | `distinct_ngram.py` | `distinct_1` / `distinct_1_experiment`, `distinct_2` / `distinct_2_experiment` | Unique n-grams / total n-grams (tokenized) | **Done** — one `DistinctNgramMetric` class, `n=1` and `n=2` |
| Template rate | `template_rate.py` | `template_rate` / `template_rate_experiment` | Share sharing same first-k tokens (default k=3) | **Done** — detects mode collapse ("Yo corro…" × N) |
| Mean token count | `mean_token_count.py` | `mean_token_count` / `_experiment` | Average tokens per sentence | **Phase F** — length compliance analysis |
| Length CV | `length_cv.py` | `length_cv` / `length_cv_experiment` | Coefficient of variation of token counts | **Phase F** — enabled for length grid (not method comparison) |
| Mean clauses | `mean_clauses.py` | `mean_clauses` / `_experiment` | Mean clausal count from `clause_count` eval | **Phase F** |

---

### Tier 2 — Batch-level constraint diagnostics

These summarize failure **patterns** across a batch. Prefer computing from sentence
`details` where possible rather than re-parsing.

| Metric | Module (proposed) | `name` | What it measures | Notes |
| --- | --- | --- | --- | --- |
| Morph failure mode | `morph_failure_mode.py` | `morph_failure_mode` | Counts of tense vs person vs number mismatches | Reads `verb_morphology` eval `details` for the batch; `breakdown` JSON holds histogram |
| LT error breakdown | `lt_error_breakdown.py` | `lt_error_breakdown` / `lt_error_breakdown_experiment` | Histogram of LT error categories | Reads `grammar_languagetool` `details.matches` for the batch; `breakdown` JSON (see Phase C) |
| Parse failure rate | `parse_failure_rate.py` | `parse_failure_rate` / `_experiment` | Fraction where `parse_ok: false` | Tool reliability at batch level |
| All-fail keyword | `all_fail_keyword.py` | `all_fail_keyword` | 1.0 if every sample misses keyword | Flags broken runs |

**Overlap with roll-ups:** `pass_rate::expected_form_match` per constraint set already measures
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
| `errors_per_100w::<evaluator>` | `100 × Σ details.match_count / Σ details.token_count` (Phase C, LT only) |

Scopes: per `constraint_set` and pooled `experiment`-wide (weighted by sentence count).

**Dissertation tables:** Compare methods via experiment-wide
`pass_rate::expected_form_match` (constraint headline),
`pass_rate::grammar_languagetool` (grammar headline / EFSR),
`errors_per_100w::grammar_languagetool` (length-normalised severity),
`pass_rate::verb_morphology` (parser diagnostic), and distribution metrics
(`uniqueness_ratio_experiment`, `self_bleu_experiment`, `template_rate_experiment`,
`distinct_1_experiment`, `distinct_2_experiment`, `lt_error_breakdown_experiment`)
in `research/explore_live_spanish_basic.ipynb` (or `explore.ipynb`).

**Future roll-ups (optional):** median, p25/p75 — add to `rollups.py` only if needed for tables.

---

## Implementation phases

### Phase A — Constraint satisfaction core *(done)*

**Goal:** Reliable constraint checking without depending on parser morph tags.

1. ~~`expected_form` on constraint sets + `expected_form_match`~~ **Done**
2. ~~`verb_morphology` + morph configs (spaCy diagnostic)~~ **Done** — keep in registry, not headline
3. ~~Run mock + live experiments; notebook compares `expected_form_match` vs `verb_morphology`~~ **Done**

**Done when:** ~~`pass_rate::expected_form_match` meaningful on live GPT output~~ ✓ (100% on `spanish_basic` / `spanish_challenging` live runs).

---

### Phase B — Distribution metrics for generation comparison *(done)*

**Goal:** Quantify diversity differences between methods.

1. ~~Implement `self_bleu` (constraint_set + experiment)~~ **Done** — `sacrebleu>=2.4`, `tokenize='intl'`
2. ~~Implement `template_rate` (k=3) and `distinct_1` / `distinct_2`~~ **Done**
3. ~~Tests with repetitive / varied / near-duplicate fixture batches~~ **Done** (`test_group_metrics.py`)
4. ~~Compare `baseline_default` vs `individual_default` on live `spanish_basic`~~ **Done**

**Live validation (June 2026, `spanish_basic`):**

| Metric | baseline | individual |
| --- | --- | --- |
| `uniqueness_ratio_experiment` | 1.00 | 0.67 |
| `self_bleu_experiment` | 0.26 | 0.77 |
| `template_rate_experiment` | 0.00 | 0.80 |
| `distinct_1_experiment` | 0.70 | 0.47 |
| `distinct_2_experiment` | 0.91 | 0.51 |

All five point the same direction. Notebooks updated (`explore_live_spanish_basic.ipynb`,
`explore_live_spanish_challenging.ipynb`). Mock runs use identical canned data per benchmark
so diversity metrics only diverge on live output.

**Done when:** ~~Experiment pivot shows distinct diversity signatures per method~~ ✓

---

### Phase C — LanguageTool grammar quality layer *(done)*

**Goal:** Add a grammar-quality signal **independent of spaCy and gold labels**, with honest
scoping. LanguageTool is a **secondary** metric — not ground truth, not a constraint checker.

#### Three independent signals (methodology framing)

| Signal | Evaluator | Role |
| --- | --- | --- |
| Constraint satisfaction | `expected_form_match` | **Headline** — gold surface form present |
| Grammar quality | `grammar_languagetool` | **Secondary** — rule-based grammaticality |
| Parser diagnostic | `verb_morphology` | **Diagnostic** — spaCy morph tags vs gold |

**What LanguageTool catches that `expected_form_match` misses:** pronoun–verb disagreement
(`Yo comimos`), det–noun agreement (`Las chico`), contractions (`a el` → `al`), some prep
errors (`de queísmo`). **What it misses:** wrong conjugation with no surface conflict
(`Nosotros como` for preterite), unnatural phrasing, constraint satisfaction.

**Do not:** treat LT as ground truth; use LT for morphology-specific constraint checking;
report "LanguageTool accuracy"; add FreeLing or Stanza for Spanish in this phase.

#### How it maps onto the pipeline

One evaluator (Stage 1) produces three derived signals at the layers they belong to:

| Layer | Component | Output |
| --- | --- | --- |
| **Stage 1** | `grammar_languagetool` evaluator | Row in `sentence_evaluations`; binary score; rich `details` |
| **Stage 2a** | Existing roll-ups + one extension | `pass_rate::grammar_languagetool` (EFSR, free); `errors_per_100w::grammar_languagetool` (new) |
| **Stage 2b** | `lt_error_breakdown` distribution metric | Category histogram in `experiment_metrics.breakdown` |

Runner order unchanged: **Stage 1 → Stage 2b → Stage 2a**. No schema or pipeline changes.

#### Stage 1 — `grammar_languagetool` evaluator

- **Module:** `research/evaluation/sentence/languagetool.py`
- **Register:** `DEFAULT_EVALUATORS` in `sentence/__init__.py`
- **Server:** cached `LanguageTool(language)` per process (same pattern as `_NLP_CACHE` in
  `verb_morphology.py`); local server default; mock client in tests (no Java in CI)
- **Language:** from `constraints["target_language"]` (default `es`)

**Rule filter (allowlist):** count only matches in:

- `AGREEMENT_VERBS`
- `AGREEMENT_NOUNS`
- `GRAMMAR`
- `MISSPELLING` (contractions such as `a el` → `al`)
- `CONFUSIONS` (e.g. `al tienda` → `a la tienda`)

**Exclude:** `TYPOS`, `DIACRITICS`, `CASING`, `STYLE`, `REDUNDANCY` — LLMs often omit accents
or capitals; these are not grammar slips for this thesis.

**Scoring:** `1.0` if zero filtered matches, else `0.0` (binary; partial scores derivable in
notebook from `details`).

**`details` schema** (source of truth for Stage 2a and 2b):

```json
{
  "passed": false,
  "match_count": 1,
  "total_match_count": 2,
  "token_count": 6,
  "matches": [
    {
      "rule": "AGREEMENT_PRONOUNSUBJECT_VERB",
      "category": "AGREEMENT_VERBS",
      "message": "Posible falta de concordancia…",
      "offset": 3,
      "error_length": 7,
      "replacements": ["comí"]
    }
  ]
}
```

On server failure: `score=0.0`, `details.error` set, `matches=[]`.

#### Stage 2a — LT roll-ups

| Metric | Formula | Notes |
| --- | --- | --- |
| **EFSR** | `pass_rate::grammar_languagetool` | Error-Free Sentence Rate; **headline LT metric**; no new code |
| **Errors per 100 words** | `100 × Σ match_count / Σ token_count` | Length-normalised; fair across methods that differ in sentence length; **extend `rollups.py`** |

Optional: mean errors per sentence (`mean::` over a derived per-sentence count) — correlated
with EFSR; report only if a single severity number is needed.

#### Stage 2b — `lt_error_breakdown`

- **Module:** `research/evaluation/distribution/lt_error_breakdown.py`
- **Scopes:** `lt_error_breakdown` (per constraint set) + `lt_error_breakdown_experiment` (pooled)
- **Input:** `grammar_languagetool` `details.matches` from sentence rows (do not re-run LT)
- **Output:** `metric_value` = total filtered errors; `breakdown` JSON = category histogram

```json
{
  "AGREEMENT_VERBS": 12,
  "AGREEMENT_NOUNS": 5,
  "GRAMMAR": 3,
  "MISSPELLING": 1
}
```

#### Dissertation outputs

**Method comparison table** (one row per generation method):

| Column | Source |
| --- | --- |
| `pass_rate::expected_form_match` | Stage 2a — constraint headline |
| `pass_rate::grammar_languagetool` | Stage 2a — grammar headline (EFSR) |
| `errors_per_100w::grammar_languagetool` | Stage 2a — length-normalised severity |
| Top categories | Stage 2b — `lt_error_breakdown_experiment` |

**Disagreement table** (notebook, from sentence-level rows):

| `expected_form_match` | `grammar_languagetool` | Interpretation |
| --- | --- | --- |
| PASS | PASS | Likely good |
| FAIL | PASS | Wrong form; otherwise grammatical |
| PASS | FAIL | **Right form, grammar slip** (e.g. `Yo comimos`) |
| FAIL | FAIL | Broken on multiple axes |

Appendix: sample of flagged `details.matches` (rule, message, sentence) for qualitative evidence.

#### Implementation checklist (Phase C)

1. `research/evaluation/sentence/languagetool.py` — evaluator
2. `research/evaluation/sentence/__init__.py` — register
3. `research/evaluation/rollups.py` — `errors_per_100w::` family
4. `research/evaluation/distribution/lt_error_breakdown.py` — breakdown metric
5. `research/evaluation/distribution/__init__.py` — register both scopes
6. Tests: mock LT in `test_evaluation.py`; breakdown in `test_group_metrics.py`
7. `research/requirements.txt` — `language-tool-python>=2.8`
8. `research/README.md` — Java requirement for local LT server

**Done when:** Live `spanish_basic` run produces EFSR, errors/100w, and category breakdown;
notebook disagreement table is populated.

#### Deferred from Phase C

- Distribution `parse_failure_rate` and `morph_failure_mode` (spaCy tool-reliability) — not needed
- Optional: `cefr_lexical` when benchmarks include `cefr_level`

---

### Phase D — Human validation

**Goal:** Ground automatic metrics in human judgement.

1. Export sentence sample CSV from notebook
2. Implement `human_rating` import evaluator
3. Compute correlation (automatic vs human) in notebook
4. Write up agreement / disagreement patterns for dissertation

**Done when:** At least one table correlating `expected_form_match` with human acceptability.

---

### Phase F — Sentence length parameter and evaluation *(code done; grid pending)*

**Goal:** Wire `sentence_length` as a generation parameter and measure compliance, clausal
complexity, and trade-offs on constraint / grammar / diversity metrics.

**Detailed plan:** [`eval_sentence_length_plan.md`](eval_sentence_length_plan.md)

**Implemented:** `length_bands.py`, `length_in_band`, `clause_count`, `mean_token_count`,
`length_cv`, `mean_clauses`; six method YAMLs; pipeline wiring; 183 tests passing.

**Length bands (tokens):**

| Label | Min | Max |
| --- | --- | --- |
| `short` | 2 | 5 |
| `medium` | 5 | 9 |
| `long` | 10 | 16 |

**Experiment grid (`spanish_basic`):** 2 methods × 3 lengths = 6 runs:

`baseline_{short,medium,long}`, `individual_{short,medium,long}`

**New evaluators:** `length_in_band`, `clause_count` (spaCy clausal deps)

**New distribution metrics:** `mean_token_count`, `length_cv`, `mean_clauses`

**Implementation order:**

1. `length_bands.py` + wire `sentence_length` through methods YAML → pipeline → generators
2. Six method configs + experiment naming suffix (`_short`, `_medium`, `_long`)
3. `length_in_band` and `clause_count` sentence evaluators
4. Length distribution metrics + tests
5. Live 6-run grid; notebook pivot (method × length × metrics)

**Done when:** Grid complete; `pass_rate::length_in_band` and `mean_clauses_experiment` show
expected patterns; notebook documents constraint/grammar/diversity trade-offs by length.

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
| We can enforce morpho-syntax | `expected_form_match`, `verb_morphology` | `morph_failure_mode` | Spot-check sample |
| Automatic tools are imperfect but usable | `grammar_languagetool` vs `expected_form_match` vs `verb_morphology` | `lt_error_breakdown`, `parse_failure_rate` | Required subset |
| Batched vs individual generation differs | Roll-up `pass_rate::expected_form_match` | `self_bleu`, `uniqueness_ratio`, `template_rate`, `distinct_1`, `distinct_2` | Optional |
| Length parameter works | `pass_rate::length_in_band`, `mean_token_count` | `length_cv`, `mean_clauses` | Pedagogical fit by band |
| Spanish vs Hebrew | Same evaluators, different parser | Same metrics, per-language runs | Yes for Hebrew |

---

## Open decisions (resolve before Phase A coding)

| Decision | Options | Recommendation |
| --- | --- | --- |
| **Partial vs binary scoring** | Partial credit per morph feature vs strict all-or-nothing | Partial credit for analysis; report `pass_rate::` with threshold 1.0 as strict column in notebook |
| **Human scale** | Binary vs Likert 1–5 | Likert for nuance; binary for inter-rater agreement (Cohen's κ) |
| **Length band at 5 tokens** | Shared boundary vs exclusive | Inclusive bands per label; each experiment has one target (see Phase F plan) |
| **Clause counting** | spaCy dep heuristics vs manual | spaCy `{ccomp, xcomp, advcl, relcl, conj}` on `VERB`/`AUX`; document limitations in appendix |
| **Parser on failure** | Score 0 vs skip sentence | Score 0 with `parse_ok: false` in `details` |

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
| `language-tool-python` | `grammar_languagetool` | Local server (Java, ~259MB first download); mock in CI |
| `sacrebleu>=2.4` | `self_bleu` | Installed; `tokenize='intl'`, `smooth_method='exp'` |
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
                                    (self_bleu, lt_error_breakdown, morph_failure_mode, ...)
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

1. ~~**`expected_form_match`** produces interpretable pass rates on live GPT runs across `spanish_basic`~~ ✓
2. ~~**`details`** support error analysis (which constraint dimension fails most often)~~ ✓
3. ~~**At least two distribution metrics** distinguish batched vs individual generation~~ ✓ (five metrics validated live)
4. **Human ratings** on a sample validate automatic constraint scores — **remaining**
5. ~~**Notebook** can pivot experiment-wide metrics for method and language comparison~~ ✓
